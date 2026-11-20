"""Private Korean Reader pages and form endpoints."""

import json
from uuid import UUID

from flask import Blueprint, abort, current_app, g, jsonify, redirect, render_template, request, url_for
from httpx import HTTPError
from postgrest.exceptions import APIError

from server import korean_analysis as llm, korean_store as store
from server.auth import login_required
from server.meta import Metadata

bp = Blueprint("korean", __name__, url_prefix="/korean")


@bp.before_request
@login_required
def require_user():
    pass


@bp.errorhandler(APIError)
@bp.errorhandler(HTTPError)
def database_error(error):
    current_app.logger.warning("Korean Reader database request failed (%s).", type(error).__name__)
    message = "The Korean Reader is temporarily unavailable. Please try again."
    if request.endpoint == "korean.knowledge":
        return jsonify(error=message), 503
    return _page("error", "Korean Reader", error=message), 503


def _page(template, title, **context):
    metadata = Metadata(title=title, robots={"index": False, "follow": False},
                        googlebot={"index": False, "follow": False})
    return render_template(f"korean/{template}.jinja", **metadata.serialize(), **context)


def _library(**context):
    return _page("library", "Korean Reader", documents=store.documents(g.user["id"]),
                 limit=llm.MAX_PASSAGE, **context)


@bp.get("/", strict_slashes=False)
def library():
    return _library()


@bp.post("/documents")
def ingest():
    text = request.form.get("text", "")
    title = request.form.get("title", "").strip()
    source = request.form.get("source", "").strip()
    try:
        exact_text = request.form.get("text_json")
        if exact_text is not None:
            try:
                if not exact_text.lstrip().startswith('"'):
                    raise ValueError
                value = json.loads(exact_text)
                value.encode("utf-8")
            except ValueError:
                raise llm.ReaderError("The pasted text could not be read. Please paste it again.") from None
            text = value
        if not llm.HANGUL.search(text):
            raise llm.ReaderError("Paste a passage containing Korean text.")
        if len(text) > llm.MAX_PASSAGE:
            raise llm.ReaderError(f"Use a passage of at most {llm.MAX_PASSAGE} characters.")
        if "\x00" in text + title + source:
            raise llm.ReaderError("Remove null characters from the passage and try again.")
        if len(title) > 120 or len(source) > 180:
            raise llm.ReaderError("Use a title of at most 120 characters and a source of at most 180.")
        excerpt = " ".join(text.split())
        fallback = excerpt if len(excerpt) <= 46 else excerpt[:46] + "…"
        document_id = store.ingest(g.user["id"], title or fallback, text, source or None)
    except llm.ReaderError as exc:
        return _library(error=str(exc), draft={"title": title, "text": text, "source": source}), 422
    return redirect(url_for("korean.reader", document_id=document_id), code=303)


def _document(document_id: UUID):
    document = store.document(g.user["id"], str(document_id))
    if document is None:
        abort(404)
    return document


def _reader(document, error=None, gloss_error=None):
    annotations = document["analysis"]["annotations"]
    concepts = store.concept_details(g.user["id"], annotations)
    segments = llm.render_segments(document["original_text"], annotations)
    for segment in segments:
        segment["unknown"] = any(
            concepts.get(concept_id, {}).get("recognition") == "learning"
            for index in segment["annotation_ids"] for concept_id in annotations[index]["concept_ids"]
        )
    return _page("reader", document["title"], document=document, segments=segments,
                 annotations=annotations, concepts=concepts, error=error, gloss_error=gloss_error,
                 missing_glosses=bool(store.missing_word_glosses(document)))


@bp.get("/documents/<uuid:document_id>")
def reader(document_id):
    return _reader(_document(document_id))


@bp.post("/documents/<uuid:document_id>/word-glosses")
def add_word_glosses(document_id):
    doc = _document(document_id)
    try:
        store.add_word_glosses(g.user["id"], doc)
    except llm.ReaderError as exc:
        return _reader(doc, gloss_error=str(exc)), 422
    return redirect(url_for("korean.reader", document_id=document_id), code=303)


@bp.post("/documents/<uuid:document_id>/delete")
def delete(document_id):
    if not store.delete_document(g.user["id"], str(document_id)):
        abort(404)
    return redirect(url_for("korean.library"), code=303)


@bp.patch("/knowledge/<uuid:concept_id>")
def knowledge(concept_id):
    data = request.get_json(silent=True)
    state = data.get("recognition") if isinstance(data, dict) else None
    if state not in ("known", "learning"):
        return jsonify(error="Choose Known or Learning."), 400
    if not store.set_recognition(g.user["id"], str(concept_id), state):
        abort(404)
    return jsonify(recognition=state)


@bp.post("/documents/<uuid:document_id>/practice")
def start_practice(document_id):
    document = _document(document_id)
    annotations = document["analysis"]["annotations"]
    concepts = store.concept_details(g.user["id"], annotations)
    try:
        targets = store.practice_targets(annotations, concepts)
        if not targets:
            raise llm.ReaderError("This passage has no concepts available to practice.")
        exercises = llm.generate_practice(document, targets)
        session_id = store.create_practice(g.user["id"], str(document_id), exercises)
    except llm.ReaderError as exc:
        return _reader(document, error=str(exc)), 422
    return redirect(url_for("korean.exercise", document_id=document_id, session_id=session_id, position=0), code=303)


@bp.route("/documents/<uuid:document_id>/practice/<uuid:session_id>/<int:position>", methods=["GET", "POST"])
def exercise(document_id, session_id, position):
    user_id = g.user["id"]
    practice = store.practice(user_id, str(session_id), str(document_id))
    if not practice or not 0 <= position < len(practice["exercises"]):
        abort(404)
    attempts = store.attempts(user_id, str(session_id))
    if any(previous not in attempts for previous in range(position)):
        abort(404)

    item = practice["exercises"][position]
    attempt = attempts.get(position)
    error = None
    if request.method == "POST":
        try:
            if attempt is None:
                answer = llm.validate_answer(request.form.get("answer", ""))
                result = llm.evaluate(item, answer)
                store.record_attempt(str(session_id), position, answer, result.model_dump())
        except llm.ReaderError as exc:
            error = str(exc)
        else:
            return redirect(url_for("korean.exercise", document_id=document_id,
                                    session_id=session_id, position=position), code=303)
    return _page("practice", "Practice · Korean Reader", document_id=document_id, session_id=session_id,
                 position=position, count=len(practice["exercises"]), prompt=item["prompt"],
                 attempt=attempt, error=error, draft=request.form.get("answer", ""),
                 limit=llm.MAX_ANSWER), 422 if error else 200

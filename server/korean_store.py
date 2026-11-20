"""Reader persistence through the request's authenticated Supabase client."""

from hashlib import sha256
from uuid import uuid4

from flask import current_app
from httpx import HTTPError
from postgrest.exceptions import APIError

from server import db, korean_analysis as llm


def _owned(table, user_id):
    return db.get().table(table).select("*").eq("user_id", user_id)


def _first(query):
    rows = query.limit(1).execute().data
    return rows[0] if rows else None


def _rpc(name, values):
    return db.get().rpc(f"korean_{name}", values).execute().data


def documents(user_id):
    return (
        db.get().table("korean_documents").select("id,title,source,created_at")
        .eq("user_id", user_id).order("created_at", desc=True).execute().data
    )


def document(user_id, document_id):
    return _first(_owned("korean_documents", user_id).eq("id", document_id))


def delete_document(user_id, document_id):
    return bool(db.get().table("korean_documents").delete()
                .eq("user_id", user_id).eq("id", document_id).execute().data)


def _cached_document(user_id, content_hash, version):
    return _first(_owned("korean_documents", user_id)
                  .eq("content_hash", content_hash).eq("analysis_version", version))


def _catalog(user_id):
    return (db.get().table("korean_concepts").select("kind,form,sense,meaning")
            .eq("user_id", user_id).order("created_at", desc=True).limit(40).execute().data)


def _release_claim(user_id, lease):
    try:
        (db.get().table("korean_import_claims").delete().eq("user_id", user_id)
         .eq("lease", lease).execute())
    except (APIError, HTTPError):
        current_app.logger.warning("Korean Reader could not release an analysis claim.")


def ingest(user_id, title, text, source):
    model = llm.model_name()
    version = f"{llm.ANALYSIS_VERSION}:{model}"
    content_hash = sha256(text.encode()).hexdigest()
    existing = _cached_document(user_id, content_hash, version)
    if existing:
        return existing["id"]

    lease = str(uuid4())
    claim = {"p_hash": content_hash, "p_version": version, "p_lease": lease}
    if not _rpc("claim_import", claim):
        existing = _cached_document(user_id, content_hash, version)
        if existing:
            return existing["id"]
        raise llm.ReaderError("This passage is already being analyzed. Try again in a moment.")

    document_id = None
    try:
        analysis = llm.analyze(text, _catalog(user_id), model=model)
        document_id = _rpc("save_document", claim | {
            "p_title": title,
            "p_text": text,
            "p_source": source,
            "p_translation": analysis.translation,
            "p_concepts": llm.concept_rows(analysis.concepts),
            "p_annotations": [annotation.model_dump() for annotation in analysis.annotations],
        })
        if not document_id:
            raise llm.ReaderError("This import expired. Please try again.")
        return document_id
    finally:
        if not document_id:
            _release_claim(user_id, lease)


def missing_word_glosses(doc):
    return llm.missing_words(doc["original_text"], (
        (item["start"], item["end"]) for item in doc["analysis"]["annotations"]
    ))


def add_word_glosses(user_id, doc):
    if not missing_word_glosses(doc):
        return

    lease = str(uuid4())
    if not _rpc("claim_import", {
        "p_hash": doc["content_hash"], "p_version": f"{doc['analysis_version']}:word-glosses", "p_lease": lease,
    }):
        raise llm.ReaderError("Word glosses are already being prepared. Try again in a moment.")

    saved = False
    try:
        current = document(user_id, doc["id"])
        if current is None:
            raise llm.ReaderError("This passage is no longer available.")
        gaps = missing_word_glosses(current)
        if not gaps:
            return
        concepts, annotations = llm.fill_word_gaps(current["original_text"], gaps, _catalog(user_id), model=llm.model_name())
        saved = _rpc("add_word_glosses", {
            "p_document": doc["id"], "p_lease": lease,
            "p_concepts": llm.concept_rows(concepts), "p_annotations": [item.model_dump() for item in annotations],
        })
        if not saved:
            raise llm.ReaderError("The word gloss request expired. Please try again.")
    finally:
        if not saved:
            _release_claim(user_id, lease)


def concept_details(user_id, annotations):
    ids = sorted({concept for annotation in annotations for concept in annotation["concept_ids"]})
    if not ids:
        return {}
    def rows_by_id(table, column):
        return {
            row[column]: row for start in range(0, len(ids), 80)
            for row in _owned(table, user_id).in_(column, ids[start:start + 80]).execute().data
        }

    concepts = rows_by_id("korean_concepts", "id")
    knowledge = rows_by_id("korean_user_knowledge", "concept_id")
    return {
        concept_id: {
            "id": concept_id,
            "form": concept["form"],
            "kind": concept["kind"],
            "meaning": concept["meaning"],
            "recognition": knowledge.get(concept_id, {}).get("recognition_state", "learning"),
            "production": knowledge.get(concept_id, {}).get("production_state", "unpracticed"),
        }
        for concept_id, concept in concepts.items()
    }


def set_recognition(user_id, concept_id, state):
    if not _first(_owned("korean_concepts", user_id).eq("id", concept_id)):
        return False
    (db.get().table("korean_user_knowledge").upsert(
        {"user_id": user_id, "concept_id": concept_id, "recognition_state": state},
        on_conflict="user_id,concept_id",
    ).execute())
    return True


def practice_targets(annotations, concepts):
    ids = dict.fromkeys(concept_id for annotation in annotations for concept_id in annotation["concept_ids"])
    prioritized = sorted((concepts[concept_id] for concept_id in ids if concept_id in concepts),
                         key=lambda item: (item["production"] != "needs_practice",
                                           item["recognition"] == "known",
                                           item["kind"] != "construction"))
    return [{field: concept[field] for field in ("id", "form", "kind", "meaning")}
            for concept in prioritized[:10]]


def create_practice(user_id, document_id, exercises):
    return db.get().table("korean_practice_sessions").insert({
        "user_id": user_id, "document_id": document_id, "exercises": exercises,
    }).execute().data[0]["id"]


def practice(user_id, session_id, document_id):
    return _first(_owned("korean_practice_sessions", user_id)
                  .eq("id", session_id).eq("document_id", document_id))


def attempts(user_id, session_id):
    rows = _owned("korean_exercise_attempts", user_id).eq("session_id", session_id).execute().data
    return {row["position"]: row for row in rows}


def record_attempt(session_id, position, answer, result):
    _rpc("record_attempt", {
        "p_session": session_id, "p_position": position, "p_answer": answer, "p_result": result,
    })

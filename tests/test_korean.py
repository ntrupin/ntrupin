import json
import re
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from noah import create_app
from server import korean_analysis as llm, korean_store as store

USER = str(uuid4())
DOCUMENT = str(uuid4())
CONCEPT = str(uuid4())
CONSTRUCTION = str(uuid4())
PRACTICE = str(uuid4())
TEXT = "  🐈 말하려고 했는데 못 했어.\r\n 말하려고 했어. "
SURFACE = "말하려고"
OTHER = "말하려고 했는데 못 했어"
BASE = f"/korean/documents/{DOCUMENT}"
EXERCISE = f"{BASE}/practice/{PRACTICE}/0"


def analysis():
    concepts = [
        llm.Concept(kind="lexical", form="말하다", sense="tell", meaning="to tell", aliases=[]),
        llm.Concept(kind="construction", form="-(으)려고 하다", sense="intention",
                    meaning="intend to do", aliases=["-려고 하다"]),
    ]
    return llm.PassageAnalysis(translation="I meant to tell them, but I couldn't.", concepts=concepts, annotations=[
        llm.Annotation(start=4, end=8, surface=SURFACE, kind="word", gloss="going to tell",
                       breakdown="말하다 + -(으)려고", explanation="", concept_refs=[0]),
        llm.Annotation(start=4, end=4 + len(OTHER), surface=OTHER, kind="clause",
                       gloss="meant to tell them but couldn't", breakdown="",
                       explanation="The second clause describes inability.", concept_refs=[1]),
    ])


def document():
    data = analysis().model_dump(exclude={"concepts"})
    for annotation in data["annotations"]:
        annotation["concept_ids"] = [[CONCEPT, CONSTRUCTION][ref] for ref in annotation.pop("concept_refs")]
    return {"id": DOCUMENT, "title": "An intention", "original_text": TEXT, "source": None, "analysis": data}


def exercise(kind="production"):
    return {"kind": kind, "prompt": "Use -려고 하다.", "constraints": "Include the intention construction.",
            "alternatives": ["말하려고 했어요"], "explanation": "The ending signals intention.", "concept_ids": [CONCEPT]}


class AnalysisTests(unittest.TestCase):
    def test_code_point_spans_and_overlap(self):
        result = llm.validate_spans(TEXT, analysis())
        segments = llm.render_segments(TEXT, [item.model_dump() for item in result.annotations])
        self.assertEqual("".join(segment["text"] for segment in segments), TEXT)
        self.assertEqual([segment["annotation_ids"] for segment in segments], [[], [0, 1], [1], []])
        self.assertEqual(segments[1]["text"], SURFACE)

    def test_existing_phrase_and_overlapping_spans_count_as_coverage(self):
        text = "“한국 노래를” 🐈 자주 듣는다."
        start = text.index("한국")
        end = text.index("”")
        gaps = llm.missing_words(text, [(start, end), (text.index("듣는다"), len(text) - 2)])
        self.assertEqual([text[a:b] for a, b in gaps], ["자주", "듣는다"])
        self.assertEqual(llm.missing_words(text, [(start, end), *gaps]), [])

    def test_unique_surface_repairs_indices_but_repeated_surface_does_not(self):
        result = analysis()
        result.annotations[1].start = 0
        self.assertEqual(llm.validate_spans(TEXT, result).annotations[1].start, 4)
        result.annotations[0].start = 0
        with self.assertRaises(llm.AnalysisOutputError):
            llm.validate_spans(TEXT, result)

    def test_missing_surface_and_invalid_concept_references(self):
        for update in ({"surface": "존재하지 않는 말"}, {"concept_refs": [-1]}):
            with self.subTest(update=update), self.assertRaises(llm.AnalysisOutputError):
                result = analysis()
                result.annotations[0] = result.annotations[0].model_copy(update=update)
                llm.validate_spans(TEXT, result)

    def test_canonical_keys_distinguish_senses_and_reuse_aliases(self):
        concept = analysis().concepts[1]
        alias = concept.model_copy(update={"form": "–려고하다", "sense": "Intention!"})
        other_sense = concept.model_copy(update={"sense": "reason"})
        canonical, alternate, distinct = llm.concept_rows([concept, alias, other_sense])
        self.assertIn(alternate["key"], canonical["alias_keys"])
        self.assertNotEqual(canonical["key"], distinct["key"])

    @patch.dict("os.environ", {"OPENAI_API_KEY": "mock"})
    @patch("server.korean_analysis.OpenAI")
    def test_analysis_retries_invalid_response_then_returns_valid_output(self, client):
        invalid = analysis()
        invalid.annotations[0].start = -1
        parse = client.return_value.__enter__.return_value.responses.parse
        def response(result):
            return SimpleNamespace(status="completed", output_parsed=result, usage=None)
        parse.side_effect = [response(invalid), response(analysis())]
        with patch.object(llm, "fill_word_gaps", return_value=([], [])):
            self.assertEqual(llm.analyze(TEXT, [], model=llm.DEFAULT_MODEL), analysis())
        self.assertEqual(parse.call_count, 2)
        self.assertFalse(parse.call_args.kwargs["store"])

    @patch.dict("os.environ", {"OPENAI_API_KEY": "mock"})
    @patch("server.korean_analysis.OpenAI")
    def test_analysis_stops_after_two_failed_outputs(self, client):
        parse = client.return_value.__enter__.return_value.responses.parse
        parse.return_value = SimpleNamespace(status="incomplete", output_parsed=None, usage=None)
        with self.assertRaises(llm.ReaderError):
            llm.analyze(TEXT, [], model=llm.DEFAULT_MODEL)
        self.assertEqual(parse.call_count, 2)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "mock"})
    @patch("server.korean_analysis.OpenAI")
    def test_word_pass_retries_omissions_and_covers_each_occurrence(self, client):
        result = analysis()
        gaps = llm.missing_words(TEXT, [(4, 8), (4, 4 + len(OTHER))])
        self.assertEqual([TEXT[start:end] for start, end in gaps], ["말하려고", "했어"])
        words = [llm.WordGloss(start=start, gloss="Gloss", breakdown="", concept_refs=[0])
                 for start, _ in gaps]
        def response(data):
            return SimpleNamespace(status="completed", output_parsed=data, usage=None)
        parse = client.return_value.__enter__.return_value.responses.parse
        parse.side_effect = [response(result),
                             response(llm.WordGlosses(concepts=result.concepts, words=[words[0]] * len(words))),
                             response(llm.WordGlosses(concepts=result.concepts, words=list(reversed(words))))]
        annotated = llm.analyze(TEXT, [], model=llm.DEFAULT_MODEL)
        self.assertEqual(annotated.annotations[:2], result.annotations)
        self.assertEqual([(item.start, item.end) for item in annotated.annotations[2:]], gaps)
        self.assertTrue(all(item.concept_refs == [2] for item in annotated.annotations[2:]))
        self.assertEqual(parse.call_count, 3)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "mock"})
    @patch("server.korean_analysis.OpenAI")
    def test_practice_validates_types_and_maps_targets_from_stored_analysis(self, client):
        parse = client.return_value.__enter__.return_value.responses.parse
        def response(kinds):
            data = {key: value for key, value in exercise().items() if key not in {"kind", "concept_ids"}}
            batch = llm.PracticeBatch(exercises=[llm.Exercise(**data, kind=kind, target_refs=[0])
                                                 for kind in kinds])
            return SimpleNamespace(status="completed", output_parsed=batch, usage=None)
        kinds = ["cloze", "cloze", "transformation", "production", "production"]
        parse.side_effect = [response(["cloze"] * 5), response(kinds)]
        batch = llm.generate_practice(document(), [{"id": CONCEPT, "form": "말하다"}])
        self.assertEqual([item["kind"] for item in batch], kinds)
        self.assertTrue(all(item["concept_ids"] == [CONCEPT] for item in batch))
        self.assertIn("going to tell", parse.call_args.kwargs["input"])
        self.assertNotIn("🐈", parse.call_args.kwargs["input"])

    @patch("server.korean_analysis._structured")
    def test_cloze_accepts_listed_alternative_and_production_uses_model(self, structured):
        self.assertTrue(llm.evaluate(exercise("cloze"), "말하려고 했어요.").correct)
        structured.assert_not_called()
        llm.evaluate(exercise(), "전화를 하려고 했어요.")
        self.assertEqual(structured.call_args.args[2]["answer"], "전화를 하려고 했어요.")

    def test_rejects_empty_oversize_and_null_answers(self):
        for answer in (" ", "가" * 281, "가\x00"):
            with self.subTest(answer=answer), self.assertRaises(llm.ReaderError):
                llm.validate_answer(answer)


class StoreTests(unittest.TestCase):
    @patch("server.korean_store._cached_document", return_value={"id": DOCUMENT})
    @patch("server.korean_store._rpc")
    @patch("server.korean_analysis.analyze")
    def test_identical_cached_text_bypasses_claim_and_model(self, analyze, rpc, cached):
        self.assertEqual(store.ingest(USER, "Title", TEXT, None), DOCUMENT)
        self.assertEqual(cached.call_args.args[0], USER)
        analyze.assert_not_called()
        rpc.assert_not_called()

    @patch("server.korean_store._cached_document", return_value=None)
    @patch("server.korean_store._rpc", return_value=False)
    @patch("server.korean_analysis.analyze")
    def test_in_flight_import_does_not_call_model(self, analyze, _rpc, _cached):
        with self.assertRaisesRegex(llm.ReaderError, "already being analyzed"):
            store.ingest(USER, "Title", TEXT, None)
        analyze.assert_not_called()

    @patch("server.korean_store._cached_document", return_value=None)
    @patch("server.korean_store._rpc", return_value=True)
    @patch("server.db.get")
    @patch("server.korean_analysis.analyze", side_effect=llm.ReaderError("Unavailable"))
    def test_failure_releases_the_claim_without_saving_document(self, _analyze, database, rpc, _cached):
        database.return_value.table.return_value = MagicMock()
        with self.assertRaisesRegex(llm.ReaderError, "Unavailable"):
            store.ingest(USER, "Title", TEXT, None)
        self.assertEqual(rpc.call_count, 1)
        claim = rpc.call_args.args[1]["p_lease"]
        database.return_value.table.return_value.delete.return_value.eq.return_value.eq.assert_called_once_with(
            "lease", claim
        )

    def test_practice_prioritizes_previous_difficulty_and_recognition(self):
        annotations = document()["analysis"]["annotations"]
        concepts = {
            CONCEPT: {"id": CONCEPT, "kind": "lexical", "form": "말하다", "meaning": "tell",
                      "recognition": "known", "production": "needs_practice"},
            CONSTRUCTION: {"id": CONSTRUCTION, "kind": "construction", "form": "-려고", "meaning": "intend",
                           "recognition": "learning", "production": "unpracticed"},
        }
        targets = store.practice_targets(annotations, concepts)
        self.assertEqual([target["id"] for target in targets], [CONCEPT, CONSTRUCTION])


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-only-key", "SESSION_COOKIE_SECURE": False})
        self.client = self.app.test_client()
        self.database_role = patch("server.db.get_user_role", return_value="member")
        self.database_role.start()
        self.addCleanup(self.database_role.stop)

    def login(self):
        patcher = patch("server.auth._load_user_from_session", return_value=SimpleNamespace(
            id=USER, email="reader@example.test"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.set_csrf()

    def set_csrf(self):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "test-csrf"
        self.headers = {"X-CSRF-Token": "test-csrf"}

    def test_guest_hits_login_on_every_reader_endpoint(self):
        self.set_csrf()
        for method, path in (
            ("GET", "/korean"), ("HEAD", BASE), ("GET", BASE),
            ("POST", "/korean/documents"), ("POST", BASE + "/delete"), ("POST", BASE + "/word-glosses"),
            ("PATCH", f"/korean/knowledge/{CONCEPT}"), ("POST", BASE + "/practice"),
            ("GET", EXERCISE), ("POST", EXERCISE),
        ):
            with self.subTest(method=method, path=path):
                response = self.client.open(path, method=method, headers=self.headers)
                self.assertIn(response.status_code, (302, 303))
                self.assertIn("/auth/login/", response.location)
                self.assertIn("no-store", response.headers["Cache-Control"])

    def test_public_homepage_and_login_work(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Korean Reader", response.data)
        self.assertIn("public", response.headers["Cache-Control"])
        response = self.client.get("/auth/login/")
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.text, r'name="csrf_token" value="[^"]+"')

    def test_homepage_remains_public_without_a_configured_session_secret(self):
        self.app.config["SECRET_KEY"] = None
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/korean/").status_code, 503)

    @patch("server.db.get")
    def test_existing_login_returns_to_reader_with_supabase_session(self, database):
        identity = SimpleNamespace(id=USER, email="reader@example.test")
        database.return_value.auth.sign_in_with_password.return_value = SimpleNamespace(
            user=identity, session=SimpleNamespace(access_token="access", refresh_token="refresh"),
        )
        entry = self.client.get(BASE)
        login = self.client.get(entry.location)
        token = re.search(r'name="csrf_token" value="([^"]+)"', login.text)[1]
        response = self.client.post(entry.location, data={
            "csrf_token": token, "email": identity.email, "password": "test",
        })
        self.assertEqual(response.location, BASE)
        with self.client.session_transaction() as session:
            self.assertEqual(session["sb_user_id"], USER)
            self.assertEqual(session["sb_access_token"], "access")
        database.return_value.auth.sign_in_with_password.assert_called_once()

    @patch("server.db.get")
    def test_login_ignores_external_return_destination(self, database):
        self.set_csrf()
        database.return_value.auth.sign_in_with_password.return_value = SimpleNamespace(
            user=SimpleNamespace(id=USER, email="reader@example.test"),
            session=SimpleNamespace(access_token="access", refresh_token="refresh"),
        )
        response = self.client.post("/auth/login/?next=//example.test", headers=self.headers,
                                    data={"email": "reader@example.test", "password": "test"})
        self.assertEqual(response.location, "/")

    @patch("server.korean_store.ingest", return_value=DOCUMENT)
    def test_mutations_require_csrf_and_import_uses_session_owner(self, ingest):
        self.login()
        data = {"text": TEXT, "user_id": str(uuid4())}
        self.assertEqual(self.client.post("/korean/documents", data=data).status_code, 403)
        unicode_header = {"X-CSRF-Token": "not-a-token-é"}
        self.assertEqual(self.client.post("/korean/documents", data=data, headers=unicode_header).status_code, 403)
        result = self.client.post("/korean/documents", headers=self.headers, data=data)
        self.assertEqual(result.location, BASE)
        self.assertEqual(ingest.call_args.args[0], USER)
        self.assertEqual(ingest.call_args.args[2], TEXT)

    @patch("server.korean_store.documents", return_value=[])
    @patch("server.korean_store.ingest")
    def test_import_rejects_oversize_text_before_llm(self, ingest, _documents):
        self.login()
        result = self.client.post("/korean/documents", headers=self.headers, data={"text": "가" * 801})
        self.assertEqual(result.status_code, 422)
        self.assertIn("at most 800", result.text)
        ingest.assert_not_called()

    @patch("server.korean_store.ingest", return_value=DOCUMENT)
    def test_browser_import_preserves_original_line_endings(self, ingest):
        self.login()
        text = "\n가려고 해.\n그래도 못 했어.\r\n"
        result = self.client.post("/korean/documents", headers=self.headers, data={"text_json": json.dumps(text)})
        self.assertEqual(result.location, BASE)
        self.assertEqual(ingest.call_args.args[2], text)

    @patch("server.korean_store.document", return_value=None)
    @patch("server.korean_store.delete_document", return_value=False)
    @patch("server.korean_analysis.generate_practice")
    def test_missing_or_foreign_documents_cannot_be_accessed_deleted_or_practiced(self, generate, delete, lookup):
        self.login()
        self.assertEqual(self.client.get(BASE).status_code, 404)
        self.assertEqual(self.client.post(BASE + "/practice", headers=self.headers).status_code, 404)
        self.assertEqual(self.client.post(BASE + "/word-glosses", headers=self.headers).status_code, 404)
        self.assertEqual(self.client.post(BASE + "/delete", headers=self.headers).status_code, 404)
        lookup.assert_called_with(USER, DOCUMENT)
        delete.assert_called_with(USER, DOCUMENT)
        generate.assert_not_called()

    @patch("server.korean_store.document", return_value=document())
    @patch("server.korean_store.add_word_glosses")
    def test_gap_fill_runs_only_for_signed_in_owner_with_csrf(self, fill, lookup):
        self.login()
        self.assertEqual(self.client.post(BASE + "/word-glosses").status_code, 403)
        fill.assert_not_called()
        result = self.client.post(BASE + "/word-glosses", headers=self.headers)
        self.assertEqual(result.location, BASE)
        lookup.assert_called_once_with(USER, DOCUMENT)
        fill.assert_called_once_with(USER, document())

    @patch("server.korean_store.set_recognition", return_value=True)
    def test_knowledge_updates_scope_and_validate_state(self, update):
        self.login()
        path = f"/korean/knowledge/{CONCEPT}"
        self.assertEqual(self.client.patch(path, headers=self.headers, json={"recognition": False}).status_code, 400)
        update.assert_not_called()
        result = self.client.patch(path, headers=self.headers, json={"recognition": "known", "user_id": "other"})
        self.assertEqual(result.json, {"recognition": "known"})
        update.assert_called_once_with(USER, CONCEPT, "known")

    @patch("server.korean_store.document", return_value=document())
    @patch("server.korean_store.concept_details", return_value={CONCEPT: {"recognition": "known"},
                                                                 CONSTRUCTION: {"recognition": "learning"}})
    def test_reader_keeps_other_unknown_construction_and_does_not_reanalyze(self, _concepts, _document):
        self.login()
        with patch("server.korean_analysis.analyze") as analyze:
            result = self.client.get(BASE)
        self.assertEqual(result.status_code, 200)
        self.assertIn('class="reader-span is-unknown"', result.text)
        self.assertIn('data-annotations="0,1"', result.text)
        self.assertIn("&#13;\n", result.text)
        analyze.assert_not_called()

    @patch("server.korean_store.practice", return_value={"exercises": [exercise()] * 5})
    @patch("server.korean_store.attempts", return_value={})
    @patch("server.korean_store.record_attempt")
    @patch("server.korean_analysis.evaluate", return_value=llm.Feedback(correct=True, feedback="Good."))
    def test_exercise_requires_owned_session_and_hides_constraints(self, evaluate, record, attempts, practice):
        self.login()
        result = self.client.get(EXERCISE)
        self.assertIn("Use -려고 하다.", result.text)
        self.assertNotIn("Include the intention construction.", result.text)
        self.assertNotIn("말하려고 했어요", result.text)
        self.assertEqual(self.client.get(EXERCISE[:-1] + "1").status_code, 404)
        self.assertEqual(self.client.post(EXERCISE, headers=self.headers, data={"answer": " "}).status_code, 422)
        evaluate.assert_not_called()
        result = self.client.post(EXERCISE, headers=self.headers, data={"answer": "가려고 했어요."})
        self.assertEqual(result.location, EXERCISE)
        practice.assert_called_with(USER, PRACTICE, DOCUMENT)
        record.assert_called_once_with(PRACTICE, 0, "가려고 했어요.", {"correct": True, "feedback": "Good."})
        attempts.return_value = {0: {"answer": "가려고 했어요.", "result": {"correct": True, "feedback": "Good."}}}
        self.assertIn("Next exercise", self.client.get(EXERCISE).text)
        self.client.post(EXERCISE, headers=self.headers, data={"answer": "Another answer"})
        evaluate.assert_called_once()


if __name__ == "__main__":
    unittest.main()

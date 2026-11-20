# Hi! I'm Noah

I am a third-year at Purdue University studying computer science with a concentration in machine intelligence and a minor in mathematics. I am broadly interested in compilers, machine learning, and markets.

[https://ntrupin.com](https://ntrupin.com).

## Korean Reader

Open `/korean/` and sign in with an existing Supabase account. The reader accepts passages up to 800 Unicode code points. An identical passage from the same account opens its saved analysis when the analysis version and model match. Deleting a passage also deletes its practice sessions and attempts. Concept knowledge carries over to other passages.

New analyses retain phrase-level explanations and fill gaps where Korean words are left uncovered. On an older passage, use **Manage passage → Fill annotation gaps** to add missing explanations to the saved passage.

### Local setup and deployment

1. Apply the Korean Reader migrations in `supabase/migrations/` in filename order to the intended Supabase project. Use the SQL Editor or your usual migration workflow.
2. Keep the site's existing `SECRET_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_KEY` in `.env` locally or environment variables on Vercel. Add `OPENAI_API_KEY` in the same environment. `KOREAN_LLM_MODEL` optionally overrides the `gpt-6-luna` default.
3. Locally, install `requirements.txt`, run `flask --app noah run --debug`, and open `http://127.0.0.1:5000/korean/`. The Vercel configuration enables Fluid Compute so synchronous model requests have time to finish.

### Verification

Run `python -m unittest discover -s tests` for mocked tests. Run `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/korean_reader.sql` against a disposable Supabase database after applying the migration to verify row-level security and persistence.

Run `python -m scripts.evaluate_korean --list` to see the curated cases. With `OPENAI_API_KEY` set, run `python -m scripts.evaluate_korean intention-and-inability` to review one case, or omit the case to evaluate all passages. Live evaluation incurs API usage. Review the contextual glosses, analysis of ambiguous constructions, and any missed annotations. Concept reuse depends on matching forms, aliases, and senses, so inconsistent model labels can still produce duplicates.

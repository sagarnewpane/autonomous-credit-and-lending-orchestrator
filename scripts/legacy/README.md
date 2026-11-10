# Hackathon-era scripts

Development scripts from the GIBL AI/ML Hackathon 2026 version. They are kept for reference
and are not maintained or tested.

- The database scripts (`clear_and_reload_db.py`, `load_large_tables.py`,
  `migrate_to_supabase.py`, `populate_config.py`, `explore_db.py`, `verify_pipeline_tables.py`)
  import a `supabase` client that no longer exists in `app/db` and expect a `cleaned_db/`
  folder that is not part of the repository.
- The OCR scripts (`test_ocr.py`, `test_ocr_chandra.py`, `test_all_docs.py`) need Tesseract,
  Ollama and sample document images, which are not distributed.
- `test_apply.py` and `test_apply_endpoint.py` post to a running server and predate the
  current loan form; `tests/test_api_offline.py` replaces them.
- `tests/` holds the hackathon test files, which need PostgreSQL and Ollama. The OCR output they
  wrote (`parser_agent_output.json`) was removed because it held identity-document fields.

Use `scripts/run_offline.py`, `experiments/run_all.py` and `pytest` instead (see the main
README).

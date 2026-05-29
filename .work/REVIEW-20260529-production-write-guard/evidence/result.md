# REVIEW-20260529-production-write-guard Evidence

## Result
- status: PASS
- fixed:
  - `scripts/verify_pipeline_refactor.py` now validates `universe.parquet` exists, is non-empty, has non-zero valid `stock_id` count, has `date`, and has a valid latest date.
  - `scripts/verify_production_write_guard.py` now blocks `ETLPipeline(data_dir=<variable or unknown source>)` in verify scripts unless the static analyzer can prove the value is a non-production temp/test path.

## Verification
- PASS: `uv run --with-requirements requirements.txt python -m py_compile scripts/verify_pipeline_refactor.py scripts/verify_production_write_guard.py app/pipeline/orchestrator.py`
- PASS: `uv run --with-requirements requirements.txt python scripts/verify_production_write_guard.py`
  - output: `PRODUCTION_WRITE_GUARD_OK`
- PASS: `uv run --with-requirements requirements.txt python scripts/verify_pipeline_refactor.py`
  - universe check: `rows=73243 stocks=1183 latest_date=2026-05-29`
  - output directory was a tempfile path under `new-top10-pipeline-verify-*`, not production `data/clean`.
- PASS: `uv run --with-requirements requirements.txt python scripts/verify_model_group_acceptance.py`
  - output: `MODEL_GROUP_ACCEPTANCE_OK health=WARN auto_retrain=BLOCKED output=artifacts/model_group_acceptance_2026-05-29.json`
- PASS: `uv run --with-requirements requirements.txt python -m app.pipeline_cli validate --json`
  - output: `ok=true`, `ERROR=0`, `WARN=5`
- PASS: `git diff --check`
- PASS: `bash ~/ai-core/scripts/codegraph.sh index`
  - indexed 198 files, 2826 nodes, 2614 edges

## Notes
- `verify_pipeline_refactor.py` emitted TWSE warnings for several dates with no valid quote table, but the ETL completed and the universe artifact passed the non-empty/date checks.
- Production `data/clean` was not modified in git status after the pipeline refactor verification.

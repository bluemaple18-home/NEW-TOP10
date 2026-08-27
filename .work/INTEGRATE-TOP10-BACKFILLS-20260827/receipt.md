# INTEGRATE-TOP10-BACKFILLS-20260827

## Scope
- Base: `main` HEAD `9d313e6e96fb3badd74e4be1ef06d1dd2f53e51d`.
- Integration branch: `codex/integrate-top10-backfills-20260827`.
- Worktree: `<integration-worktree>`.
- Ordered inputs:
  1. `f17bd6e10a2a4737a9b3faf993e0d78c36218f0f`
  2. `998f26fe1cc3d30f374828f1383b2d8c235890f0..0fb28cb8a7a6a17b30067e2704e4ef67bb76a2bd`

## Boundaries
- Do not modify `<main-checkout>` main checkout.
- Do not push, deploy, send external review traffic, or touch launchd.
- Stop on cherry-pick conflicts instead of guessing.
- Keep runtime artifacts, production `artifacts/external_review`, ranking outputs, and scheduler changes out of the tracked tree.

## Acceptance
- Preserve or make traceable the ordered input commits.
- Run affected daily isolated backfill and external review provider/backfill tests.
- Run shell syntax checks for affected shell scripts.
- Run full available verification, using original artifact roots read-only only if required.
- Run `git diff --check`.
- Report branch tip, commit sequence, test results, tree artifact safety checks, and merge-ready verdict.

## Repair revalidation
- Reviewer P1 repair scope:
  - `scripts/isolated_external_review_backfill.py` no longer carries hardcoded ChatGPT/Gemini exact markers or the account email; prepare requires CLI/env provider markers and fails closed when missing.
  - New external review evidence redacts exact provider URLs and keeps only non-sensitive canonical target descriptions.
  - Daily evidence keeps only `docs/evidence/CARD-NEW-TOP10-ISOLATED-DAILY-BACKFILL-20260827/sanitized_receipt.md`; raw manifest, capacity, launchd and formal-baseline machine-local evidence files were removed from tracked tree.
  - `scripts/run_isolated_daily_backfill.py` now writes raw runtime evidence to `output_root/evidence` by default. Repo docs receive a sanitized receipt only when `--sanitized-receipt-path` is explicitly supplied and constrained to the card evidence directory.
  - `scripts/run_isolated_daily_backfill.py` no longer serializes `rm -rf <absolute path>`; rollback is textual guidance scoped to the isolated output root.
- Scope correction: formal provider scripts were restored to the integrated candidate state and were not changed by this repair.
- Tests:
  - `PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -m pytest -q tests/test_isolated_daily_backfill.py` → 6 passed.
  - `PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -m pytest -q tests/test_isolated_external_review_backfill.py tests/test_external_review_provider_preflight.py` → 18 passed.
  - `PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -m pytest -q tests/test_external_review_api_provider.py` → 5 passed.
- Read-only runtime artifact verification:
  - External isolated backfill original artifact root with `--require-complete` → PASS, 36 slots.
  - Daily isolated backfill original manifest summary → `DELIVERED_CANDIDATE`, 18 completed, 6 skipped, capacity PASS, formal baseline PASS.
- Shell syntax:
  - `bash -n scripts/review_chatgpt_chrome.sh` → PASS.
  - `bash -n scripts/review_gemini_chrome.sh` → PASS.
  - `bash -n scripts/run_external_review_provider_preflight.sh` → PASS.
  - `bash -n scripts/run_external_review_host_runner.sh` → PASS.
- Secret/path scan over repair-owned files: no email, exact provider ids/URLs, destructive absolute rollback command, or machine-local absolute paths found.
- Tracked-tree boundary:
  - Largest tracked file remains under 3 MB; no 95 MB runtime artifact is tracked.
  - No tracked `artifacts/external_review`, `artifacts/isolated_daily_backfill`, `artifacts/isolated_external_review_backfill`, or ranking CSV artifacts.

# REPAIR-NEW-TOP10-EXTERNAL-REVIEW-DOM-COLLECTOR-20260827 Receipt

## Status

`DELIVERED_CANDIDATE`

## Candidate commits

- `4202f11` - Add DOM collector repair card
- `f0fba33` - Repair ChatGPT review DOM collector
- `4f98558` - Wait for stable ChatGPT review collection

## Repair result

- Root cause was corrected from provider response absence to ChatGPT collector retrieval bug.
- `2026-08-03:chatgpt` was recovered read-only from the existing ChatGPT page; no ChatGPT resend was performed for that slot.
- ChatGPT collector now anchors on the correlated user prompt markers and rejects stale TSKG, prefix-only, uncorrelated, or still-generating responses.
- ChatGPT collector waits for two stable correlated snapshots before accepting raw response.

## Backfill result

- Ledger: `artifacts/isolated_external_review_backfill/2026-08-03_2026-08-26/ledger.json`
- Completion manifest: `artifacts/isolated_external_review_backfill/2026-08-03_2026-08-26/manifest/completion_manifest.json`
- Status counts: `OK=36`
- Provider counts: `chatgpt=18`, `gemini=18`
- Isolated normalized responses: `36`
- Final `next-slot`: `COMPLETE`

## Verification

- `bash -n scripts/review_chatgpt_chrome.sh` PASS
- `.venv/bin/python -m pytest -q tests/test_external_review_provider_preflight.py tests/test_isolated_external_review_backfill.py` PASS, 17 tests
- `.venv/bin/python scripts/isolated_external_review_backfill.py verify --require-complete --output-root artifacts/isolated_external_review_backfill/2026-08-03_2026-08-26` PASS
- `git diff --check` PASS

## Formal path evidence

- `artifacts/external_review` exists as an empty directory.
- File count under `artifacts/external_review` is `0`.
- All review outputs were written under `artifacts/isolated_external_review_backfill/2026-08-03_2026-08-26/`.

## External write discipline

- Every ledger slot has `attempt_count=1`.
- No merge, push, deploy, scheduler change, ranking change, or formal external-review artifact write was performed.

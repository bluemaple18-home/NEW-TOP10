# POST-DAILY-EXTERNAL-REVIEW-03｜Gemini Collector

## Goal

Build a Gemini collector with the same raw-response storage, local normalization, and `external-review.v1` boundary as ChatGPT.

## Dependencies

- `POST-DAILY-EXTERNAL-REVIEW-01` completed.
- `docs/architecture/EXTERNAL_REVIEW_CONTRACT.md`.
- `scripts/normalize_external_review_response.py`.
- `scripts/verify_external_review_contract.py`.

## Required Output

```text
artifacts/external_review/YYYY-MM-DD/gemini_response_YYYY-MM-DD.json
artifacts/external_review/YYYY-MM-DD/gemini_raw_YYYY-MM-DD.txt
```

## Implementation Options

Prefer the safest available local path:

- Browser JS harness if Gemini web UI is logged in and stable.
- Existing local Gemini / ai-core env integration only if it does not require committing secrets and still respects the packet boundary.

## Required Behavior

- Use the same review packet produced by `POST-DAILY-EXTERNAL-REVIEW-01`.
- Include the same boundary text as ChatGPT.
- In multi-browser / multi-account setups, require an exact Gemini conversation URL marker, not the broad `gemini.google.com/app` marker.
- Before send or collect, verify visible guards such as expected conversation title, account label, and plan label.
- Store raw response first, then normalize with `scripts/normalize_external_review_response.py`.
- Validate normalized output with `scripts/verify_external_review_contract.py`.
- Provider field must be `gemini`.
- If raw response is sparse or malformed, normalizer may emit a low-confidence `needs_human_review=true` artifact; it must not fabricate algorithm claims or promotion readiness.

## Out Of Scope

- Do not merge reviewer outputs.
- Do not change ranking/model/report/publish artifacts.
- Do not commit API keys or browser/session secrets.

## Acceptance

```bash
TOP10_GEMINI_URL_PART=gemini.google.com/app/<conversation-id> TOP10_GEMINI_EXPECTED_TITLE=盤後選股檢討報告 TOP10_GEMINI_EXPECTED_ACCOUNT="風17 一年" TOP10_GEMINI_EXPECTED_PLAN=Pro bash scripts/review_gemini_chrome.sh probe
.venv/bin/python scripts/normalize_external_review_response.py --provider gemini --date 2026-06-08 --raw artifacts/external_review/2026-06-08/gemini_raw_2026-06-08.txt --packet artifacts/external_review/2026-06-08/review_packet_2026-06-08.json --out artifacts/external_review/2026-06-08/gemini_response_2026-06-08.json
.venv/bin/python scripts/verify_external_review_contract.py artifacts/external_review/2026-06-08/gemini_response_2026-06-08.json
.venv/bin/python -m py_compile <new_gemini_collector_script>
git diff --check
```

## Evidence

- `artifacts/external_review/2026-06-08/gemini_response_2026-06-08.json`
- `artifacts/external_review/2026-06-08/gemini_raw_2026-06-08.txt`

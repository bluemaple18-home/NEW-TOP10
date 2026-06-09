# POST-DAILY-EXTERNAL-REVIEW-02｜ChatGPT Collector

## Goal

Use the existing Chrome Apple Events harness to submit a safe `review_packet` to the `ChatGPT - 股票` tab, store the raw review, and normalize it into a valid `external-review.v1` JSON response.

## Dependencies

- `POST-DAILY-EXTERNAL-REVIEW-01` completed.
- `docs/architecture/EXTERNAL_REVIEW_CONTRACT.md`.
- `scripts/review_chatgpt_chrome.sh`.
- `scripts/normalize_external_review_response.py`.
- `scripts/verify_external_review_contract.py`.

## Required Output

```text
artifacts/external_review/YYYY-MM-DD/chatgpt_response_YYYY-MM-DD.json
artifacts/external_review/YYYY-MM-DD/chatgpt_raw_YYYY-MM-DD.txt
```

## Required Behavior

- Build prompt from the safe packet only.
- Before sending, validate the exact `--packet` payload with `scripts/verify_external_review_packet.py`; never send `review_packet_manifest_YYYY-MM-DD.json`.
- Include the boundary text from `EXTERNAL_REVIEW_CONTRACT.md`.
- Reviewer may answer freely, but prompt must request the required review information.
- Store raw response first, then run `scripts/normalize_external_review_response.py`.
- Parsed/normalized JSON must pass `scripts/verify_external_review_contract.py`.
- If raw response is sparse or malformed, normalizer may emit a low-confidence `needs_human_review=true` artifact; it must not fabricate algorithm claims or promotion readiness.

## Out Of Scope

- Do not call Gemini.
- Do not merge reviewer outputs.
- Do not change ranking/model/report/publish artifacts.
- Do not send internal algorithms, weights, feature structures, or source code.

## Acceptance

```bash
bash scripts/review_chatgpt_chrome.sh --date 2026-06-08 --packet artifacts/external_review/2026-06-08/review_packet_2026-06-08.json
.venv/bin/python scripts/normalize_external_review_response.py --provider chatgpt --date 2026-06-08 --raw artifacts/external_review/2026-06-08/chatgpt_raw_2026-06-08.txt --packet artifacts/external_review/2026-06-08/review_packet_2026-06-08.json --out artifacts/external_review/2026-06-08/chatgpt_response_2026-06-08.json
.venv/bin/python scripts/verify_external_review_contract.py artifacts/external_review/2026-06-08/chatgpt_response_2026-06-08.json
git diff --check
```

## Evidence

- `artifacts/external_review/2026-06-08/chatgpt_response_2026-06-08.json`
- `artifacts/external_review/2026-06-08/chatgpt_raw_2026-06-08.txt`

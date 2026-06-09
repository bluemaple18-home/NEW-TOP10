# POST-DAILY-EXTERNAL-REVIEW-01｜Review Packet And Storage

## Goal

Create a safe daily `review_packet` from existing public-facing artifacts and store all external review artifacts under `artifacts/external_review/YYYY-MM-DD/`.

## Inputs

- `artifacts/ranking_YYYY-MM-DD.csv`
- `artifacts/daily_report_YYYY-MM-DD.json`
- `artifacts/daily_report_YYYY-MM-DD.md`
- Optional: `artifacts/clawd_publish_payload_YYYY-MM-DD.json`
- Optional: public OHLC / forward outcome fields already present in local features

## Required Output

```text
artifacts/external_review/YYYY-MM-DD/review_packet_YYYY-MM-DD.json
artifacts/external_review/YYYY-MM-DD/review_packet_YYYY-MM-DD.md
```

## Packet Rules

Packet may include:

- stock_id / stock_name
- rank / bucket / publish section
- public-facing reasons
- industry / concept labels
- public OHLC summary
- observed next-day or same-day outcome when available
- market overview from daily report

Packet must not include:

- model feature names not already exposed publicly
- SHAP internals beyond public reason text
- model weights
- hidden scoring formula
- training labels
- source code snippets
- promotion gate internals

## Implementation Scope

- Add `scripts/build_external_review_packet.py`.
- Add `scripts/verify_external_review_packet.py`.
- Do not call ChatGPT / Gemini in this slice.

## Acceptance

```bash
.venv/bin/python scripts/build_external_review_packet.py --date 2026-06-08
.venv/bin/python scripts/verify_external_review_packet.py --packet artifacts/external_review/2026-06-08/review_packet_2026-06-08.json
.venv/bin/python -m py_compile scripts/build_external_review_packet.py scripts/verify_external_review_packet.py
git diff --check
```

## Evidence

- `artifacts/external_review/2026-06-08/review_packet_2026-06-08.json`
- `artifacts/external_review/2026-06-08/review_packet_2026-06-08.md`

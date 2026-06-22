# POST-DAILY-EXTERNAL-REVIEW-06｜Host Runner Clawd / Harness

## Goal

Make post-daily external review run every trading day after daily ranking finishes, without depending on Codex to perform the external ChatGPT / Gemini disclosure step.

## Positioning

This is a host-owned automation runner. Codex remains responsible for safe packet generation, local validation, normalization, merge, and verification. Clawd / harness owns browser submission to ChatGPT and Gemini using local logged-in sessions and operator-approved export policy.

## Dependencies

- `POST-DAILY-EXTERNAL-REVIEW-01` through `04` completed.
- Daily run has produced same-date artifacts:
  - `artifacts/ranking_YYYY-MM-DD.csv`
  - `artifacts/daily_report_YYYY-MM-DD.json`
  - `artifacts/market_context_YYYY-MM-DD.json`
- Browser sessions are available:
  - ChatGPT project/tab logged in to the intended account.
  - Gemini tab logged in to `風17 一年 / bluemaple17`.

## Required Behavior

Host runner sequence:

1. Wait for same-date daily status `OK`.
2. Run:
   ```bash
   .venv/bin/python scripts/build_external_review_packet.py --date YYYY-MM-DD
   .venv/bin/python scripts/verify_external_review_packet.py --packet artifacts/external_review/YYYY-MM-DD/review_packet_YYYY-MM-DD.json
   ```
3. Refuse to send `review_packet_manifest_YYYY-MM-DD.json`.
4. Submit only `review_packet_YYYY-MM-DD.json` / generated prompt to ChatGPT and Gemini.
5. Store raw responses first:
   ```text
   artifacts/external_review/YYYY-MM-DD/chatgpt_raw_YYYY-MM-DD.txt
   artifacts/external_review/YYYY-MM-DD/gemini_raw_YYYY-MM-DD.txt
   ```
6. Normalize and verify:
   ```bash
   .venv/bin/python scripts/normalize_external_review_response.py --provider chatgpt --date YYYY-MM-DD --raw artifacts/external_review/YYYY-MM-DD/chatgpt_raw_YYYY-MM-DD.txt --packet artifacts/external_review/YYYY-MM-DD/review_packet_YYYY-MM-DD.json --out artifacts/external_review/YYYY-MM-DD/chatgpt_response_YYYY-MM-DD.json
   .venv/bin/python scripts/normalize_external_review_response.py --provider gemini --date YYYY-MM-DD --raw artifacts/external_review/YYYY-MM-DD/gemini_raw_YYYY-MM-DD.txt --packet artifacts/external_review/YYYY-MM-DD/review_packet_YYYY-MM-DD.json --out artifacts/external_review/YYYY-MM-DD/gemini_response_YYYY-MM-DD.json
   .venv/bin/python scripts/verify_external_review_contract.py artifacts/external_review/YYYY-MM-DD/chatgpt_response_YYYY-MM-DD.json
   .venv/bin/python scripts/verify_external_review_contract.py artifacts/external_review/YYYY-MM-DD/gemini_response_YYYY-MM-DD.json
   ```
7. Build and verify summary:
   ```bash
   .venv/bin/python scripts/build_external_review_summary.py --date YYYY-MM-DD
   .venv/bin/python scripts/verify_external_review_summary.py --summary artifacts/external_review/YYYY-MM-DD/external_review_summary_YYYY-MM-DD.json
   ```

## Host Runner Options

Option A: Clawd task

- Create a Clawd project task named `POST-DAILY-EXTERNAL-REVIEW-HOST-RUNNER`.
- Trigger after `scripts/run_daily_publish.sh` succeeds or by launchd 10-20 minutes after daily schedule.
- Use existing Chrome profile sessions, not Codex browser execution.
- Write status artifact:
  ```text
  artifacts/external_review/YYYY-MM-DD/host_runner_status_YYYY-MM-DD.json
  ```

Option B: Harness adapter

- Add a local harness job that receives `{date, packet_path, chatgpt_target, gemini_target}`.
- Harness performs browser submission and returns raw text only.
- Repo scripts perform normalization and merge after raw text lands.

## Catch-up Mode

Historical catch-up must not depend on the current `artifacts/automation_status.json`,
because that file is overwritten by later daily or non-trading-day runs.

For catch-up, runner may use:

```bash
.venv/bin/python scripts/run_external_review_host_runner.py \
  --date YYYY-MM-DD \
  --allow-existing-daily-artifacts \
  --skip-provider-submit
```

This mode is allowed only when same-date daily artifacts exist:

```text
artifacts/ranking_YYYY-MM-DD.csv
artifacts/daily_report_YYYY-MM-DD.json
artifacts/market_context_YYYY-MM-DD.json
```

The runner must record:

```text
daily_status_source: existing_daily_artifacts
daily_artifact_gate.status: OK
```

This does not weaken the normal daily schedule path: without
`--allow-existing-daily-artifacts`, same-date `automation_status.json == OK` is still
required.

## Required Status Fields

```json
{
  "schema_version": "external-review-host-runner-status.v1",
  "run_date": "YYYY-MM-DD",
  "status": "OK|PARTIAL|FAILED|SKIPPED",
  "daily_status_ok": true,
  "packet_verified": true,
  "chatgpt": {
    "status": "OK|FAILED|SKIPPED",
    "target": "chatgpt project or conversation marker",
    "raw_path": "artifacts/external_review/YYYY-MM-DD/chatgpt_raw_YYYY-MM-DD.txt",
    "response_path": "artifacts/external_review/YYYY-MM-DD/chatgpt_response_YYYY-MM-DD.json"
  },
  "gemini": {
    "status": "OK|FAILED|SKIPPED",
    "target": "gemini conversation marker",
    "expected_account": "風17 一年 / bluemaple17",
    "raw_path": "artifacts/external_review/YYYY-MM-DD/gemini_raw_YYYY-MM-DD.txt",
    "response_path": "artifacts/external_review/YYYY-MM-DD/gemini_response_YYYY-MM-DD.json"
  },
  "summary_path": "artifacts/external_review/YYYY-MM-DD/external_review_summary_YYYY-MM-DD.json",
  "notes": []
}
```

## Safety Boundaries

- Send only verified `review_packet_YYYY-MM-DD.json` content.
- Never send manifest lineage, local paths, model paths, feature paths, source code, weights, hidden feature names, promotion gates, or training data structure.
- If one reviewer fails, produce partial summary with `single_reviewer_only=true` and `needs_human_review=true`.
- External review output remains research-only and must not alter ranking/model/publish behavior.
- No `PROMOTION_READY`, no auto model changes, no Clawd recommendation message rewrite from external reviewer output.

## Acceptance

```bash
.venv/bin/python scripts/build_external_review_packet.py --date YYYY-MM-DD
.venv/bin/python scripts/verify_external_review_packet.py --packet artifacts/external_review/YYYY-MM-DD/review_packet_YYYY-MM-DD.json
.venv/bin/python scripts/verify_external_review_contract.py artifacts/external_review/YYYY-MM-DD/chatgpt_response_YYYY-MM-DD.json
.venv/bin/python scripts/verify_external_review_contract.py artifacts/external_review/YYYY-MM-DD/gemini_response_YYYY-MM-DD.json
.venv/bin/python scripts/build_external_review_summary.py --date YYYY-MM-DD
.venv/bin/python scripts/verify_external_review_summary.py --summary artifacts/external_review/YYYY-MM-DD/external_review_summary_YYYY-MM-DD.json
.venv/bin/python scripts/verify_external_review_host_runner.py --status artifacts/host_runner/YYYY-MM-DD/host_runner_status_YYYY-MM-DD.json --summary artifacts/host_runner/YYYY-MM-DD/host_runner_summary_YYYY-MM-DD.json --require-success
git diff --check
```

## Evidence

- `artifacts/host_runner/YYYY-MM-DD/host_runner_status_YYYY-MM-DD.json`
- `artifacts/host_runner/YYYY-MM-DD/host_runner_summary_YYYY-MM-DD.json`
- `artifacts/external_review/YYYY-MM-DD/chatgpt_response_YYYY-MM-DD.json`
- `artifacts/external_review/YYYY-MM-DD/gemini_response_YYYY-MM-DD.json`
- `artifacts/external_review/YYYY-MM-DD/external_review_summary_YYYY-MM-DD.json`

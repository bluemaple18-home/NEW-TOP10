# S2 formal-entry capability audit — Issue #10 production recovery

Date: 2026-08-29  
Scope: static/read-only audit of formal production entry capability  
Decision: `BLOCK_SCOPE_EXPANSION / CANARY_PATH_NOT_APPLICABLE_WITHOUT_NEW_SUBSYSTEM`  
Status: `S2_AUDITED_BLOCK_SCOPE`  

## Root question

Can Issue #10 proceed by satisfying the global production canary readiness gate exactly as written: create → run → select → publish → transaction → tag → push?

Answer: no. The existing NEW-TOP10 production daily path does not expose official production entrypoints or correlation artifacts for `transaction`, `tag`, and `push`. Filling the seven-step receipt with narrative artifacts would forge PASS evidence, so the existing blocked receipt must remain `BLOCKED` with `canary_created=false`.

## Hard facts

- Official daily chain is `com.new-top10.daily.plist → scripts/run_with_storage_guard.sh daily → scripts/run_daily_publish.sh → scripts/run_daily.sh → python -m scripts.run_automation daily`.
  - `scripts/com.new-top10.daily.plist:14` points at `scripts/run_daily_publish.sh`.
  - `scripts/run_daily_publish.sh:41-43` calls `scripts/run_daily.sh` and captures its exit code.
  - `scripts/run_daily.sh:89-91` invokes `-m scripts.run_automation daily`.
  - `scripts/run_automation.py:276-313` routes mode `daily` to `_run_daily()` and then `_run_daily_final_artifacts()` when status remains OK.
- Official daily core is ETL / validate / rank / report / publish-ready / optional send, not seven-step canary.
  - `app/automation/daily_orchestrator.py:42-75` runs daily domain actions including preflight, ETL, validation, ranking, postchecks, and shadow/reporting side effects.
  - `app/automation/daily_orchestrator.py:78-83` produces final report and Clawd payload.
  - `scripts/run_automation.py:1025-1063` writes publish-ready payload/message artifacts through `clawd.payload`.
- `app/contracts/daily_v2.py` is a fixed five-step shadow contract:
  - `app/contracts/daily_v2.py:15-23` defines `etl`, `validate`, `rank`, `report`, `publish-ready`.
  - `app/contracts/daily_v2.py:25` makes those the required daily steps.
  - `app/workflows/daily_v2.py:294-314` validates those five outputs and requires publish-ready to be `shadow_only=true`, `send_enabled=false`, and `publish_ready=true`.
- `app/automation/daily_contract.py` production map is also five-step:
  - `app/automation/daily_contract.py:6-13` maps production core to `etl`, `validate`, `rank`, `report`, `publish-ready`.
  - `app/automation/daily_contract.py:17-27` makes production-equivalent attestation fail closed by returning `False`.
- `scripts/run_daily_publish.sh` contains send guards, but send is optional and separate from canary `transaction/tag/push`.
  - `scripts/run_daily_publish.sh:70-91` requires `automation_status.json`, exact `run_date`, `metadata.clawd_publish_message`, and notify flags before send is allowed.
  - `scripts/run_daily_publish.sh:98-107` records skipped publish when live send is not allowed.
  - `scripts/run_daily_publish.sh:110-143` only sends after the guards and fails loud if send command fails.
- There is no official production entrypoint/correlation artifact for generic `transaction`, `tag`, or `push`. The global gate requires all seven exact steps and does not allow N/A, so the existing production canary receipt must stay blocked.

## Agentic workflow audit

### 檢查 1 — Task 邊界: `PARTIAL`

Evidence:

- The production daily path is still a monolithic run from `com.new-top10.daily.plist` through `scripts/run_with_storage_guard.sh daily`, `run_daily_publish.sh`, and `run_daily.sh` into `python -m scripts.run_automation daily` (`scripts/run_daily_publish.sh:41-43`, `scripts/run_daily.sh:89-91`, `scripts/run_automation.py:276-313`).
- Daily v2 shadow steps are locatable and fixed: `etl`, `validate`, `rank`, `report`, `publish-ready` (`app/contracts/daily_v2.py:15-25`).

Gap:

- The production path does not isolate global canary seven steps. It can locate daily core stages, but cannot extract official production `transaction`, `tag`, or `push` steps.

Repair suggestion:

- Do not force seven-step canary over the existing production daily path. Either create a new subsystem with real seven-step semantics under separate Owner authorization, or use an Issue #10-specific one-shot evidence-only recovery gate over the existing daily entry.

### 檢查 2 — Input / Output 契約: `PARTIAL`

Evidence:

- `run_daily_publish.sh` gates send on `artifacts/automation_status.json` and `metadata.clawd_publish_message` (`scripts/run_daily_publish.sh:70-91`).
- `run_automation.py` records expected and actual Clawd payload/message artifacts (`scripts/run_automation.py:1025-1063`).
- daily_v2 validates five output artifacts (`app/workflows/daily_v2.py:294-314`).

Gap:

- Existing artifacts do not carry seven-step canary correlation across create/run/select/publish/transaction/tag/push.

Repair suggestion:

- For Issue #10, preserve existing artifact contracts and build one-shot storage-guard evidence around them. Do not label those artifacts as seven-step canary PASS.

### 檢查 3 — 可程式化成功標準: `PARTIAL`

Evidence:

- Daily v2 has deterministic validators for five steps (`app/workflows/daily_v2.py:294-314`).
- Storage guard and S1 receipts provide deterministic gate evidence for resource safety.
- `verify_daily_publish_workflow.py:101-121` statically verifies daily publish wrapper guards.

Gap:

- There is no deterministic validator for generic canary `transaction`, `tag`, and `push` in the official production daily path.

Repair suggestion:

- Keep global canary gate blocked for this path. If production recovery still needs to proceed, define a smaller Issue #10 gate that matches actual daily semantics: storage guard → daily core → artifacts → send-disabled receipt.

### 檢查 4 — 獨立 SOP / Skill 規範: `PASS/PARTIAL`

Evidence:

- Existing operation docs, storage guard policy, daily wrapper checks, and recovery execution card provide separable instructions and checkpoints.
- S0/S1 evidence files are independent artifacts under `.work/CARD-NEW-TOP10-ISSUE10-PRODUCTION-RECOVERY-20260829/`.

Gap:

- There is no independent SOP for seven-step production canary semantics in this repository.

Repair suggestion:

- Treat Issue #10 recovery SOP as a production recovery path, not as canary readiness, unless a new canary subsystem is explicitly authorized.

### 檢查 5 — 控制流歸屬: `PASS`

Evidence:

- `scripts/run_daily_publish.sh:41-43` deterministically runs `scripts/run_daily.sh`.
- `scripts/run_daily.sh:89-91` deterministically invokes `scripts.run_automation daily`.
- `scripts/run_automation.py:276-313` routes daily mode to daily orchestration and final artifacts.
- `app/automation/daily_orchestrator.py:42-83` owns daily ordering in code.

Gap:

- None for the existing daily path. The gap is semantic mismatch with the external seven-step canary gate, not uncontrolled flow.

Repair suggestion:

- Reuse this deterministic control flow for Issue #10 one-shot evidence-only recovery if Owner re-arbitrates away from the canary path.

### 檢查 6 — 失敗處理與回退: `PARTIAL`

Evidence:

- `run_daily_publish.sh:46-57` skips Clawd send if daily fails.
- `run_daily_publish.sh:98-107` records skipped send when live send is not allowed.
- `run_daily_publish.sh:130-143` fails the wrapper if send command fails.
- Storage guard fail-closed behavior is already evidenced by Issue #10 S0/S1 receipts.

Gap:

- There is no canary-specific rollback receipt for all seven global steps, especially `transaction`, `tag`, and `push`.

Repair suggestion:

- Do not progress S3/S4 from a canary receipt. If recovery proceeds, require an Issue #10 one-shot evidence-only rollback plan scoped to existing daily artifacts and send-disabled behavior.

## 試金石結果

- 單步隔離執行 production: `PARTIAL`
  - Existing daily_v2 shadow steps can be isolated.
  - Existing production daily path is a monolith around `run_automation daily`.
  - `transaction/tag/push` cannot be isolated because they are not official production daily steps.
- 憑 trace 重建流程: `PARTIAL`
  - Existing daily/storage receipts can reconstruct daily core, artifacts, status, send-disabled/send-skipped behavior, and storage fail-closed outcomes.
  - They cannot reconstruct seven-step canary create/run/select/publish/transaction/tag/push correlation.

## Global gate result

The global production canary readiness gate requires the exact seven steps and no N/A. The existing NEW-TOP10 daily path cannot truthfully satisfy that schema without creating a new subsystem. Therefore:

- S2 verdict: `BLOCK_SCOPE_EXPANSION / CANARY_PATH_NOT_APPLICABLE_WITHOUT_NEW_SUBSYSTEM`
- Existing blocked receipt remains: `BLOCKED`
- `canary_created=false`
- Do not fill PASS evidence with arbitrary text artifacts.
- 禁止以任意文字 artifact 填 PASS。

## 最小替代路徑 proposal

Do not create a production canary for Issue #10. Instead, re-arbitrate the execution card to a recovery-specific one-shot evidence-only gate over the existing daily production entry:

`storage guard → daily core → artifacts → send-disabled receipt`

Required properties:

- one-shot only
- explicit date and entry chain
- send disabled / evidence-only
- storage guard receipt required
- daily core artifacts required
- automation status required
- no marker clear unless separately authorized
- no launchd mutation

This proposal changes the execution card blocking edge and therefore requires mainline / Owner re-arbitration. It must not automatically proceed to S3 or S4.

## why_not_less

Less would mean treating the five-step daily path as if it satisfied the seven-step canary gate. That would blur missing `transaction/tag/push` semantics and create false PASS evidence.

## why_not_more

More would mean building a new canary subsystem, registry, transaction ledger, tag writer, or push pipeline only to satisfy a generic gate. Issue #10 has not measured a need for that expansion; the actual recovery need is one-shot evidence over the existing daily path.

## do_not_absorb

- Do not absorb a new production canary subsystem.
- Do not absorb a new transaction/tag/push registry.
- Do not absorb a second scheduler or daemon.
- Do not absorb a new authority ledger.
- Do not relabel daily artifacts as canary PASS.
- Do not proceed to marker clear, one-shot production, send, launchd, commit, push, merge, or deploy from this audit.

## Next step

Stop at S2 audit. Mainline / Owner must re-arbitrate whether Issue #10 recovery should abandon the global canary path and use the smaller one-shot evidence-only recovery gate instead.

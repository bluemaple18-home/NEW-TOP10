# CARD — NEW-TOP10 Issue #10 Production Recovery Execution

Date: 2026-08-29  
Status: `PENDING_MAINLINE_OWNER_REARBITRATION`  
Decision: `PRODUCTION_STILL_BLOCKED / S2_CANARY_PATH_BLOCK_SCOPE`  
Owner authorization interpretation: Owner 最新只說「授權」production recovery 階段；主線解讀為允許 local repair/readiness evidence，不自動擴張到 marker clear、one-shot live daily、send、launchd、commit、push、merge 或 deploy。

## Goal

建立 Issue #10 production recovery 的逐閘門執行卡，讓已套入 main 的 daily swap stop-loss 候選可以被安全地往 production readiness 推進，但每一步都必須有明確 acceptance、verification、rollback 與 Owner checkpoint。

本卡不是 production 放行單；它只定義後續 recovery 階段的可驗收順序與不可混入邊界。

## Root Question

在三檔候選已套入 main、deterministic tests 已通過的情況下，NEW-TOP10 daily 是否已可恢復 production execution？

目前答案：不可。  
原因：daily policy 仍是 `launch_verified=false`，restart marker 仍拒絕自動清除，production canary capability gate 仍 `BLOCKED`。這些都不是單靠 local tests 可補齊的 production 語意。

## Current Blocker

1. `docs/operations/top10-storage-policy.json` 的 daily candidate 已刻意標為 `launch_verified=false`。
2. restart marker `logs/storage_safety/restart_denied/daily.json` 目前 SHA 為 `fffd80db1b176b19d817cd616f73b192907a98380d1826e62a2607445f7de9eb`，且 `automatic_clear_allowed=false`。
3. `docs/operations/top10-storage-safety.md` 的 stale「目前 launch_verified=true」current-state wording 已於 S0 修正；不得再沿用先前手冊舊敘述作為 production 放行依據。
4. production canary capability gate 仍 `BLOCKED`；尚未有 create→run→select→publish→transaction→tag→push 的正式入口 capability receipt。
5. 先前 S0 capacity `NO-GO` snapshot 已被 fresh S0 evidence supersede，不得沿用。
6. fresh S0 capacity 與 swap 子閘門已通過；剩餘 `NO-GO` reason 僅 `POLICY_NOT_LIVE_VERIFIED`，這會阻擋 production，不阻擋 validation-only S1。
7. Fresh S1 rerun 已由 independent review 裁決 `S1_ACCEPT`；這只接受 non-production representative validation，不等於 production ready。S3 marker clear、S4 one-shot production、S5 send、S6 launchd 仍 blocked。
8. S2 formal-entry capability audit 已裁決 `BLOCK_SCOPE_EXPANSION / CANARY_PATH_NOT_APPLICABLE_WITHOUT_NEW_SUBSYSTEM`；global canary 七步 gate 不適用於現有 five-step daily production path，既有 blocked receipt 維持 `BLOCKED` / `canary_created=false`。

## Facts

- Issue #10 三檔候選已整合進 main workspace：
  - `app/storage_safety.py` → `2a4b3a100fd043f701259f3a818c87f6924f1296aedd5c92d67a916ce5fe5abd`
  - `tests/test_storage_safety.py` → `3d41e15ef5e9011a770cda2cf47a46f1586af962235419d5836b743547b8450f`
  - `docs/operations/top10-storage-policy.json` → `a788e7aea32f0ffd901d87c89cddbd67cc90e3f516a6984ffff9a44e80b4588e`
- 受影響 gate 已有 evidence：`79 passed, 31 subtests passed`。
- 新 daily 語意：
  - 2GiB swap growth → `SOFT_SWAP_WARNING`，不觸發 stop。
  - 4GiB swap growth → `SWAP_EMERGENCY_HARD_STOP`。
  - RSS+swap 同升、host runtime free space、RSS hard cap 仍 fail closed。
  - warning 後 live sampling density 可收斂到 50% interval，且不可 busy-loop。
- daily policy 目前 `launch_verified=false`，代表 local candidate 不等於 live-ready policy。
- formal canary capability receipt 目前只能作為 blocked receipt，不得偽造 PASS 或以真 canary 補證據。
- Superseded prior S0 read-only measure evidence:
  - `superseded=true`
  - `host_free_bytes=29052866560`
  - `host_total_bytes=245107195904`
  - `verdict=NO-GO`
  - `reasons=["POLICY_NOT_LIVE_VERIFIED", "HOST_START_FREE_SPACE_BELOW_THRESHOLD"]`
  - dry-run reclaim：`bytes_before=2059737`、`bytes_after=2059737`、`file_count=29`、`removed_paths=[]`
  - 解讀：此 snapshot 已被 fresh S0 receipt 取代，不得再用來阻擋 S1。
- Fresh S0 capacity receipt：`.work/CARD-NEW-TOP10-ISSUE10-PRODUCTION-RECOVERY-20260829/s0_fresh_capacity_receipt.json`
  - `captured_at_utc=2026-08-29T03:20:08Z`
  - `fresh_run=true`
  - `supersedes_prior_capacity_snapshot=true`
  - `host_free_bytes=37798309888`
  - `host_total_bytes=245107195904`
  - `start_free_ratio_threshold=0.15`
  - `computed_free_ratio=0.15421134311701026`
  - `computed_margin_bytes=1032230502`
  - `project_bytes=3437615639`
  - `project_file_count=38852`
  - `swap_bytes=9497351290`
  - `rss_bytes=0`
  - `host_start_free_space_subgate=PASS`
  - `swap_metric_subgate=PASS`
  - `overall_measure_verdict=NO-GO`
  - `remaining_reasons=["POLICY_NOT_LIVE_VERIFIED"]`
  - 解讀：capacity 子閘門已過但餘裕薄；production readiness 未過，因 policy false 仍阻擋 production。
- Fresh S1 validation summary：`.work/CARD-NEW-TOP10-ISSUE10-PRODUCTION-RECOVERY-20260829/s1_fresh_validation_summary.md`
  - receipt path：`.work/CARD-NEW-TOP10-ISSUE10-PRODUCTION-RECOVERY-20260829/s1_fresh_validation/bounded_observer_receipt.json`
  - receipt SHA256：`a811929ebd4d2bd872a184be0eca64d130c8a8c828a094330ad8409772f25fd0`
  - verdict：`INCONCLUSIVE`
  - interpretation：`FAIL-CLOSED`
  - `fresh_s1=true`
  - `supersedes_run2=false`
  - `production_candidate_policy_sha=a788e7aea32f0ffd901d87c89cddbd67cc90e3f516a6984ffff9a44e80b4588e`
  - cold：exit `0`、guard `OK`、child `OK`、peak RSS `1849393152`、peak/max swap growth `1179899659`、min host ratio `0.14842306791453244`、project delta `344721414`、artifacts complete、source unchanged、unknown writes empty、final quiescent true。
  - cold warning path：not exercised；此 run 不得宣稱 warning cadence 已驗證。
  - warm：exit `78`、pre-child `NO-GO`、reason `HOST_START_FREE_SPACE_BELOW_THRESHOLD`、preflight free `36379480064` / total `245107195904`（約 `14.84%`）。
  - warm child receipt missing 是因未 spawn，不是 crash。
  - conclusion：fresh S0 capacity PASS 只證明單次起跑；薄餘裕不足以支撐 cold 後第二次 15% start gate。
- Fresh S1 falsifiable hypotheses:
  - A：cold 造成 swap/file allocation 壓低 free space。若 baseline headroom 增加 `>=2GiB`，warm 應能在同一 15% start gate 下 spawn。
  - B：concurrent external writes 或 purgeable-space 波動造成 free space 下降。若靜置後 fresh measure 仍下降，此假說成立度提高。
- Fresh S1 rerun acceptance：`.work/CARD-NEW-TOP10-ISSUE10-PRODUCTION-RECOVERY-20260829/s1_fresh_rerun_acceptance.md`
  - receipt path：`.work/CARD-NEW-TOP10-ISSUE10-PRODUCTION-RECOVERY-20260829/s1_fresh_rerun_20260829/bounded_observer_receipt.json`
  - receipt SHA256：`49cc62094fbb07f787a92e90cb9bb8cd22cf86ebe056dfa3af47764d4935032b`
  - independent review：`S1_ACCEPT`
  - verdict：`BOUNDED_ACCEPTABLE`
  - scope：validation-only；`production_run=false`、`network_send=false`、`production_policy_changed=false`、`restart_marker_cleared=false`、`git_operation=false`
  - fresh preflight：`38021488 KiB >= 38001527 KiB`，PASS
  - cold：exit `0`、guard `OK`、child `OK`、live samples `2`、peak RSS `1815642112`（約 `1.816GB`）、max swap growth `28311552`、min host ratio `0.15726567289806337`、project delta `344722608`、artifacts/source/quiescence all OK。
  - warm：exit `0`、guard `OK`、child `OK`、live samples `1`、elapsed `57.56995701789856s`、peak RSS `4063232`（約 `4MB`）、max swap growth `446305403`、min host ratio `0.15676474229279427`、project delta `132090445`、artifacts/source/quiescence all OK。
  - remaining risks：warm 約 56–58 秒且只有 1 個 live sample；4MB 不可當強峰值證據。兩輪均未 exercise 2GiB warning，warning cadence live evidence 仍缺，不得宣稱已驗證。
- S2 formal-entry capability audit：`.work/CARD-NEW-TOP10-ISSUE10-PRODUCTION-RECOVERY-20260829/s2_formal_entry_capability_audit.md`
  - verdict：`BLOCK_SCOPE_EXPANSION / CANARY_PATH_NOT_APPLICABLE_WITHOUT_NEW_SUBSYSTEM`
  - audit result：Task boundary `PARTIAL`、I/O `PARTIAL`、programmable criteria `PARTIAL`、independent SOP `PASS/PARTIAL`、control flow `PASS`、failure/rollback `PARTIAL`
  - touchstones：single-step isolation production `PARTIAL`；trace reconstruction `PARTIAL`
  - hard fact：official daily chain is `launchd plist → run_daily_publish.sh → run_daily.sh → run_automation daily`
  - hard fact：official daily core is ETL / validate / rank / report / publish-ready / optional send
  - hard fact：`app/contracts/daily_v2.py` 與 `app/automation/daily_contract.py` 都固定 five-step daily semantics；production-equivalent attestation fail-closed returns `False`
  - hard gap：沒有 `transaction/tag/push` official production entrypoint/correlation artifacts
  - global gate：requires exact seven and no N/A；不得以任意文字 artifact 填 PASS
  - minimal alternative proposal：Issue #10 不建立 production canary，改用既有 daily 正式入口做 one-shot evidence-only recovery gate（storage guard → daily core → artifacts → send-disabled receipt）；此路徑會改 blocking edge，需主線/Owner 重新裁決，不得自動進 S3/S4。

## Stable Trace IDs

Functional Requirements:

- `FR-ISS10-01` — daily-only soft warning / emergency hard stop contract：2GiB warning、4GiB hard stop，legacy jobs 語意不變。
- `FR-ISS10-02` — receipt contract：warnings 與 limits 為 additive schema，從全部 samples deterministic 重算 peak swap delta。
- `FR-ISS10-03` — warning density contract：warning 後 sampling interval 收斂，不影響 normal cadence，不 busy-loop。
- `FR-ISS10-04` — policy truth contract：candidate policy 不得暗示 production verified；manual docs 不得用舊 launch_verified 敘述放行。
- `FR-ISS10-05` — production canary capability contract：正式入口必須能證明 create→run→select→publish→transaction→tag→push。
- `FR-ISS10-06` — Owner checkpoint contract：marker clear、one-shot daily、send、launchd 都是獨立授權，不被「production recovery 授權」自動包含。

Success Criteria:

- `SC-ISS10-01` — storage safety candidate deterministic tests 通過：`79 passed, 31 subtests passed`。
- `SC-ISS10-02` — daily policy 明確 `launch_verified=false`，且 verification_basis 說明 isolated candidate / RUN2 未驗證 production。
- `SC-ISS10-03` — operation manual 與 policy/current facts reconciled；沒有 stale launch_verified=true 放行語意。
- `SC-ISS10-04` — formal canary capability receipt 不含 placeholder，且 gate 由 `BLOCKED` 轉為 deterministic pass。
- `SC-ISS10-05` — marker clear 需 Owner 單獨授權，且清除前保存 marker SHA/內容。
- `SC-ISS10-06` — one-shot production run 有明確日期、入口、send mode、evidence path 與 stop/rollback condition。
- `SC-ISS10-07` — send 與 launchd 分別以獨立 checkpoint 放行，不混入前序 slice。

Prior candidate slices:

- `SLICE-ISS10-STOPLOSS` traces_to: `FR-ISS10-01`, `FR-ISS10-02`, `SC-ISS10-01`, `SC-ISS10-02`
- `SLICE-ISS10-CADENCE` traces_to: `FR-ISS10-03`, `SC-ISS10-01`

## Blocking Edges and Frontier

Blocking edges:

- `SLICE-ISS10-RECOVERY-S0` must complete before any claim that docs/policy reflect current production truth.
- `SLICE-ISS10-RECOVERY-S1` is accepted for non-production representative validation only; it does not unlock production side effects.
- `SLICE-ISS10-RECOVERY-S2` audited the formal canary path and blocks scope expansion; a seven-step canary receipt cannot be truthfully repaired without a new subsystem.
- `SLICE-ISS10-RECOVERY-S3` is blocked by Owner marker-clear authorization and by mainline/Owner re-arbitration after S2 block-scope.
- `SLICE-ISS10-RECOVERY-S4` is blocked by S3 and by explicit Owner authorization for a dated one-shot production run.
- `SLICE-ISS10-RECOVERY-S5` is blocked by S4 and by explicit send authorization.
- `SLICE-ISS10-RECOVERY-S6` is blocked by S4/S5 decision outcome and by explicit launchd/control-plane authorization.

Current frontier:

- Mainline / Owner re-arbitration：decide whether to replace the global canary path with an Issue #10 one-shot evidence-only recovery gate over the existing daily entry.

Blocked frontier:

- `SLICE-ISS10-RECOVERY-S2` — audited/block-scope；no truthful seven-step canary repair without a new subsystem.
- `SLICE-ISS10-RECOVERY-S3` through `S6` remain blocked until Owner grants each external/production/control-plane step separately.

## Slices

### `SLICE-ISS10-RECOVERY-S0` — docs/policy truth reconciliation

traces_to: `FR-ISS10-04`, `SC-ISS10-02`, `SC-ISS10-03`

Acceptance:

- `docs/operations/top10-storage-safety.md` no longer contains a current-state claim that daily is `launch_verified=true`.
- Policy truth remains explicit: daily candidate is `launch_verified=false`.
- Any readiness wording says local candidate evidence is necessary but not sufficient for production.

Verification:

- Static text check for stale `launch_verified=true` current-state language.
- Policy load/read check confirms daily `launch_verified=false`.
- `git diff --check` on changed docs/policy.

Likely files:

- `docs/operations/top10-storage-safety.md`
- `docs/operations/top10-storage-policy.json` only if wording drift is discovered; otherwise no policy mutation.
- `docs/tasks/*` evidence notes if needed.

Rollback:

- Revert only the S0 documentation edits.
- Do not restore stale production-verified wording unless new evidence genuinely supports it.

### `SLICE-ISS10-RECOVERY-S1` — non-production representative validation with new semantics

traces_to: `FR-ISS10-01`, `FR-ISS10-02`, `FR-ISS10-03`, `SC-ISS10-01`, `SC-ISS10-06`

Acceptance:

- A non-production representative run exercises the new daily semantics without using production send, production marker clear, launchd, or external publish.
- Evidence captures receipt warnings, limits, peak swap growth, stop reasons if any, process identity, final quiescence, and source identity.
- Validation explicitly distinguishes bounded local evidence from production live readiness.
- Fresh S0 evidence shows host capacity and swap metric subgates PASS; S1 is no longer blocked by host capacity. `POLICY_NOT_LIVE_VERIFIED` still blocks production, but does not block validation-only evidence.
- Fresh S1 rerun is accepted under the established S1 warm contract. This acceptance remains validation-only and must not be promoted to production readiness.
- Neither cycle exercised `SOFT_SWAP_WARNING`; warning cadence live evidence remains missing and must not be claimed.

Verification:

- Use only non-production representative validation command approved for this slice.
- No daily production entry, no canary, no send, no network mutation.
- Receipt reviewed against 2GiB warning / 4GiB hard stop / 50% warning cadence expectations.
- If warning path is not exercised, mark `warning_path_exercised=false` and do not claim warning cadence validation.
- Warm single-live-sample peak RSS is weak peak evidence but accepted for S1; do not use it as strong production peak-memory proof.

Likely files:

- `.work/CARD-NEW-TOP10-ISSUE10-DAILY-SWAP-STOPLOSS-01/*` evidence only.
- No source/config/test changes unless S1 discovers a reproducible local product bug and Owner authorizes a repair card.

Rollback:

- Delete or quarantine only S1-generated local evidence if invalid.
- No production state should have changed.

### Checkpoint A — local truth and representative evidence

traces_to: `SC-ISS10-02`, `SC-ISS10-03`, `SC-ISS10-06`

Decision:

- S0/S1 evidence allowed S2 audit, but S2 blocks the global canary path as scope expansion.
- Do not clear marker, run production, or send until mainline/Owner re-arbitrates the recovery path.

### `SLICE-ISS10-RECOVERY-S2` — canary formal-entry capability audit

traces_to: `FR-ISS10-05`, `SC-ISS10-04`

Status: `AUDITED_BLOCK_SCOPE`

Acceptance:

- Formal canary capability receipt has real, deterministic artifacts for all seven steps:
  1. create
  2. run
  3. select
  4. publish
  5. transaction
  6. tag
  7. push
- Missing artifacts fail closed; placeholders are not accepted.
- Repair may be dry-run or capability-only, but cannot use a real production canary to backfill missing evidence.
- Audit result: existing NEW-TOP10 daily path cannot provide official `transaction/tag/push` production entrypoint/correlation artifacts; therefore seven-step canary repair is not applicable without a new subsystem.

Verification:

- S2 audit uses static source evidence from official daily chain, daily v2 contracts, production daily contract, wrapper send guards, and prior blocked receipt.
- Existing blocked receipt remains `BLOCKED` / `canary_created=false`.
- No arbitrary text artifact may be used to fill seven-step PASS evidence.
- Minimal alternative path requires mainline/Owner re-arbitration before changing blocking edges.

Likely files:

- `.work/*/production_canary_capability_receipt*.json`
- `docs/tasks/*` repair/evidence card
- Canary wrapper/receipt tooling only if the gap is in local receipt generation, and only under a separate implementation card.

Rollback:

- Revert local receipt/tooling changes.
- Keep blocked receipt as evidence of why production remained stopped.

### `SLICE-ISS10-RECOVERY-S3` — Owner checkpoint: marker clear

traces_to: `FR-ISS10-06`, `SC-ISS10-05`

Acceptance:

- Owner explicitly authorizes clearing or superseding `logs/storage_safety/restart_denied/daily.json`.
- Before clear, record marker path, SHA, content summary, reason, actor, timestamp, and rollback note.
- Marker clear is not bundled with production run.

Verification:

- Read marker before action.
- Verify exact marker no longer blocks only after Owner-approved operation.
- Confirm no launchd/send/run occurred as part of this slice.

Likely files:

- `logs/storage_safety/restart_denied/daily.json`
- `.work/*/marker_clear_receipt.json`

Rollback:

- Restore saved marker content if clear was erroneous and no production run has started.
- If production run has started, stop and escalate; do not silently recreate marker.

### `SLICE-ISS10-RECOVERY-S4` — one-shot production run with explicit date/entry/send mode

traces_to: `FR-ISS10-06`, `SC-ISS10-06`

Acceptance:

- Owner authorizes one exact dated run.
- Entry chain is explicitly stated before execution:
  `launchd plist → run_with_storage_guard.sh daily → run_daily_publish.sh → run_daily.sh → run_automation daily → possible send`
- Send mode is explicitly set to `evidence-only` or `dry-run`; if actual send is desired, stop and split to S5.
- Runtime stop conditions include storage, RSS, swap, marker, source identity, receipt schema, and final quiescence.

Verification:

- Capture production run receipt and compare against S1/S2 contracts.
- Verify no send occurred unless S5 has separate approval.
- Verify no launchd schedule mutation occurred.

Likely files:

- `logs/storage_safety/*`
- `.work/*/one_shot_production_receipt.json`
- Existing shell entry scripts as read-only unless a separate code repair is authorized.

Rollback:

- Stop process group if stop condition triggers.
- Preserve receipts and marker state.
- Do not retry automatically.

### `SLICE-ISS10-RECOVERY-S5` — separate send authorization

traces_to: `FR-ISS10-06`, `SC-ISS10-07`

Acceptance:

- Owner explicitly authorizes send after reviewing one-shot evidence.
- Send target, content, and idempotency/duplicate-send protection are documented.
- Send is not implied by S4 dry-run/evidence-only success.

Verification:

- Send receipt exists with correlation ID and duplicate protection.
- If send is skipped, receipt states skipped and why.

Likely files:

- Send receipt/evidence under `.work/*` or existing send log path.
- No ranking/model code changes.

Rollback:

- If send is wrong, record correction procedure; do not delete evidence.
- No automatic resend.

### `SLICE-ISS10-RECOVERY-S6` — separate launchd/control-plane recovery

traces_to: `FR-ISS10-06`, `SC-ISS10-07`

Acceptance:

- Owner explicitly authorizes launchd/control-plane mutation.
- Current plist, schedule, entrypoint, environment, and enabled state are captured before change.
- Recovery decision says whether launchd remains disabled, is reloaded, or is scheduled for next run.

Verification:

- Read-only launchd status before and after any authorized mutation.
- Confirm next scheduled behavior without running an unscheduled production daily.

Likely files:

- launchd plist path
- `.work/*/launchd_recovery_receipt.json`
- Operation docs only if current control-plane truth changes.

Rollback:

- Restore previous plist/enabled state from captured receipt.
- If reload fails, stop with evidence; do not keep retrying.

## why_not_less

不能只靠已通過的 `79 passed, 31 subtests` 放行 production，因為 tests 證明的是 local deterministic behavior，不證明 live entry chain、marker authority、send side effects 或 launchd control plane。

不能只改手冊文字就放行，因為 blocker 包含 policy `launch_verified=false`、restart marker 與 canary capability gate。

## why_not_more

本卡不把 recovery 做成新 governance system、registry、daemon、第二套 scheduler 或第二套 canary engine。Issue #10 的 measured gap 是 daily swap stop-loss 與 production readiness evidence，不是全面重建 runtime。

## do_not_absorb

- 不吸收新的 authority ledger。
- 不吸收新的 workflow FSM。
- 不吸收新的 database 或 canonical writer。
- 不吸收第二套 scheduler / daemon / registry。
- 不把 canary capability repair 變成真正 production canary。
- 不把 send、launchd、marker clear 混入 local readiness。

## 禁止混入 #1-#8

1. 不得在 S0/S1/S2 清除 restart marker。
2. 不得在 S0/S1/S2 執行 one-shot live daily。
3. 不得在 S0/S1/S2 發送任何 production send。
4. 不得在 S0/S1/S2 修改 launchd 或外部控制面。
5. 不得把 stale `launch_verified=true` 手冊敘述當作放行證據。
6. 不得用真 production canary 補 formal-entry capability receipt。
7. 不得 commit、push、merge、deploy，除非 Owner 另行明確授權對應步驟。
8. 不得把 Owner 的「授權 production recovery 階段」解讀為授權所有 production side effects。

## Next Step

從 current frontier 選一張最小 slice：

1. Stop at S2 audit: `BLOCK_SCOPE_EXPANSION / CANARY_PATH_NOT_APPLICABLE_WITHOUT_NEW_SUBSYSTEM`。
2. Mainline / Owner must re-arbitrate whether to use the smaller Issue #10 one-shot evidence-only recovery gate instead of the global canary path。
3. S3+ 仍等待獨立 Owner checkpoint；S1/S2 不授權 marker clear、production daily、send 或 launchd。

## Waiting Conditions

- S3 之前等待 Owner marker-clear 授權。
- S4 之前等待 Owner 指定日期、入口與 send mode。
- S5 之前等待 Owner 單獨 send 授權。
- S6 之前等待 Owner 單獨 launchd/control-plane 授權。

## Limits

本卡不是 apply、merge、commit、push、deploy、marker clear、one-shot production run、send 或 launchd 授權。任何跨出 local repair/readiness evidence 的動作，都需要新的 Owner 明示授權與獨立 receipt。

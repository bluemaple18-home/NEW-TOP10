---
id: FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1
status: ACCEPTED_I1_I4
type: implementation
chain_id: FOG-RUNTIME-TIME-AUTHORITY-01
dispatch_version: 2
implementation_generation: 1
ownership: implementation_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 實作橫跨時間權威、receipt exact schema、processed/source authority、獨立 verifier、shell與LaunchAgent靜態 wiring；錯誤會誤放行或阻斷自動研究，且需 clean-room 重建前鏈安全能力。
accepted_architecture_candidate_sha: f9cfbabde1d89d2f759a7cbc60d1dd03e96a2171
architecture_review_sha: 5c95a2e
accepted_main_sha: 408f3e0
implementation_thread_id: 019fa64f-3973-7d10-b0aa-4759af7aff1d
reviewer_thread_id: 019fa66b-444f-7522-915b-15aad3de5fe3
repair_thread_id: 019fa67b-7377-7002-a8d3-d7f6aee514c5
integration_main_sha: 74a034f
evidence_path: docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/
---

# FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1

## Goal

依已接受的
`docs/architecture/fog_runtime_time_authority_v1.md`與
`docs/architecture/fog_runtime_receipt_v3.schema.json`，以 clean-room方式完成
I1–I4：

- 單一市場時間 authority與 versioned policy；
- processed-ID、source lineage、trusted baseline authority；
- deterministic receipt v3 producer與 independent verifier；
- shell／LaunchAgent靜態 wiring。

Executor 只交付可獨立 Review 的 candidate，不執行 I5 live migration、LaunchAgent
reload/kickstart、circuit recovery或 production acceptance。

## Accepted authority與lineage

- Accepted architecture candidate：
  `f9cfbabde1d89d2f759a7cbc60d1dd03e96a2171`
- Targeted Review GO：
  `5c95a2e`
- Mainline accepted tree：
  `408f3e0`
- Original Review findings：`FRTA-P1-01/02/03`，均已 CLOSED。
- Required regression IDs：
  - `FRTA-REG-RRV-P1-01-PROCESSED-ID`
  - `FRTA-REG-RRV-P1-03-SOURCE-BASELINE`
  - `FRTA-REG-RECEIPT-V3-EXACT`
  - `FRTA-REG-TIME-DATE-LINEAGE`

Rejected candidate `acd835df3a4fe40a149333dca0b55e62cc8eded9` 只可作
non-ancestor歷史證據；禁止 merge、cherry-pick、copy patch、以其 stored PASS
取代本卡 RED→GREEN。

## Traceability與dependency frontier

| Slice ID | traces_to | blocking edges | Exit |
|---|---|---|---|
| `FRTA-I1-AUTHORITY` | architecture §3–§6、§8–§10；四個 `FRTA-REG-*` | 無；current frontier | pure authority與 red matrix GREEN |
| `FRTA-I2-PRODUCER` | architecture §7.1–§7.4、receipt schema | I1 | fixture receipt v3 deterministic GREEN |
| `FRTA-I3-VERIFIER` | architecture §7.5、§8–§10 | I1、I2 | independent fixture consumer GREEN |
| `FRTA-I4-WIRING` | architecture §7、§10 I4 | I1–I3 | shell/plist static wiring GREEN；未操作 live |
| `FRTA-I5-LIVE` | architecture §10 I5、§11–§13 | Implementation Review GO | `pending / out-of-scope` |

每完成 2 個 slice必須做 checkpoint。不得跳到仍被 blocking edge擋住的 slice。

## Phase 0：baseline與RED

修改 implementation前：

1. 記錄 main source SHA、clean worktree、existing/missing file inventory。
2. 記錄 model、ranking、weights、baseline與 promotion protected hashes。
3. 先寫會失敗的 public-behavior tests，固定四個 `FRTA-REG-*`：
   - forged／同源 processed-ID；
   - source path/hash drift與 self-reported baseline；
   - v3 missing/unknown/type/forged lineage；
   - 台北跨 UTC 日界與合法休市日 source lineage。
4. 保存 RED命令、exit與最小錯誤摘要；不得把 missing module本身當成 GREEN。

## Slice I1：pure authority

實作：

- `config/fog_runtime_time_authority_v1.json`
- `scripts/fog_authority_contracts.py`
- `scripts/fog_runtime_time_authority.py`
- `scripts/verify_processed_id_authority.py`
- `tests/test_fog_runtime_time_authority.py`
- `tests/test_fog_closed_regime_runtime.py`

Required behavior：

- strict RFC3339 UTC `Z`、IANA `Asia/Taipei` projection；
- signed age boundary：`-5`／`900` accept，`-5.001`／`900.001` reject；
- canonical policy JSON/hash，不接受 env/receipt policy override；
- `market_run_date`、`artifact_run_date`、`daily_source_date`、
  `source_trade_date`分離；
- host timezone／locale independent；
- processed-ID與 source/baseline role-path authority fail closed。

Checkpoint A：I1 pure tests與兩個 authority regressions GREEN，runtime wiring仍無
diff。

## Slice I2：receipt v3 producer

實作／修改：

- `scripts/verify_closed_regime_runtime.py`
- `scripts/verify_fog_closed_regime_recovery.py`
- I1 authority modules
- `tests/test_fog_closed_regime_runtime.py`
- `tests/test_daily_research_quota_verifier.py`

Required behavior：

- producer/verifier共用
  `docs/architecture/fog_runtime_receipt_v3.schema.json`；
- closed exact schema、complete fixture、canonical hashes；
- v2不得 relabel或補造 authority，只能 archive/fail closed；
- 合法休市日：
  run/artifact=`2026-08-08`、daily source=`2026-08-07`可通過；
- wrong/future source、artifact drift、unknown/missing/type mismatch、
  absolute/path escape、wrong contract hash全部拒絕；
- receipt不能自報 baseline、policy、date、regime或 production impact取得 authority。

## Slice I3：independent verifier

修改：

- `scripts/verify_daily_research_quota.py`
- I1/I2 authority與 verifier modules
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_fog_closed_regime_runtime.py`

Required behavior：

- verifier用自有 clock、repo policy與 canonical source artifacts重算；
- 不使用 `generated_at_utc.date() == run_date`；
- stale/future/naive/wrong market date/host drift、midnight rollover、
  exact boundaries皆 deterministic；
- processed-ID、source-lineage、baseline與 receipt v3四個 regressions全 GREEN。

Checkpoint B：I1–I3 targeted suite GREEN；canonical fixture與 hostile mutations
由獨立 verifier重算；production scheduler仍未切換。

## Slice I4：shell與LaunchAgent靜態 wiring

修改：

- `scripts/run_fog_research_worker.sh`
- `scripts/run_daily_research_quota.sh`
- `scripts/com.new-top10.fog-research-worker.plist`
- I1–I3 modules
- `tests/test_fog_research_retry_circuit.sh`
- `tests/test_fog_runtime_time_wiring.sh`
- I1–I3 Python tests

Required behavior：

- worker建立 immutable time context，daily child只傳遞；
- shell不存在 `date +%F` contract identity fallback；
- `TZ=UTC`／`Asia/Taipei`／`America/Los_Angeles` identity一致；
- legacy env mismatch、market-midnight rollover fail closed；
- plist不注入 date/timezone/freshness policy；
- `fog_worker`維持唯一 queue mutation owner；
- 不 reload/kickstart/install LaunchAgent。

## Changed-file allowlist

Production/config：

- `config/fog_runtime_time_authority_v1.json`
- `scripts/fog_authority_contracts.py`
- `scripts/fog_runtime_time_authority.py`
- `scripts/verify_processed_id_authority.py`
- `scripts/verify_closed_regime_runtime.py`
- `scripts/verify_fog_closed_regime_recovery.py`
- `scripts/verify_daily_research_quota.py`
- `scripts/run_fog_research_worker.sh`
- `scripts/run_daily_research_quota.sh`
- `scripts/com.new-top10.fog-research-worker.plist`

Tests：

- `tests/test_fog_runtime_time_authority.py`
- `tests/test_fog_closed_regime_runtime.py`
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_fog_research_retry_circuit.sh`
- `tests/test_fog_runtime_time_wiring.sh`

Evidence/card：

- `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/**`
- 本卡

Read-only normative authority，不得修改：

- `docs/architecture/fog_runtime_time_authority_v1.md`
- `docs/architecture/fog_runtime_receipt_v3.schema.json`
- 原 architecture／Repair／Review evidence

若需要 allowlist外檔案，立即停止回主線；不得臨場擴張。

## Forbidden scope

- 不操作 live LaunchAgent、installed plist、queue、retry/circuit state或 scheduler。
- 不修改 model、ranking、weights、baseline、promotion或 production artifacts。
- 不修改 architecture/schema authority或原 Review/Repair evidence。
- 不 merge/push/deploy、切 production、archive v2 receipts或跑三輪 acceptance。
- 不採用 rejected `acd835df…` code/patch/fixtures/stored PASS。
- 不自行建立 Review/Repair/Implementation-2或宣稱 ACCEPTED。

## Verification

至少執行：

```bash
cd <repo-root>
.venv/bin/python -m pytest -q \
  tests/test_fog_runtime_time_authority.py \
  tests/test_fog_closed_regime_runtime.py \
  tests/test_daily_research_quota_verifier.py
bash tests/test_fog_research_retry_circuit.sh
bash tests/test_fog_runtime_time_wiring.sh
bash -n scripts/run_fog_research_worker.sh
bash -n scripts/run_daily_research_quota.sh
plutil -lint scripts/com.new-top10.fog-research-worker.plist
.venv/bin/python -m pytest -q
git diff --check
```

另需：

- exact allowlist；
- four regression IDs逐項 RED→GREEN evidence；
- protected hashes before/after一致；
- schema/fixture由 producer與 verifier共用；
- secret、本機絕對路徑、debug marker、TODO/FIXME掃描；
- shell不含未綁時區 date authority；
- commit後 worktree clean。

## Delivery與後續

- Executor只交 `DELIVERED_IMPLEMENTATION_CANDIDATE` 與完整 SHA。
- strict candidate必須進新的唯一 Implementation Reviewer task；該 Reviewer與
  architecture Reviewer不同責任線。
- `NO_GO`後本 implementation chain只建立一個可重用 Repair task，最多
  Repair-2；修後回同一 Implementation Reviewer。
- Review GO後由主線整合 candidate，再單獨執行 I5 migration/live acceptance。
- I5失敗不得 legacy fallback；rollback到 safe stopped state。

## Pre-dispatch receipt

- Current card：
  `docs/tasks/2026-07-28_FOG-RUNTIME-TIME-AUTHORITY-01_IMPLEMENTATION-1_clean_room_runtime.md`
- Mainline dispatcher：
  `019f82c1-b7d0-7eb3-9371-7a95ebfbd7ce`
- Previous accepted card／task：
  `REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01`／
  `019fa448-4ffe-7473-af1a-7cc1f417bdd7`
- Source kind：`commit`
- Source SHA：`87e4da7dd63bafe82b16c28990e7be6db137b4e6`
- Source branch：`main`
- Source clean：是
- Git metadata：可用
- unrelated dirty paths：`[]`
- Client receipt：
  `client-new-thread:41ed603a-6075-45ba-b5d2-822954c3db36`
- Implementation task：
  `019fa64f-3973-7d10-b0aa-4759af7aff1d`
- Task title：`Implement FOG runtime authority`
- Worktree：獨立 Codex worktree；初始 detached HEAD、clean
- Capability preflight：Git／Python／唯讀 `rg` 可用；CodeGraph index
  未初始化，Executor 不建立 allowlist 外狀態，改以唯讀查詢並留 evidence
- Workflow：
  `ARCHITECTURE_REVIEW_GO → ACCEPTED → IMPLEMENTATION_IN_PROGRESS`
- Gate 1 card contract：`PASS`
- Gate 2 visible thread：`PASS`
- Gate 3 candidate delivery：
  `PASS`（`f7d51a3d994707c819198fd1edcdcf0db4dd0775`）
- Gate 4 independent implementation review：
  `REVIEW_GO`（Repair-1 `6905ab2`；re-review `3642c99`）
- Gate 5 mainline integration：
  `PASS`（`74a034f`）
- I5 live/runtime acceptance：`PENDING / OUT_OF_SCOPE`

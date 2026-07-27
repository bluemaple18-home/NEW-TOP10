---
id: FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1
status: REPAIR_READY
type: repair
chain_id: FOG-RUNTIME-TIME-AUTHORITY-01
dispatch_version: 2
repair_generation: 1
ownership: repair_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 三個固定 P1 涉及休市日資料語意、前鏈安全能力重建與 receipt exact-schema trust boundary；需修補核心 architecture contract，但不得進入 runtime 實作。
reviewed_candidate_sha: 26d8471d15572f216095122f2462df79bc96edc1
review_evidence_sha: 3102e13
reviewer_thread_id: 019fa448-4ffe-7473-af1a-7cc1f417bdd7
repair_thread_id: 019fa471-2a58-7690-951d-9be2a2a4ca97
evidence_path: docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1/
---

# FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1：時間契約閉合

## Repair question

在不修改 runtime code、舊 blocked chain 或 production state 的前提下，修正
architecture candidate `26d8471d15572f216095122f2462df79bc96edc1` 的三個固定
P1，使契約能：

1. 區分 civil run identity、artifact identity 與 data source date；
2. 以合法 successor lineage重建前鏈已關閉的安全能力，而不接受 rejected
   Repair-2 candidate；
3. 以單一 versioned authority完整定義 receipt v3 exact schema。

## Fixed findings ledger

| Finding ID | Severity | Required closure |
|---|---|---|
| `FRTA-P1-01` | P1 | 拆開 `market_run_date`、artifact run identity、daily data source date；新增休市日 deterministic case |
| `FRTA-P1-02` | P1 | 固定 successor base/rebuild policy，將前鏈安全 modules/tests納入 implementation allowlist與 regression mapping |
| `FRTA-P1-03` | P1 | 新增完整 receipt v3 exact schema、types、required/optional/nullability、unknown-field與 v2 mapping |

Review evidence：
`docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01/review.md`。

Repair 只可關閉上述 findings與其直接 regression。不得新增產品要求、改名重置
chain或宣稱 runtime已修復。

## Required repair

### FRTA-P1-01：三種日期語意

Architecture 必須分開定義：

- `market_run_date`：由 run context UTC instant投影 `Asia/Taipei` 的 civil date；
- `artifact_run_date`／artifact identity：本次 daily run的 identity/path binding；
- `daily_source_date`：artifact內資料的 canonical source date，可早於
  `market_run_date`；
- `source_trade_date`：regime-history最近適用交易日。

不得再要求 `daily_source_date == market_run_date`。Verifier 必須從 canonical
artifact／source lineage重算各欄位。新增至少一個固定休市日 case：

```text
market_run_date=2026-08-08
artifact_run_date=2026-08-08
daily_source_date=2026-08-07
expected=ACCEPT when all lineage/hash/freshness gates pass
```

另需列出錯誤 source date、future source date及 artifact identity drift 的
fail-closed outcome。

### FRTA-P1-02：successor lineage與能力重建

明定：

- `acd835df…` 維持 rejected/non-ancestor evidence source，不得 merge、cherry-pick
  或視為 accepted base；
- successor implementation從 Review GO 後的 mainline accepted architecture
  commit開始；
- 只以 clean-room reimplementation重建前鏈已關閉的能力與 tests；
- `RRV-P1-01` processed-ID authority、`RRV-P1-03` source-lineage/baseline
  authority及 time regression必須有固定 regression IDs；
- I1–I5 implementation allowlist納入必要 modules/tests：
  `scripts/fog_authority_contracts.py`、
  `scripts/verify_fog_closed_regime_recovery.py`、
  `scripts/verify_processed_id_authority.py`、
  `scripts/verify_closed_regime_runtime.py`、
  `tests/test_fog_closed_regime_runtime.py`及其直接 verifier tests；
- 不得把 rejected candidate code的存在當成 regression已通過。

Architecture 必須提供 keep/reimplement/reject matrix、合法 base、逐 slice allowlist
與 red→green tests。

### FRTA-P1-03：receipt v3 exact schema

新增：

`docs/architecture/fog_runtime_receipt_v3.schema.json`

此檔是 architecture phase 的 machine-readable normative contract，至少必須：

- 使用 closed object schema，所有 object layer明定
  `additionalProperties: false`；
- 完整列出 top-level與 nested keys、types、required keys、optional/nullability；
- 綁定 time authority、run/artifact/source dates、contract/policy/hash、
  queue owner、runner identity、research contract、exact regime、
  state transition、topic-run lineage、production impact；
- 明定 canonical RFC3339 UTC `Z`、IANA zone、date與 SHA-256格式；
- 明定 producer/verifier共用同一 repo authority；
- 列出 v2→v3 field mapping：可直接重算、必須重新查 authority、無法補造而
  fail closed；
- unknown/missing/type mismatch一律 deterministic reject；
- 至少提供一個 canonical complete v3 fixture與 hostile mutation table，可放在
  schema `examples`與 Repair evidence，不得建立第二套相互矛盾 schema。

## Allowlist

- `docs/architecture/fog_runtime_time_authority_v1.md`
- `docs/architecture/fog_runtime_receipt_v3.schema.json`
- `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1/**`
- 本卡

原 architecture evidence與 Review evidence為 immutable evidence，不得修改。

## Forbidden scope

- 不修改 `scripts/**`、`tests/**`、config、plist、model、ranking、baseline或
  production artifacts。
- 不 merge/cherry-pick rejected candidate `acd835df…`。
- 不操作 LaunchAgent、queue、retry state、scheduler、live receipts或 acceptance。
- 不修改原 Review findings，不建立新 Reviewer，不自行 GO。
- 不開新 chain、不建立 Implementation 卡、不 push/merge/deploy。

## Phase 0 red evidence

修改 architecture前，Repair evidence必須先記錄 candidate現況的三個 RED：

1. 休市日合法 source-date case被 invariant拒絕；
2. I1–I5 allowlist缺少前鏈 safety modules/tests；
3. receipt v3無完整 closed key/type manifest與 canonical complete fixture。

紅燈證據是 contract comparison，不得執行或修改 production runtime。

## Verification

至少執行：

```bash
cd <repo-root>
python3 -m json.tool \
  docs/architecture/fog_runtime_receipt_v3.schema.json >/dev/null
rg -n \
  'market_run_date|artifact_run_date|daily_source_date|source_trade_date' \
  docs/architecture/fog_runtime_time_authority_v1.md
rg -n \
  'additionalProperties|required|queue_owner|runner_identity|state_transition|production_impact' \
  docs/architecture/fog_runtime_receipt_v3.schema.json
git diff --check
```

另需驗證：

- exact changed-file allowlist；
- schema所有 object nodes皆 closed；
- required keys唯一且實際存在於 properties；
- canonical fixture能依 schema contract逐欄對照；
- v2 mapping沒有補造 authority；
- 三個 finding before→after mapping；
- predecessor `RRV-P1-01`、`RRV-P1-03`與 time regression IDs皆進 successor
  test/allowlist；
- 無本機絕對路徑、secret、live/prod mutation。

## Delivery與targeted re-review

- Repair只交付 `DELIVERED_REPAIR_1_CANDIDATE` 與完整 SHA。
- 修後回原 Reviewer task
  `019fa448-4ffe-7473-af1a-7cc1f417bdd7`。
- Reviewer只可 targeted re-review `FRTA-P1-01/02/03`與 Repair regression；
  不得新增一般 finding或移動球門。
- GO 才授權主線 acceptance architecture並建立 Implementation卡。
- NO_GO 則同一 Repair task可進 Repair-2；strict上限為 Repair-2，禁止
  Repair-3。

## Pre-dispatch receipt

- Current card：
  `docs/tasks/2026-07-28_FOG-RUNTIME-TIME-AUTHORITY-01_REPAIR-1_contract_closure.md`
- Mainline dispatcher：
  `019f82c1-b7d0-7eb3-9371-7a95ebfbd7ce`
- Previous card／task：
  `REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01`／
  `019fa448-4ffe-7473-af1a-7cc1f417bdd7`
- Source kind：`commit`
- Source SHA：`3102e13`
- Source branch：`codex/fog-runtime-time-authority-review`
- Source clean：是
- Git metadata：可用
- unrelated dirty paths：`[]`
- Client receipt：
  `client-new-thread:ee300c7b-d1ed-4f39-a0e0-d62cca950d52`
- Repair task：`019fa471-2a58-7690-951d-9be2a2a4ca97`
- Repair title：`修復 FOG runtime time authority`
- Repair worktree：isolated／registered
- Repair initial HEAD：
  `5ffc0a33874fe742ba7ffa2170ad6236612817e4`
- Repair initial branch：`detached`
- Repair initial worktree：clean
- Capability preflight：task內執行中；worktree provisioning已 `PASS`
- Workflow：
  `REVIEW_NO_GO → REPAIR_READY`
- Gate 1 card contract：`PASS`
- Gate 2 visible thread：`PASS`
- Gate 3 Repair delivery：`PENDING`
- Gate 4 targeted re-review：`PENDING`
- Gate 5 implementation authorization：`DENIED_UNTIL_REVIEW_GO`

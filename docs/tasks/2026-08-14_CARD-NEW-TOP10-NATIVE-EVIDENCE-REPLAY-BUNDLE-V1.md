---
id: CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: delivered_candidate
type: evidence-replay
priority: P1
owner: TOP10new research platform
role: evidence
cycle: 6
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: 需重跑已驗證的 development-only 真實週期並固化可重算證據，規格固定但證據與容量契約嚴格。
date: 2026-08-14
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
canonical_queue_change_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/
---

# 固化 Native Evidence Replay Bundle

## 工作名稱

重跑已驗證的兩個 development-only native evidence 週期，保存可提交、可重算的小型證據包。

## 背景

- Card B thread `01a000d1-e6c9-7b51-89d0-f3198d0e2544` 已合法回報 `BLOCKED_EVIDENCE_NOT_REPRODUCIBLE`。
- 已提交的 activation summary 只有週期 counts 與 SHA，沒有 observation／evidence IDs、lineage、matched contrasts、official eligibility 與 learning projection。
- 原 isolated canary root 已依 cleanup drill 回收；現存 `data/research/research_ledger.duckdb` 不含該 canary execution units／observations。
- 使用者已核准直接跑，不等待長週期；本卡只重跑先前約數秒完成的 bounded development-only canary。

## Root question

能否用既有正式入口重跑兩個 real development-only cycles，並在不保留大型 isolated DB、不碰 production surface 的前提下，產生 Card B 可重算的 immutable replay bundle？

## 允許修改

- `app/research/native_evidence_activation.py` 的 evidence export／verification 直接相關 bounded 變更。
- 必要的 `scripts/` 小型 export／verify CLI。
- 對應 targeted tests。
- `docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/`。
- 本卡狀態與證據索引。

## 禁止修改

- `artifacts/autonomous_research/next_action_queue.json`、manager selection、quota、rerun、cooldown。
- Production ranking、signals、LightGBM、promotion、scheduler、launchd、背景服務。
- 主工作區既有 232MB ledger 與現存 projections；本卡必須用獨立 temporary root。
- Sealed、unknown、legacy、synthetic evidence 不得寫入正向 bundle。
- 不得提交 DuckDB、cache、raw 大型 corpus、絕對路徑或秘密資訊。
- 使用者 dirty files與既有 `.work/**`。

## Functional contracts

### `NERB-FR-001`｜Exact replay boundary

- 只用既有正式 native evidence runner，重跑與 activation summary 相同的 2 個 representative cycles。
- 每 cycle 必須 `SUCCEEDED / OBSERVED / EXACT`；execution units 必須 `VALID / PROVEN_NON_SEALED`。
- 第二次 ingest 必須增量 0；任一失敗即 `NO-GO`。

### `NERB-FR-002`｜Reproducible compact bundle

- Bundle 至少包含：cycle identity、receipt identity、execution unit、observation/evidence ID、lineage、scope、parameter、action、trial spec、result metrics、eligibility decision/reasons、learning inputs、matched contrasts與 policy/catalog hashes。
- 所有 identity、semantic hash 與排序 deterministic；禁止把 generated_at 放入 identity。
- 只保存 Card B admission 與 provenance 重算所需欄位，不提交完整 DB。

### `NERB-FR-003`｜Independent recomputation

- Verifier 必須從 bundle 重算 counts、lineages、contrasts、eligibility／learning semantic hashes。
- 至少有一組 parameter/scope 達到 `>=3` matched catalog-adjacent contrasts與 `>=2` distinct lineages；否則合法輸出 `NO-GO_INSUFFICIENT_EVIDENCE`，不得造資料。
- Tamper、missing row、duplicate identity、sealed／unknown、hash mismatch fixtures 必須 fail closed。

### `NERB-FR-004`｜Parity and cleanup

- Canonical queue、production、scheduler與主 ledger before/after hashes不變。
- Temporary root 容量在既有 policy budget內；保存 bundle 後回收 isolated DB／raw corpus。
- Cleanup 後 verifier 仍須只靠 committed-format bundle通過。

## 執行切片

1. `NERB-SLICE-001`：鎖 exact runner、輸出 schema、parity hashes與負向 fixtures。
2. `NERB-SLICE-002`：跑兩個 bounded real cycles，輸出 compact bundle。
3. `NERB-SLICE-003`：獨立 verifier、二跑 deterministic proof、tamper matrix。
4. `NERB-SLICE-004`：容量、cleanup、affected tests、`git diff --check`、candidate commit。

## 驗收

- 2 cycles、8 或實際 official runner 產生的 valid units全數可追溯；不得硬編 counts。
- Eligibility／learning projection可由 bundle獨立重算。
- Bundle與 manifest皆為 repo-relative、JSON 可解析、小型可提交 artifact。
- Canonical queue、production、scheduler、主 ledger hash零變更。
- Targeted tests、verifier、py_compile、JSON validation、`git diff --check` 全綠。
- 交付 `DELIVERED_CANDIDATE` commit；不得 merge、push、deploy或啟 scheduler。

## Stop conditions

- 正式 runner 無法重現 positive observations：回 `BLOCKED_REAL_REPLAY_FAILED`。
- 必須碰 production、canonical queue、scheduler或主 ledger才能成功：回 `BLOCKED_SCOPE_VIOLATION`。
- 真實輸出不足 contrasts／lineages：回 `NO-GO_INSUFFICIENT_EVIDENCE`，仍可提交完整負向 bundle與 verifier，但不得聲稱 Card B ready。
- 容量或 cleanup gate失敗：立即停止，不再跑下一 cycle。

## Deliverable

- Candidate commit SHA。
- Bundle／manifest／verifier／tests 路徑。
- 實際 cycle、unit、eligibility、lineage、contrast counts。
- Parity與cleanup receipt。
- 明示：未 merge、未 push、未 production mutation。

## 交付結果

- Bundle：`docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/bundle.json`。
- Manifest／parity／cleanup receipt：`docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/manifest.json`。
- Verifier：`app/research/native_evidence_replay.py` 與 `scripts/native_evidence_replay_bundle.py --verify`。
- Focused tests：`tests/test_native_evidence_replay.py`。
- 實際結果：2 cycles、8 valid units、8 adaptive-eligible observations、4 distinct lineages、4 matched contrasts；admission `PASS`。
- 邊界：未 merge、未 push、未 deploy、未啟 scheduler，canonical queue／production／主 ledger 零變更。

# CARD-ME-D1-DAILY-CLOSE-SNAPSHOT-01

狀態：`MAINLINE_ACCEPTED_LOCAL / NON_PRODUCTION`

Owner admission：2026-09-07 本對話明確指示 Fog 留在原對話，ME-D1「開工」。

## Root question

既有 FetchStage、validation snapshot 與 DatasetBundle seams，能否在不新增 Market Evidence subsystem 的前提下，形成可重現、可稽核的 finalized Daily Close immutable `DatasetSnapshot`，並把其 fingerprint 接入既有 trial lineage？

## 使用者需求

### Daily Close snapshot <!-- US-001 -->

系統必須在 enrichment 前固定 provider-neutral Daily Close input truth，並讓後續研究可以定位 exact immutable snapshot。

- **FR-001**：正規化 instrument、market、trading date、OHLCV/value，明示 price basis 與 finalized EOD 語意。 <!-- FR-001 traces_to: US-001 -->
- **FR-002**：以 deterministic canonical records fingerprint 建立 immutable snapshot data 與 manifest；相同完整輸入契約產生相同 identity。 <!-- FR-002 traces_to: US-001 -->
- **FR-003**：missing、duplicate、OHLC invariant、business-day gap 與 partial-market 狀態必須 fail loud 或結構化保存，不得 silent `0`／silent drift。 <!-- FR-003 traces_to: US-001 -->
- **FR-004**：FetchStage 必須先物化並重新讀取固定 snapshot，再交給既有 filter／FinMind／indicator stages；validation-only provider seam 必須保持相容。 <!-- FR-004 traces_to: US-001 -->
- **FR-005**：既有 DatasetBundle／attempt／receipt lineage 必須能綁定 exact Daily Close snapshot fingerprint；不建立第二套 registry／ledger。 <!-- FR-005 traces_to: US-001 -->

1. **Given** 同一組 Daily Close rows 與同一 provenance，**When** 重建 snapshot，**Then** canonical records fingerprint 與 snapshot identity 相同。 <!-- AS-US001-01 traces_to: FR-001, FR-002 -->
2. **Given** duplicate key、invalid OHLC、null required value 或 price-basis drift，**When** 建立或載入 snapshot，**Then** 明確拒絕且不產生可消費 snapshot。 <!-- AS-US001-02 traces_to: FR-001, FR-003 -->
3. **Given** business-day 或單一市場無 observation，**When** 建立 manifest，**Then** gap／partial-market evidence 可機器判讀，且不捏造成休市或成功。 <!-- AS-US001-03 traces_to: FR-003 -->
4. **Given** FetchStage 的代表性離線輸入，**When** 執行 canonical downstream pipeline，**Then** 固定 snapshot 被消費，輸出與 snapshot 前原始 rows 在既有轉換邊界等價。 <!-- AS-US001-04 traces_to: FR-004 -->
5. **Given** 已驗證 Daily Close manifest，**When** 建立 strategy-matrix DatasetBundle，**Then** bundle identity 含 exact Daily Close snapshot content ID，requested／executed receipt 可重建相同 lineage。 <!-- AS-US001-05 traces_to: FR-005 -->

- **SC-001**：canonical Research Matrix dimension growth=`0`；Research Spine、backtest math、ranking 與 publish authority不變。 <!-- SC-001 traces_to: US-001, FR-005 -->
- **SC-002**：新增 deterministic unit／integration tests 全綠，並以一份既有 parquet 做唯讀代表性驗證。 <!-- SC-002 traces_to: US-001, FR-001, FR-002, FR-003, FR-004, FR-005 -->
- **SC-003**：`git diff --check` 通過，diff 僅限本卡。 <!-- SC-003 traces_to: US-001 -->

## Guardrails

- `EXTEND_EXISTING > ADD_SUBSYSTEM`。
- 不做 intraday、live、多 provider resolver／fallback／repair、broker、第二套 registry／ledger／scheduler。
- 不改 Research Matrix 維度、backtest math、ranking、publish、scheduler 或 production runtime。
- 本卡不授權 merge、push、deploy 或外部 write。
- Fog 完全不在本卡 scope。

## 垂直切片與依賴

| Slice | Scope | traces_to | Blocking edge | Verification |
|---|---|---|---|---|
| `ME-D1-SLICE-001` | Daily Close contract、canonicalization、immutable materializer／loader | `FR-001`–`FR-003`, `AS-US001-01`–`03` | 無；目前 frontier | unit tests |
| `ME-D1-SLICE-002` | FetchStage snapshot handoff 與 validation seam compatibility | `FR-004`, `AS-US001-04` | `ME-D1-SLICE-001` | pipeline integration test |
| `ME-D1-SLICE-003` | DatasetBundle versioned Daily Close component 與 requested／executed lineage | `FR-005`, `AS-US001-05`, `SC-001` | `ME-D1-SLICE-001` | bundle／receipt tests |
| `ME-D1-SLICE-004` | 代表性 parquet 對帳、receipt、文件狀態 reconciliation | `SC-002`, `SC-003` | `ME-D1-SLICE-002`, `ME-D1-SLICE-003` | read-only real-data check＋targeted suite＋diff gate |

Checkpoint：完成 `SLICE-001` 後先驗 contract；完成 `SLICE-002/003` 後跑整合與 lineage regression，再進 acceptance。

## Likely files

- `app/pipeline/daily_close_snapshot.py`
- `app/pipeline/fetch_stage.py`
- `app/research/dataset_bundle.py`
- `app/research/run_receipts.py`
- `tests/test_daily_close_snapshot.py`
- `tests/test_validation_snapshot_adapter.py`
- `tests/test_research_dataset_bundle.py`
- `tests/test_autonomous_research_receipts.py`

## Evidence

- `docs/evidence/ME-D1-DAILY-CLOSE-SEAM-AUDIT-20260907.md`
- `docs/evidence/ME-D1-DAILY-CLOSE-SNAPSHOT-IMPLEMENTATION-20260907.md`
- `.work/CARD-ME-D1-DAILY-CLOSE-SNAPSHOT-01/review/review_state.jsonl`
- `.work/CARD-ME-D1-DAILY-CLOSE-SNAPSHOT-01/evidence/`

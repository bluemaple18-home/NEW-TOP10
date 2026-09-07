# Repair generation 1 — CARD-ME-D1-DAILY-CLOSE-SNAPSHOT-01

直接修復 `.work/CARD-ME-D1-DAILY-CLOSE-SNAPSHOT-01/review/review_state.jsonl` 的 `ME-D1-REV-001..004`。請先讀原卡、review state、目前 diff 與相關 tests。修改共享 workspace 的 code／tests；不要修改 docs、`.work`、review state 或本 task file；不 commit／push／連外。

TDD：一次建立一個 red-capable public-behavior test，實際確認因目標症狀 RED，再做最小修復轉 GREEN。最後一併跑完整 focused/regression tests。

## 固定 findings 與修復邊界

1. `ME-D1-REV-001 P1`：snapshot handoff 丟掉既有 `transactions`。把它納入明確 nullable Daily Close records contract；缺值保持 null、存在時必須 finite/non-negative，不得補 0。整合測試要證明既有 downstream-consumed欄位完整保留，不可只比較 snapshot 子集合。不要泛化保留任意未知欄位。
2. `ME-D1-REV-002 P1`：無 authority 就宣告 `FINALIZED_EOD`。新增可驗證、deterministic 的 finalization gate：
   - `fetched_at` 早於 observed trading date 一律拒絕；
   - 若 latest observed date 等於 `fetched_at` 的 Asia/Taipei 日期，只有跨過保守且版本化的 official Daily Close cutoff 才可 finalized；收盤前同日資料必須 RED→拒絕；
   - 歷史日期可由 official finalized-daily endpoint contract＋fetched time證明；
   - manifest 明示 observation/observed-at policy、timezone、cutoff/version 與 observed-through date，不靠未記錄的預設常數。
3. `ME-D1-REV-003 P1`：receipt 無法反查 snapshot。把 manifest 與 records 發布進**既有 research corpus** 的 immutable artifact namespace，並在 versioned `DAILY_CLOSE_SNAPSHOT` DatasetBundle component 保存 corpus-relative content-addressed `manifest_ref`／`records_ref`。不得保存任意 absolute path作 authority、不得建 registry／ledger。新增 public round-trip test：從持久化 receipt→DatasetBundle→component ref→載入 exact snapshot，即使原 CLI snapshot root 被移除，仍可重建。
4. `ME-D1-REV-004`＋主線代表性量測：現行 516,169 rows 產生 88,882,274-byte nested JSON，物化 16.09s、reload 6.482s、macOS peak RSS 1,587,429,376 bytes。移除 full nested-list serialization；records 改為串流 canonical、壓縮且 byte-deterministic 的 immutable格式（例如 fixed-metadata JSONL gzip）與 incremental SHA-256，loader 也不得重建完整 nested dict list。保留 collision fail-closed。新增適度規模測試，主線會再跑 516k-row acceptance。

另確認原 handoff 最小契約的 `observed_at / fetched_at`：可用 day-precision observed-at contract＋exact fetched_at，但必須在 manifest 明示且驗證。

允許修改：

- `app/pipeline/daily_close_snapshot.py`
- `app/pipeline/fetch_stage.py`
- `app/research/dataset_bundle.py`
- `app/research/run_receipts.py`
- `scripts/run_autonomous_research.py`（只限既有 optional plumbing）
- `tests/test_daily_close_snapshot.py`
- `tests/test_validation_snapshot_adapter.py`
- `tests/test_research_dataset_bundle.py`
- `tests/test_autonomous_research_receipts.py`

驗證：

- 新 RED/GREEN tests。
- `.venv/bin/pytest -q tests/test_daily_close_snapshot.py tests/test_validation_snapshot_adapter.py tests/test_research_dataset_bundle.py tests/test_autonomous_research_receipts.py`
- `.venv/bin/pytest -q tests/test_research_spine_contracts.py tests/test_research_spine_daily_cutover.py tests/test_forecast_contracts.py tests/test_forecast_fixture.py`
- `.venv/bin/python scripts/run_autonomous_research.py --help`
- `git diff --check`

若固定 format 或 corpus locator 無法在 allowlist 內成立，停止並回報 contract fork，不自行擴檔。

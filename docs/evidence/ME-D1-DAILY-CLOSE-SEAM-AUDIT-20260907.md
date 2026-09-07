# ME-D1 Daily Close Seam Audit

狀態：`MEASURED_GAP_CONFIRMED / READY_FOR_OWNER_ADMISSION_DECISION / NOT_ADMITTED`

固定證據基線：`f787437e2c88a327ad7be210f31d790fa96ee3f7`

## Root question 與邊界

現有 NEW-TOP10 是否已具備足以延伸成 ME-D1 第一個 bounded slice 的 Daily Close data/evidence seam，而不新增完整 Market Evidence subsystem？

本次只讀取 source、測試、設定與本機既有 parquet；不連外、不抓資料、不改 runtime、不准入 ME-D1 implementation。

## 現行資料流

```text
app.pipeline_cli
  → FetchStage
  → DataFetcherOrchestrator
      → AsyncTWSEFetcher / AsyncTPEXFetcher
  → tradable-universe filter + deterministic trade-key dedupe
  → IndicatorStage / FundamentalStage
  → EventStage
      → data/clean/features.parquet
      → data/clean/events.parquet
  → FilterStage
      → data/clean/universe.parquet
  → research DatasetBundle 以 features artifact SHA-256 綁定下游 trial
```

另有 `app/pipeline/validation_snapshot.py`：它能讀取 digest-pinned CSV/parquet、驗必要欄位、值域、日期窗口與 TWSE/TPEX 覆蓋，並只替換 `FetchStage` 的 provider acquisition；但目前只由 storage validation mode 使用，不是 production Daily Close snapshot owner。

## 已觀測資料事實

`data/clean/features.parquet`：

- 516,169 rows、1,967 stocks、282 trade dates，範圍 2025-07-08 至 2026-09-01。
- `(date, stock_id)` null=0、duplicate=0。
- latest date 1,930 rows：TWSE 1,072、TPEX 858。
- OHLCV/value null=0，`low <= open/close <= high` 違反=0。
- SHA-256=`aab60603280ae3d2a603b705ab02c5b19f518dcf178080482b2500b221f954ce`。

`events.parquet` 與 features keys 完全相等；`universe.parquet` 是 features key 的子集合，沒有額外 key。

既有 `PipelineDataValidator` 對三個 clean parquet 回 `ok=true / ERROR=0 / WARN=4`。四個 warning 都在 features 最新日長週期指標覆蓋，其中 TPEX 的 `ma20` 與 `bb_middle` 只有 0.1%，但 validator 仍允許整體 pipeline 通過。這是 downstream feature completeness 事實，不等同 Daily Close base fields 缺漏。

## Contract 對照

| ME-D1 最小語意 | 現況 | 判定 |
|---|---|---|
| instrument / trading date / OHLCV | `stock_id`、`market`、`date`、OHLCV/value 已存在 | `EXISTS` |
| missing / duplicate / OHLC invariant | final parquet validator 與 validation snapshot 已有部分 deterministic checks | `PARTIAL_EXISTS` |
| immutable dataset fingerprint | Research DatasetBundle 可綁 `features.parquet` SHA-256 | `DOWNSTREAM_ONLY` |
| provider-neutral Daily Close snapshot | production fetch 後直接進 enrichment，只保存 clean feature parquet | `MISSING` |
| source/provider identity與版本 | row 只有市場別；沒有 exact endpoint／provider version／fetch receipt | `MISSING` |
| observed_at / fetched_at | clean parquet 與 DatasetBundle 未承載 | `MISSING` |
| finalization status | 沒有可機器判讀的 finalized EOD 欄位 | `MISSING` |
| price basis / adjustment policy | 未明示 raw／adjusted policy | `MISSING` |
| calendar / gap semantics | fetch 使用 business-day range；失敗或休市日只是不產 row，沒有 gap manifest | `MISSING` |
| lineage to exact trial input | trial 可追到 features artifact hash，但不能追到 immutable Daily Close source snapshot | `PARTIAL` |

## Measured gap

1. `DataFetcherOrchestrator.data_dir` 目前只建目錄；TWSE/TPEX Daily Close response 沒有被物化成 immutable source snapshot。
2. 每日 source log 只留在 fetcher process memory；未保存 fetched time、endpoint/version、成功／缺市場、finalization 或 limitation evidence。
3. `features.parquet` 同時混合行情、技術指標、FinMind／融資券與基本面欄位，不能充當 provider-neutral Daily Close truth。
4. validation snapshot 已提供可延伸的 strict input seam，但 production path 未使用它作 canonical handoff。
5. Research DatasetBundle 已提供 content-addressed downstream identity，但目前 identity 是 enriched features artifact；strategy-matrix coverage 仍使用 placeholder 1970 dates 與 zero git blob identity，不能替 Daily Close provenance 背書。
6. production fetch 允許單日單一市場失敗後繼續聚合；後續只驗 latest market coverage，缺少逐日 gap／partial-market evidence。

## Admission 建議

```text
MEASURED_GAP = CONFIRMED
REUSE = EXTEND_EXISTING
IMPLEMENTATION_AUTHORITY = NONE
ADMISSION_DECISION = PENDING_OWNER
```

若 Owner 後續明確 admission，最小充分 slice 應只做：

1. 將既有 TWSE/TPEX parser 輸出映射成 provider-neutral finalized Daily Close observation。
2. 在 enrichment 前產生 immutable DatasetSnapshot 與小型 manifest，至少固定 source、fetched_at、finalization、price basis、calendar/gap、missing/duplicate 與 content fingerprint。
3. 讓既有 FetchStage 消費固定 snapshot；不改 Research Matrix、backtest math、ranking 或 publish。
4. 把 DatasetSnapshot fingerprint 接到既有 DatasetBundle／trial lineage，而不是新增第二套 registry、ledger 或 scheduler。
5. 用同一份代表性 Daily Close input 做 deterministic bytes／identity、duplicate、gap、partial-market、raw-vs-adjusted drift 與下游等價測試。

## Why not less / why not more

- **why not less**：只繼續 hash `features.parquet` 無法重建「抓到的 Daily Close input truth」，也無法區分 provider 資料變動與 indicator/enrichment code 變動。
- **why not more**：既有 FetchStage、validation snapshot、parquet validation 與 DatasetBundle 已涵蓋大部分必要 seam；目前沒有證據需要 multi-provider resolver、live freshness、repair runtime、broker、intraday 或完整 Market Evidence Plane。

## 結論

ME-D1 具體缺口已成立，且可沿既有 seam 做 bounded extension；但本 audit 只把 #17 推到 `READY_FOR_OWNER_ADMISSION_DECISION`。在 Owner 明確裁決前，不得建立 implementation card 或修改 code/runtime。

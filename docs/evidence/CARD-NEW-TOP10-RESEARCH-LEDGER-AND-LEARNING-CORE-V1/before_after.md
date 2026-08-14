# Research Ledger & Learning Core｜Before / After

## Before

- `run_history.json/jsonl` 同時承擔營運、coverage 與研究 evidence，identity 粒度混合。
- Daily backfill 需從 filesystem artifact 反推已執行事實。
- 沒有 immutable requested/executed receipt，也沒有 sealed fail-closed eligibility。
- Parameter comparison 以 winner/delta 為主，沒有 matched learning contract。

## After

- Canonical lifecycle：`TrialSpec → Intent → AttemptStarted → RunReceipt`。
- Source bytes、matrix、migration mapping 進 immutable CAS；DuckDB 可刪除重建。
- Legacy records 逐筆分類，不能因數量或檔名升格成 adaptive evidence。
- Eligibility、failure、matched learning 都有 versioned policy 與 immutable projection。
- Daily runner owner、選題、quota 保持；原生 receipt 先驗證、ingest，再產 Fog compatibility projection。

## Unchanged

- Fog Map UI 與 coverage universe。
- Autonomous Research scheduler owner。
- Production ranking、LightGBM model、signals、promotion gates。

## Rollback

- Card A projection皆可停止消費；DuckDB可整檔刪除。
- Daily shell可恢復 legacy compatibility refresh；immutable receipts保留，不需刪除。
- `adaptive_search.enabled=false` 的未來開關不影響本卡，因本卡沒有 adaptive queue。

## Known limitations

- Legacy lineage多數只能 diagnostic。
- 真實 native corpus可能仍為零 eligible；synthetic tests只證明算法。
- 單一 regime 不得泛化成 global。
- Optuna、dynamic refinement、dashboard、Card B shadow queue均未施工。

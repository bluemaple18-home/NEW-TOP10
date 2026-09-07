---
id: RADAR-01-P1-D-CONTEXT
status: context-ready
type: context-manifest
---

# Context manifest

- CodeGraph indexed HEAD：`23401329f9ffea56b99765f821c29eb57e17caf7`
- Graph query：RADAR-01 P1-D historical statistics／relevant base rate，入口確認為 `app/signals/occurrences.py`、`app/signals/scanner.py`、`app/signals/specs.py` 與 `app/pipeline/daily_close_snapshot.py`。
- Source confirmation：P1-B exact snapshot/feature validation seam、P1-A eligibility/evaluation horizon、P1-C occurrence projection與 Daily Close `UNADJUSTED` price basis 已直接查讀。
- Data fact：`data/clean/features.parquet` 直接量測 516,169 rows、1,967 stocks、2025-07-08～2026-09-01、TWSE/TPEX、duplicate key=0、invalid close=0。

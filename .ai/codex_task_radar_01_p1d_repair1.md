# RADAR-01 P1-D Repair 1

- 目標：只修 `RADAR-P1D-STRICT-001`；先讀 `docs/tasks/2026-09-07_REPAIR-RADAR-01-P1-D-G1-STABLE-PUBLIC-ERRORS.md` 與原 task card。
- 允許：`app/signals/historical_statistics.py`、`tests/test_signal_historical_statistics.py`；加 overlap/path/iterable 三條 public RED/GREEN。
- 禁止：改統計/base-rate/effective-N/MAE/scanner、擴 scope、commit、push、deploy。
- 原則：在 public boundary 精準 normalize；只 catch 外部 iterable materialization，不 broad-catch 內部 pandas/numpy bug。
- 驗收：`/tmp/radar_p1d_review_red.py` exit 0、targeted+regression tests 綠、git diff/check 綠，回報 changed lines 與 reason codes。

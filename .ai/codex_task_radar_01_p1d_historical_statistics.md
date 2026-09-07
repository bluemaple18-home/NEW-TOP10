# RADAR-01 P1-D strict implementation task

- 目標：依 `docs/tasks/2026-09-07_CARD-RADAR-01-P1-D-HISTORICAL-STATISTICS-BASE-RATE.md` 完成 evidence-backed historical signal statistics 與 relevant base-rate in-memory projection。
- 允許：`app/signals/historical_statistics.py`、必要時對 `app/signals/scanner.py` 做最小 shared validation seam 抽取、`app/signals/__init__.py`、`tests/test_signal_historical_statistics.py`；先 RED 再 GREEN。
- 禁止：修改 default SignalSpec eligibility、Existing Backtest Engine、Research Ledger/Matrix、ranking、P1-E、Fog、runtime、API/UI、writer/persistence、push/deploy；暫不更新 canonical backlog/frontier/evidence acceptance（由 Mainline 驗收後處理）。
- 契約：UNADJUSTED close 的 per-instrument H-session direction-adjusted price return；baseline 固定同 snapshot/universe/window/horizon/direction；tail/unobservable/overlap 全部可觀測；immutable content-addressed；stable reason codes；default zero eligible。
- 驗收：P1-D targeted tests 加 P1-A～P1-C regression 全綠、deterministic recompute、malformed/tamper fail-closed；列出改檔與剩餘風險，不 commit、不 push、不 deploy。

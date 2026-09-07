# RADAR-01 P1-C implementation worker

目標：依 `docs/tasks/2026-09-07_CARD-RADAR-01-P1-C-SIGNAL-OCCURRENCE-RADAR-PROJECTION.md` 實作 content-addressed `SignalOccurrence` 與 deterministic no-score/no-rank Daily Radar projection。

限制：只消費已驗證 `DailySignalScanReport`、exact ME-D1 manifest 與 exact `RADAR_ELIGIBLE` SignalSpec；重新驗證 report/snapshot/spec/count/hit invariants；occurrence 只代表 `TRIGGERED`；沿用 `app.research.contracts.content_hash`；所有輸出 frozen/in-memory。validation-only eligible specs 不得回寫 catalog。

可改檔案：`app/signals/occurrences.py`、`app/signals/radar_projection.py`、`app/signals/__init__.py`、`tests/test_signal_occurrence_radar_projection.py`。可讀其他 repo 檔案；不可修改允許清單外任何檔案。

不可改：scanner/spec/daily-close 現有契約、Research Spine/Matrix、ranking/scoring、statistics/base-rate、confluence、DB/writer/persistence、UI/API/runtime/scheduler/provider/Fog、docs、git history、push/deploy/production。

驗收：卡片 AS-US001-01～07 與 SC-001 source 部分；先 RED 再 GREEN；stable reason codes；相同 inputs 產生相同 occurrence/projection IDs；default catalog 輸出 no-eligible；tampered report fail closed；`ranking_impact` 固定 `NONE`；執行 `.venv/bin/python -m pytest tests/test_signal_occurrence_radar_projection.py tests/test_daily_signal_scanner.py tests/test_signal_specs.py -q` 與 `git diff --check`。完成時只回報 changed files、test output、已知 residual risk；不得 commit。

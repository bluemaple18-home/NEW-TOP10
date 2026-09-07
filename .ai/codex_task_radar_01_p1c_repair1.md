# RADAR-01 P1-C Repair generation 1

目標：依 `docs/tasks/2026-09-07_REPAIR-RADAR-01-P1-C-G1-INTEGRITY.md` 關閉 Reviewer 的 P1-F001～F003；只做 bounded repair。

可改：`app/signals/occurrences.py`、必要時 `app/signals/radar_projection.py`、`app/signals/__init__.py`、`tests/test_signal_occurrence_radar_projection.py`。不可改其他檔案；不得 commit/push/deploy。

必要修復：
1. 在讀取 nested 欄位、regex、enum `.value`、iteration 或比較前，集中驗證 `DailySignalScanReport`、`DailySignalScanStatus`、counts exact int（bool 禁止）、tuple containers、每個 `DailySignalScanSummary`／`DailySignalScanHit`／`DailySignalScanWarning` exact type與欄位；malformed 一律 stable `SignalOccurrenceError`。
2. 每個 hit 的非空字串 `stock_id` 必須存在 exact loaded snapshot 的 report.scan_date rows；outside/empty/non-string fail closed。
3. 移除 occurrence 暴露的 mutable `endpoint_contract` mapping。保留 immutable scalar `provider_identity`、`adapter_contract`，並新增綁定完整 source/endpoint semantics 的 SHA-256 provenance content ID；所有 occurrence fields 都必須深層不可變且 ID 可重算。
4. 先補 RED 再 GREEN：outside/empty/non-string instrument、mutable provenance、None hash/ref、string status、bool eligible/summary/warning counts、wrong summary/hit/warning objects、invalid warning fields。

驗證：`.venv/bin/python -m pytest tests/test_signal_occurrence_radar_projection.py tests/test_daily_signal_scanner.py tests/test_signal_specs.py -q`、`git diff --check`；回報 changed files/tests/residual，不得擴到 statistics/base-rate/confluence/ranking/UI/API/runtime/Fog。

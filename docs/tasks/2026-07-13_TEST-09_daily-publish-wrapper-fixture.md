# TEST-09｜Daily Publish Wrapper Fixture 修復

- status: ready
- priority: P0
- task thickness: strict

## 根因與 RED

- red-capable command：`.venv/bin/python scripts/verify_daily_publish_wrapper_guards.py`
- 現象：`catch_up_date_reaches_sender` 的 wrapper exit 為 2。
- 已定位：fake project 未提供 wrapper 新增依賴 `record_top10_publish_event.py` 與 `send_top10_ops_report.py`，不是 live wrapper 本體錯誤。
- 可證偽假說：若只補齊兩個可觀測 stub，兩個既有 case 應轉綠；若仍失敗，才檢查下一個 wrapper contract，不得先改 production wrapper。

## 依賴與 frontier

- blocker：無。
- frontier：可立即開工。

## 可改檔案

- `scripts/verify_daily_publish_wrapper_guards.py`
- `tests/test_daily_publish_wrapper_guards.py`（可新增）
- 本卡 status/result

## 不可改

- `scripts/run_daily_publish.sh`、`scripts/run_daily.sh`
- send／event／ops production scripts
- config、plist、artifacts、通知設定
- 不得 live send

## 實作契約

1. 在 fake project 建立最小 event／ops stub，記錄 argv 與 exit code；不得複製整個 production dependency tree。
2. 既有 send failure 必須保留原 send exit code 7；event/ops stub 不得掩蓋。
3. catch-up success 必須 exit 0，且 sender、event、ops 都收到 `--allow-stale-send` 或正確 run-date 契約。
4. 加 public CLI regression test；失敗輸出仍保留完整 evidence。
5. 清除任何 debug instrumentation。

## 驗收

- 原 RED command 轉綠，兩個 cases failed_count=0。
- 新 regression tests 通過。
- live wrapper hash 不變。
- `git diff --check` 通過。

## 回報

建立單一 atomic commit；回報 SHA、RED→GREEN 證據與剩餘風險，不 merge、不 push、不 send。

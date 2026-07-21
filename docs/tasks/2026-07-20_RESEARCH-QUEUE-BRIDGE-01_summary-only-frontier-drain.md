---
id: RESEARCH-QUEUE-BRIDGE-01
status: DONE
type: implementation
risk: medium
---

# RESEARCH-QUEUE-BRIDGE-01：打通 summary-only frontier drain

## Root question

如何在不重新輸出 1GB+ full-record inventory 的前提下，讓 controlled-grid worker 持續消化尚未執行的 representative replay？

## 已確認 blocker

- `weekend_universe_inventory_2026-07-20.json` 顯示 `2,836,291` 個 pending combo、`59,514` 個 `REPRESENTATIVE_REPLAY_REQUIRED`。
- summary-only inventory 設定 `records_inline=false`。
- `run_controlled_grid_drain_host_runner.py` 因此跳過 frontier queue 建構。
- `run_representative_replay_drain_worker.py` 只讀實體 frontier queue；檔案不存在時誤判 `queue_empty`。

## 目標契約

1. summary-only inventory 建構期間，利用記憶體中已分類的 rows 同步輸出最多 144 筆的 bounded frontier queue。
2. bounded queue 只包含當批可執行的 representative，不輸出完整 286 萬筆 records。
3. replay append run history 後重建 inventory／queue，下一批不得重選已完成 combo。
4. `queue_empty` 只可在 bounded queue 確實沒有 representative 時出現。
5. 全流程維持 research-only；不改 production ranking、不訓練模型、不 promotion。

## 驗收

- 回歸測試能重現「summary 有 backlog、實體 queue 為空」並在修復後轉綠。
- frontier queue verifier 同時支援 legacy full-record 與 bounded summary 模式。
- host runner 不再將 `build_frontier_queue` 標成 `SKIPPED`。
- 最小 replay smoke 至少選取一筆或在缺資料時明確回報 runner-level blocker，不得再假報 `queue_empty`。
- 受影響測試、`git diff --check` 通過；diff 不碰 production ranking、模型或 promotion。

## 邊界

- 不恢復日常 full-record JSON。
- 不修改目前工作樹內既有的 baseline harness／Chrome review 未提交變更。
- 不推送、不部署。

## 結果與證據

- bounded frontier queue：`144` 筆 active representatives，沒有輸出 full records。
- 真實 replay smoke：`completed_replay_count=1`、`appended_run_history_count=1`、`failed_batch_count=0`。
- 研究進度：`expanded_processed 30461 → 30462`；`representative_required_count 59514 → 59513`。
- host runner：`status=OK`；停止原因為 `max_batches_reached`，不再是 `queue_empty`。
- 回歸測試：7 tests passed，包含 required backlog 搭配空 bounded queue 必須失敗的負向案例。
- inventory、frontier queue、representative replay、rollup、fog map verifier：全部 `OK`。
- `py_compile`、`git diff --check`、debug marker scan：通過。

## 剩餘範圍

- 仍有 `59,513` 個 representative replay 待排程分批消化。
- `2,423,416` 個 `UNSUPPORTED_INPUT` 需由 baseline ranking／regime slice 資料卡另行解除，並非本 queue bridge 修復範圍。

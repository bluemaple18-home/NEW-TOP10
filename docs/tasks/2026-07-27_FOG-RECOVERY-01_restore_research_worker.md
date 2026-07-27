---
id: FOG-RECOVERY-01
status: READY_FOR_DISPATCH
type: implementation
owner: implementation-thread
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 跨 inventory、controlled-grid 與 worker recovery，但 production 邊界明確且可由 deterministic tests 驗證。
traces_to:
  - SC-FOG-RECOVERY-01
  - SC-FOG-RECOVERY-02
  - SC-FOG-RECOVERY-03
---

# FOG-RECOVERY-01：恢復迷霧研究 worker

## Root question

如何消除 weekend inventory 與 research map snapshot 的 2 筆時間差，讓 controlled-grid linkage 不再誤判失敗，並讓 retry circuit 只在根因修復且驗證通過後安全恢復？

## 已知證據

- `artifacts/weekend_training/weekend_universe_inventory_verification_latest.json`：
  - inventory `current_processed_count=33360`
  - source snapshot／latest map `expanded_processed=33358`
  - 3 個一致性 checks 失敗
- `logs/fog_research_retry_20260727.state`：同一 fingerprint 連續失敗 3 次，`circuit_open=1`
- `logs/fog_research_retry_20260727.context.log`：研究本體與 fog map build 為 OK；失敗發生在 controlled-grid host runner 的 inventory verification。
- `scripts/run_fog_research_worker.sh` 每 15 分鐘仍被喚醒，但 circuit open 時會安全跳過。

## 允許範圍

- `scripts/build_weekend_universe_inventory.py`
- `scripts/verify_weekend_universe_inventory.py`
- `scripts/run_controlled_grid_drain_host_runner.py`
- `scripts/run_fog_research_worker.sh`
- 與上述行為直接相關的新／既有 `tests/test_*.py`
- `docs/evidence/FOG-RECOVERY-01/**`
- 本卡的狀態／結果欄位

## 禁止範圍

- 不得修改 production ranking、模型檔、權重或 promotion 狀態。
- 不得刪除或覆寫既有 runtime artifacts、logs、retry state。
- 不得用放寬 verifier、忽略 2 筆差異、固定 sleep 或無限 retry 掩蓋 race。
- 不得執行 live publish、外部 AI、Discord、交易或其他外部 write。
- 不得在實作 thread 直接宣告 production recovery；只交付 candidate commit 與證據。

## 實作要求

1. 先建立能重現「source snapshot 在 inventory build 過程中前進」的失敗測試。
2. 找出 inventory 讀取多份會變動來源時的 snapshot 邊界，採取一致 snapshot、重新讀取／重建或明確 fail-loud 機制；不可容忍不一致值。
3. controlled-grid verifier 必須維持 fail-closed，真正 stale／不一致仍應失敗。
4. circuit recovery 必須是明確且安全的動作：只有根因 verification 通過後才允許清除／輪替相同 fingerprint；不得自動吞掉新 failure。
5. 更新或新增回歸測試，涵蓋成功、stale snapshot、連續相同 failure 與新 fingerprint。

## 驗收條件

- `SC-FOG-RECOVERY-01`：可重現 2 筆 race 的測試在修復前為紅、修復後為綠。
- `SC-FOG-RECOVERY-02`：inventory、source snapshot、latest map 使用同一一致性邊界；controlled-grid verifier 為 OK。
- `SC-FOG-RECOVERY-03`：circuit 不會在 blocker 未修時自動解除；修復後可由可稽核流程恢復下一輪 worker。
- 受影響測試、完整 `pytest -q`、shell syntax check 與 `git diff --check` 通過。
- 交付一個原子 candidate commit，附完整 SHA、changed files、驗證命令與輸出摘要。

## 證據路徑

- `docs/evidence/FOG-RECOVERY-01/verification.md`
- `docs/evidence/FOG-RECOVERY-01/result.md`

## 停損

- 同一 blocker 最多 3 次；第 3 次即停，不進行第 4 次。
- 若修復需要改 production contract、刪 runtime state、或無法建立 red-capable test，標記 `BLOCKED` 並交回主線。

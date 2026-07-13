---
id: REFACTOR-02
status: integrated
type: implementation
priority: P1
model: gpt-5.6-terra
---

# 研究 worker 狀態機與重試治理

## 目標

把研究 quota 從「最低完成量」改成「單批上限」，消除 partial queue 被誤判失敗後每 15 分鐘重跑的迴圈；研究流程不得影響每日報牌。

## 依賴與 frontier

- blocking edges：無。
- frontier：可立即開工。
- 與 REFACTOR-01 平行；不得修改 daily 正式主線。

## 可改範圍

- `scripts/verify_daily_research_quota.py`
- `scripts/run_daily_research_quota.sh`
- `scripts/run_fog_research_worker.sh`
- `scripts/run_pm_research_harness_loop.sh`
- `scripts/com.new-top10.fog-research-worker.plist`
- `scripts/com.new-top10.pm-research-harness.plist`
- 對應 `tests/test_*research*`。

## 不可改範圍

- `app/agent_b_ranking.py`
- `app/agent_b_modeling.py`
- `scripts/run_daily.sh`、`scripts/run_daily_publish.sh`
- `config/automation.yaml` 的 daily／notify 區段
- `models/`、`data/`、正式 ranking／report artifacts
- 不得啟動或重新載入 launchd；只提交程式與 plist 變更。

## 行為契約

1. 結果狀態至少區分 `COMPLETED`、`PARTIAL_NO_MORE_WORK`、`BLOCKED`、`FAILED`。
2. 0／1／3／5 個 topic 都有 deterministic 判定；quota=5 不代表必須湊滿 5。
3. 純拒絕證據仍是有效研究輸出，不得因數量不足變成 runtime failure。
4. 真失敗需有 bounded retry、退避、連續失敗熔斷與 failure fingerprint。
5. PM harness 與 fog worker 不得同時搶同一 queue；提出並實作單一 ownership。

## 驗收條件

- 先補 0／1／3／5 topics 的行為測試。
- partial queue 回傳成功狀態且 worker 不重啟同一批。
- 真失敗達 retry cap 後停手，保留錯誤上下文。
- shell 語法、對應 unittest、`git diff --check` 通過。

## 建議驗證

```bash
uv run python -m unittest tests.test_daily_research_quota_verifier
bash -n scripts/run_daily_research_quota.sh
bash -n scripts/run_fog_research_worker.sh
bash -n scripts/run_pm_research_harness_loop.sh
git diff --check
```

## 回報要求

- 新狀態表
- retry／熔斷規則
- 已驗證、未驗證、剩餘風險

## 主線整合結果

- 整合提交：`b59f4e8`
- 主線退修並重驗：共享鎖 contention、stale failure fingerprint、6 項 quota 狀態測試通過。
- 未 reload launchd；repo 內 plist 變更尚未套用到本機已載入服務。

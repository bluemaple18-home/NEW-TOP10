---
id: REFACTOR-01
status: integrated
type: implementation
priority: P1
model: gpt-5.6-sol
---

# 每日報牌 v2 契約與可續跑主線

## 目標

在不切換正式排程的前提下，建立可 shadow 執行的精簡主線：

`ETL → Validate → Rank → Report → Publish-ready`

每日正式報牌是唯一不可破壞契約。這張卡只建立 v2 與測試，不得啟用 live send。

## 依賴與 frontier

- blocking edges：無。
- frontier：可立即開工。
- 後續切換正式排程必須另開 integration／acceptance 卡。

## 可改範圍

- `app/workflows/` 新模組。
- `app/contracts/` 的 daily 契約新模組。
- `scripts/run_daily_v2.py` 或等價薄 CLI。
- `tests/test_daily_workflow_v2.py` 與必要測試 fixture。
- 本卡文件的 status／result。

## 不可改範圍

- `scripts/run_daily.sh`
- `scripts/run_daily_publish.sh`
- `scripts/com.new-top10.daily.plist`
- `config/automation.yaml` 的通知 live gate
- `models/`、`data/clean/`、既有正式 `artifacts/ranking_*.csv`
- 不得發送 Clawd／Discord，不得切換 production entrypoint。

## 行為契約

1. 每步有固定 input／output、started／finished／failed 狀態。
2. 子程序有 timeout；失敗帶 command、exit code、stderr 摘要。
3. run manifest 以 `run_id` 隔離並原子寫入。
4. 同一 `run_id` 可從最後成功步驟 resume，完成步驟不得重寫 production artifact。
5. 模型不可載入、日期不一致、ranking 非當日、Top10 不完整時必須 fail loud。
6. publish 階段只產 publish-ready artifact；本卡禁止實際傳送。

## 驗收條件

- RED：先補模型載入失敗、stale ranking、step timeout、resume 的失敗測試。
- GREEN：最小實作通過上述測試。
- 可用 temp directory 跑完整 shadow workflow，不改正式資料。
- manifest 可重建每步輸入、輸出、耗時與失敗原因。
- `git diff --check` 通過，diff 不含卡片範圍外檔案。

## 建議驗證

```bash
uv run python -m unittest tests.test_daily_workflow_v2
uv run python scripts/run_daily_v2.py --dry-run --run-date YYYY-MM-DD
git diff --check
```

## 回報要求

- 已驗證
- 未驗證及原因
- 剩餘風險
- 正式切換前仍需哪些 integration／acceptance 證據

## 主線整合結果

- 整合提交：`acf3dc2`
- 主線重驗：6 項 workflow 測試與完整 temp-dir shadow run 通過。
- production switch：未啟用；既有 daily／publish／launchd／通知設定未修改。

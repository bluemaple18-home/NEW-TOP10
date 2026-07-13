---
id: REFACTOR-04
status: integrated
type: implementation
priority: P1
model: gpt-5.6-terra
---

# uv 環境鎖定與操作文件校正

## 目標

建立可重現的 `uv + .venv` 專案環境，讓 clone 後的安裝、每日 dry-run、排名與訓練 import 可被驗證；同步修正 README／QUICKSTART／DEVELOPMENT 的失效指令。

## 依賴與 frontier

- blocking edges：無。
- frontier：可立即開工。
- 不得切換正式 launchd 或通知設定。

## 可改範圍

- `pyproject.toml`、`uv.lock`。
- `requirements.txt` 的相容策略；若保留需註明 source of truth。
- `README.md`、`QUICKSTART.md`、`DEVELOPMENT.md`、必要操作文件。
- 環境 smoke test／dependency validation test。

## 不可改範圍

- `AGENTS.md` 為 generated file，不得直接編輯。
- 不得修改模型權重、排名公式、正式資料或 artifact。
- 不得修改 live notify 值或啟停 launchd。
- 共享文件與指令不得含本機絕對路徑。

## 行為契約

1. `uv sync` 在乾淨環境有唯一 lockfile。
2. 至少區分 runtime、training/reporting、dev/test dependencies。
3. 能 import pandas、pyarrow、lightgbm、sklearn、matplotlib、FastAPI 與訓練入口。
4. 文件只描述實際存在的入口與 17:30 排程，不再引用失效檔案。
5. live send 的實際狀態要明確揭露，但本卡不得改開關。

## 驗收條件

- `uv lock --check` 或等價 lock 驗證通過。
- `uv sync` 後 dependency smoke 通過。
- README 內指令與檔案路徑可被靜態檢查。
- `git diff --check` 通過。

## 建議驗證

```bash
uv lock --check
uv sync
uv run python -c "import pandas, pyarrow, lightgbm, sklearn, matplotlib, fastapi"
git diff --check
```

## 回報要求

- dependency groups 與相容策略
- 已驗證、未驗證、剩餘風險

## 主線整合結果

- 整合提交：`dc103de`
- 主線重驗：`uv lock --check`、環境契約測試與核心 runtime／training import 通過。
- daily dry-run 未在隔離 worktree 執行，因該 worktree 沒有正式資料；未因此修改資料或正式流程。

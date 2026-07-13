# REFACTOR-12｜Automation Status Contract 抽離

- status: ready
- priority: P1
- task thickness: strict

## 目標

從 `scripts/run_automation.py` 抽離 Step／Status dataclass、status output path 與 summary payload 的純契約邏輯；保留 daily canonical status、monitor/retrain 分流及 dry-run 命名完全等價。

## 依賴與 frontier

- 依賴：REFACTOR-06 pipeline policy 已完成。
- blocker：無。
- frontier：可立即開工。

## 可改檔案

- `app/automation/status_contract.py`（可新增）
- `app/automation/__init__.py`
- `scripts/run_automation.py`
- `tests/test_automation_status_contract.py`
- `tests/test_automation_status_contract_unit.py`（可新增）
- 本卡 status/result

## 不可改

- daily／monitor／retrain 步驟、command、錯誤語意
- `scripts/run_daily.sh`、`scripts/run_daily_publish.sh`
- config、plist、ranking、model、data artifacts
- status schema version 與現有 JSON 欄位

## 實作契約

1. 新模組為 deterministic contract：dataclass、output-path policy、summary projection；不得讀 env/config 或寫檔。
2. `scripts.run_automation.StepResult`、`AutomationStatus`、`STATUS_SCHEMA_VERSION` 仍可 import。
3. runner 只保留 I/O adapter，委派純函式；JSON 內容、路徑與 key order/欄位不得漂移。
4. table-driven tests 覆蓋 daily、monitor、retrain、reference、dry-run。
5. 舊新 golden payload 深度相等；live 控制檔 hash 不變。

## 驗收

- automation status contract tests 全通過。
- pipeline-window／resource-guard verifier 仍通過。
- full unittest、`py_compile`、`git diff --check` 通過。
- 不執行正式 daily/retrain，不 reload。

## 回報

建立單一 atomic commit；回報 SHA、golden evidence 與剩餘風險，不 merge、不 push、不 reload。

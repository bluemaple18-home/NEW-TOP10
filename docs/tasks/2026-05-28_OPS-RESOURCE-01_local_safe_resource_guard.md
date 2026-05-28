# OPS-RESOURCE-01：本機安全資源模式

## 五行派工卡

任務ID：OPS-RESOURCE-01
卡片類型｜派工對象：Ops / Resource Guard｜Codex
請讀：`scripts/run_automation.py`、`scripts/daily_retrain.sh`、`scripts/run_daily.sh`、`config/automation.yaml`
任務目的：建立 `local_safe / standard / host_full` 資源模式，避免本機測試誤跑全量 ETL、正式 retrain、重型 industry monitor
證據路徑：`artifacts/resource_guard_latest.json`、`logs/retrain_YYYYMMDD.log`

## 背景

正式 ETL / retrain / industry momentum monitor 會讓本機 CPU 長時間滿載。後續所有測試必須能區分：

- 本機安全驗證：不跑長任務。
- 主機正式任務：允許全量流程。

## 範圍

本卡新增：

- `TOP10_RESOURCE_PROFILE=local_safe|standard|host_full`
- `--resource-profile` CLI 參數
- `local_safe` guard：
  - 正式 `retrain` 必須被擋，除非 `TOP10_ALLOW_HEAVY_RETRAIN=1`
  - `daily` 沒有 `TOP10_PIPELINE_START_DATE` / `TOP10_PIPELINE_END_DATE` 時必須被擋，除非 `TOP10_ALLOW_FULL_ETL=1`
  - `monitor` 預設跳過 `industry_momentum.monitor`，除非 `TOP10_ALLOW_HEAVY_MONITOR=1`
  - 子程序 thread env 預設降到 1

## 非範圍

- 不改模型權重。
- 不跑正式 retrain。
- 不跑全量 ETL。
- 不改 ranking score。

## 驗收

- `scripts/verify_resource_guard.py` 使用 TemporaryDirectory，不讀寫正式模型與資料。
- 驗證 `local_safe` 擋正式 retrain。
- 驗證 `local_safe` 擋無日期窗 daily。
- 驗證 `local_safe` monitor 會跳過重型 industry monitor。
- `bash -n scripts/daily_retrain.sh scripts/run_daily.sh` 通過。
- `py_compile` 通過。

## 主機使用方式

主機正式流程請明確設定：

```bash
TOP10_RESOURCE_PROFILE=host_full bash scripts/run_daily.sh
TOP10_RESOURCE_PROFILE=host_full bash scripts/daily_retrain.sh retrain --trigger manual
```

本機測試請使用：

```bash
TOP10_RESOURCE_PROFILE=local_safe uv run --with-requirements requirements.txt python -m scripts.run_automation monitor
uv run --with-requirements requirements.txt python scripts/verify_resource_guard.py
```

# M13-07：產業動能 shadow monitor 接入 automation

狀態：`completed`
完成日期：`2026-05-18`

任務ID：`M13-07`
卡片類型｜派工對象：Monitoring / automation｜Codex
請讀：`docs/tasks/2026-05-18_M13-06_industry_momentum_shadow_ranking_walkforward.md`、`scripts/run_automation.py`、`docs/AUTOMATION.md`
任務目的：把 M13-06 的 `monitor_only` 結論變成可重跑的離線監控入口，讓 monitor automation 會更新產業動能 shadow artifact；不接 production ranking / model / UI。
證據路徑：`scripts/monitor_industry_momentum.py`、`artifacts/industry_momentum_walkforward_shadow.md`、`artifacts/industry_momentum_walkforward_shadow.json`。

## 範圍

- 新增 `scripts/monitor_industry_momentum.py`。
- `scripts.run_automation monitor` 增加 step：
  - `industry_momentum.monitor`
- 更新 `docs/AUTOMATION.md`，記錄 M13 產業動能 shadow monitor。

## 不做

- 不修改 production ranking CSV/API。
- 不修改 `risk_adjusted_score`。
- 不修改 LightGBM feature list。
- 不把產業訊號放進 weekly 推薦理由。
- 不新增 UI。

## 完成紀錄

- `scripts/monitor_industry_momentum.py` 會重跑 `scripts/research_industry_momentum_walkforward.py`。
- 更新 artifact：
  - `artifacts/industry_momentum_walkforward_shadow.json`
  - `artifacts/industry_momentum_walkforward_shadow.md`
- stdout 會輸出可讀監控狀態，例如：
  - `INDUSTRY_MOMENTUM_MONITOR_MONITOR_ONLY return_uplift=0.005 hit_rate_uplift=0.0093 shadow_concentration=0.264`

## 驗證結果

```bash
uv run --with-requirements requirements.txt python scripts/monitor_industry_momentum.py
uv run --with-requirements requirements.txt python -m py_compile scripts/monitor_industry_momentum.py scripts/run_automation.py
uv run --with-requirements requirements.txt python -m scripts.run_automation monitor --dry-run
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

結果：通過。

重點輸出：

- `INDUSTRY_MOMENTUM_WALKFORWARD_OK`
- `INDUSTRY_MOMENTUM_MONITOR_MONITOR_ONLY return_uplift=0.005 hit_rate_uplift=0.0093 shadow_concentration=0.264`
- `weekly_primary_reasons_no_industry_signal=True`

## Review 重點

- monitor automation 是否只更新 research artifact。
- 是否可能讓 monitor failure 影響既有 PSI / factor monitor 流程。
- 是否有任何 production score / model / UI 泄漏。

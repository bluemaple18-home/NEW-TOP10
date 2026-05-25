# REVIEW-M13-07：產業動能 shadow monitor automation review

任務ID：`REVIEW-M13-07`
卡片類型｜派工對象：Review｜另一個 AI
請讀：
- `docs/tasks/2026-05-18_M13-07_industry_momentum_monitor_automation.md`
- `scripts/monitor_industry_momentum.py`
- `scripts/run_automation.py`
- `docs/AUTOMATION.md`
- `artifacts/industry_momentum_walkforward_shadow.md`

任務目的：review M13-07 是否只是把 M13-06 monitor_only 研究接進離線 monitor automation，確認沒有 production ranking/model/UI 泄漏。

證據路徑：
- `artifacts/industry_momentum_walkforward_shadow.md`
- `artifacts/industry_momentum_walkforward_shadow.json`

## Review 問題

1. `scripts/monitor_industry_momentum.py` 是否只重跑 research artifact，不修改 production ranking？
2. `scripts.run_automation monitor` 新增 `industry_momentum.monitor` 是否合理？
3. 這個 monitor step 失敗時是否應讓整個 monitor 失敗？目前設計是 yes，和 `factor.monitor` 一致。
4. 是否仍維持 `weekly_primary_reasons_no_industry_signal=True`？
5. 是否需要在下一張卡才接 API/UI，而不是本卡直接接？

## 已跑驗證

```bash
uv run --with-requirements requirements.txt python scripts/monitor_industry_momentum.py
uv run --with-requirements requirements.txt python -m py_compile scripts/monitor_industry_momentum.py scripts/run_automation.py
uv run --with-requirements requirements.txt python -m scripts.run_automation monitor --dry-run
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

已知輸出：

- `INDUSTRY_MOMENTUM_MONITOR_MONITOR_ONLY return_uplift=0.005 hit_rate_uplift=0.0093 shadow_concentration=0.264`
- `weekly_primary_reasons_no_industry_signal=True`

## Review 標準

- P0/P1/P2：production ranking/model/UI 被改、monitor 寫入正式 ranking、或推薦文案出現產業訊號。
- P3：automation 失敗策略、文件、命名建議。
- 若無 blocker，請明確說：`M13-07 可以過；產業動能維持 monitor_only，不接 production integration。`

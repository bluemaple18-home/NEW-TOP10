# RESEARCH-COST-BASIS-INCREMENTAL-01 Evidence

status: NO-GO

## Root question

Cost basis 控制 liquidity activity 後，是否仍有足以進入成本化 Top10 replay 的獨立增益？

## Evidence

- artifact：`artifacts/model_experiments/cost_basis_incremental_walkforward_2026-07-23.json`
- verifier：`.venv/bin/python scripts/verify_feature_group_regime_walkforward.py`
- representative run：

```bash
.venv/bin/python scripts/research_feature_group_regime_walkforward.py \
  --market-regime-history artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json \
  --universe-mode point-in-time-liquidity \
  --liquidity-top-n 200 \
  --incremental-primary-group cost_basis \
  --output artifacts/model_experiments/cost_basis_incremental_walkforward_2026-07-23.json
```

## Data facts

- 成熟樣本：252 日、`2025-06-26`～`2026-07-08`。
- `close_vs_vwap_5d`、`close_vs_vwap_20d` 覆蓋 100%。
- reclaim/loss 僅首個成熟日因初始化不足低於 coverage gate，其餘完整。
- point-in-time universe 每日最多 200 檔。

## Result

- cost basis group：91 OOS 日、IC `0.013877`、Top-Bottom spread `0.015160`。
- group decision：`MONITOR_ONLY`。
- incremental vs liquidity：
  - weighted partial IC：`0.006802`
  - stable buckets：7
  - positive bucket rate：`0.285714`
  - decision：`NO_INCREMENTAL_EDGE`
- `RISK_OFF` 不穩定：fold 3 `+0.079310`、fold 4 `-0.033299`。

## Acceptance mapping

- partial IC >= 0.01：FAIL。
- stable bucket positive rate >= 0.60：FAIL。
- portfolio replay eligibility：FAIL，依契約停止。
- production ranking／模型／權重未修改：PASS。

## Interpretation

成本位置本身有部分橫斷面訊息，但大部分與 liquidity activity 或特定時期重疊。它可作理由文字、診斷或監控欄位；目前不能作獨立選股加分。

## Remaining risk

- 不允許事後只挑 `RISK_OFF`；若未來要檢驗 regime-only 假說，必須另開新卡、預註冊並使用新的 OOS 日期。

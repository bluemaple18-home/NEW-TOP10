---
id: RESEARCH-FEATURE-REGIME-WF-01-EVIDENCE
status: NO_GO
type: evidence
---

# Feature Group × Regime Walk-forward 結果

## Status

`NO_GO_FOR_PORTFOLIO_REPLAY`

本輪研究已完成，但沒有 feature group 達到進入 portfolio replay 的門檻。這是候選淘汰結論，不代表研究管線失敗。

## 已觀測事實

- 真實資料範圍：2025-06-02～2026-06-24，共 269 個已有 10D 成熟標籤的交易日。
- 5 個 expanding-window folds；每 fold 保留 10 個交易日 label embargo。
- 特徵選擇與方向只使用當時已成熟的 train labels。
- 每日橫斷面有效覆蓋率門檻為 70%。
- regime history 採 append-only：保留既有 244 日標籤，只追加 36 日。
- 重新計算的 history 在 244 個重疊日中有 85 日改標（34.8361%）；全部保留舊標，未讓資料回補改寫歷史 regime。
- `models/latest_lgbm.pkl` SHA-256 前後皆為 `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`。
- production ranking、正式 feature、權重、API 與 UI 均未修改。

## 最終結果

| Feature group | Decision | OOS days | Weighted IC | Top-bottom spread | Positive stable buckets |
|---|---|---:|---:|---:|---:|
| cost_basis | MONITOR_ONLY | 66 | 0.0172 | 0.0020 | 50.0% |
| event | REJECTED | 73 | 0.0116 | -0.0006 | 50.0% |
| liquidity_activity | REJECTED | 94 | 0.0078 | -0.0010 | 33.3% |
| industry_momentum | REJECTED | 87 | 0.0069 | 0.0050 | 33.3% |
| pattern | REJECTED | 101 | -0.0009 | -0.0055 | 50.0% |
| technical_trend | REJECTED | 117 | -0.0063 | -0.0152 | 25.0% |
| chip_flow | INSUFFICIENT_DATA | 0 | — | — | — |
| fundamental | INSUFFICIENT_DATA | 0 | — | — | — |

唯一條件監控項是 `NARROW_LEADER/liquidity_activity`：36 OOS days、5 fold buckets、IC 0.0138、spread 0.0177、60% buckets 同時正向。證據只足以繼續累積，不足以改 ranking。

## 被排除的假陽性

未套來源遮罩時，`trust_buy_days_3d/5d/10d` 曾產生看似強的 `chip_flow` candidate。追查後確認：

- `trust_buy > 0` 在來源缺值時會轉成 `False/0`，衍生 rolling days 因此表面上不是缺值。
- FinMind 歷史抓取只涵蓋整段資料平均成交額前 200 檔，且 cohort 使用全期間平均，不能視為 point-in-time universe。
- `institutional_available` 真實覆蓋率只有 10.4471%；研究遮罩了 476,502 筆表面非空但來源不可得的 chip-flow 衍生值。

因此 chip-flow 結論改判 `INSUFFICIENT_DATA`，禁止送入 portfolio replay。

## Acceptance mapping

- fold embargo、train-only selection、負向特徵方向、append-only history、availability mask：verifier `OK`。
- 代表性真實資料：5 folds 執行成功。
- 模型與 production ranking 邊界：未寫入；模型 hash 與 Git 版本一致。
- 研究 promotion：`false`。

## Remaining risk / next step

1. 若要重測 chip flow，必須先有 point-in-time、append-only、TWSE/TPEx 語意一致的歷史法人來源；不可沿用全期間 top-200 cohort。
2. `cost_basis` 與 `NARROW_LEADER/liquidity_activity` 只保留監控，待新增成熟日期後用相同 frozen contract 追加驗證。
3. 產業動能本輪維持 `REJECTED_CURRENT_FORM`；產業 feature family 仍可提出新假設，但不得重用固定加分 overlay。

## Reproduce

```bash
uv run --with-requirements requirements.txt python scripts/verify_feature_group_regime_walkforward.py
uv run --with-requirements requirements.txt python scripts/build_market_regime_history.py \
  --output artifacts/model_experiments/market_regime_history_2026-07-22.json
uv run --with-requirements requirements.txt python scripts/build_append_only_market_regime_history.py \
  --base artifacts/market_regime_history_2026-05-29.json \
  --extension artifacts/model_experiments/market_regime_history_2026-07-22.json \
  --output artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json
uv run --with-requirements requirements.txt python scripts/research_feature_group_regime_walkforward.py \
  --market-regime-history artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json \
  --output artifacts/model_experiments/feature_group_regime_walkforward_final_2026-07-23.json
```

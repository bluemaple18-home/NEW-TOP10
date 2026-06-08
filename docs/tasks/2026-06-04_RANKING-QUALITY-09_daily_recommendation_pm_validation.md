# RANKING-QUALITY-09 每日推薦 PM 風險驗證

## 目標

延續每日推薦訓練主線，針對 half-year dense 回測中表現最好的 K 系列 constrained ranking 候選，加入 Public Equity PM 風險視角：

- 報酬是否優於 baseline
- 回撤是否惡化
- 是否只靠單一族群或少數股票撐起來
- 10D 推薦持有視角在不同時間窗是否穩定

## 不做

- 不訓練模型
- 不覆蓋 `models/latest_lgbm.pkl`
- 不改 production ranking
- 不接推播
- 不宣稱 promotion ready

## 方法

讀取既有 artifacts：

- `portfolio_batch01_*_half_year_dense_top10_h10_2026-06-02.json`
- `replay_window_stability_half_year_dense_2026-06-02.json`
- `replay_window_stability_half_year_dense_k9_2026-06-02.json`

輸出：

- `artifacts/model_experiments/daily_recommendation_pm_validation_2026-06-02.json`
- `artifacts/model_experiments/daily_recommendation_pm_validation_2026-06-02.md`

## 驗收

- builder 可產出 JSON / Markdown。
- verifier 通過。
- contract 明確標示 research-only、read-existing-artifacts-only、no production change。

## 本輪結果

已完成。

- baseline：`53.08% / max DD -8.17%`
- 候選數：8
- `ADVANCE_TO_DAILY_SHADOW`: 1
- `RESEARCH_SHADOW_WITH_GUARDS`: 5
- `MONITOR_ONLY`: 2
- 最佳候選：`feature_group_constrained_k9`

`feature_group_constrained_k9`：

- half-year dense total return：`61.64%`
- return delta：`+8.56%`
- max DD：`-8.45%`
- DD delta：`-0.28%`
- win rate：`57.19%`
- top group positive share：`15.56%`
- top3 stock positive share：`18.00%`
- 10D window stability：`PARTIAL_STABILITY`

結論：可進下一階段 daily shadow monitor，但仍不可正式升版或改 production ranking。

驗證：

- `python3 -m py_compile scripts/build_daily_recommendation_pm_validation.py scripts/verify_daily_recommendation_pm_validation.py`
- `uv run --with-requirements requirements.txt python scripts/build_daily_recommendation_pm_validation.py --date 2026-06-02 --artifact-label half_year_dense`
- `uv run --with-requirements requirements.txt python scripts/verify_daily_recommendation_pm_validation.py --artifact artifacts/model_experiments/daily_recommendation_pm_validation_2026-06-02.json`

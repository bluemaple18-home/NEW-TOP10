# RANKING-QUALITY-11 K9 Production Overlay Candidate，Baseline/K8 留對照

## 背景

半年有限資金回測顯示：

- baseline：`+53.08% / max DD -8.17%`
- `feature_group_constrained_k9`：`+61.64% / max DD -8.45%`
- K9 比 baseline 報酬高 `+8.56%`，最大回撤只差 `-0.28%`

PM 方向：K9 可做 production overlay candidate，但正式預設必須關閉。
要真正改 `artifacts/ranking_YYYY-MM-DD.csv`，必須同時滿足：

- `production_ranking_overlay.enabled=true`
- `production_ranking_overlay.promotion_review_approved=true`
- 如用環境變數，也只能在上述兩者都為 true 時生效。

目前 config 預設為 default-off，不會改正式每日推薦。

## 正式規則

K9：

- 保留 production Top9
- 用 feature-group shadow score 補第 10 名
- 正式輸出仍寫 `artifacts/ranking_YYYY-MM-DD.csv`

對照：

- baseline：`artifacts/baseline_ranking_YYYY-MM-DD.csv`
- K8：`artifacts/ranking_comparison_k8_YYYY-MM-DD.csv`
- comparison JSON：`artifacts/ranking_comparison_YYYY-MM-DD.json`

以上對照 artifact 只會在 overlay payload 存在時輸出；default-off 時不輸出 baseline/comparison，避免誤以為正式榜已切換。

## 不做

- 不重訓模型
- 不覆蓋 `models/latest_lgbm.pkl`
- 不改推播
- 不把 K8 設為正式榜

## 本輪證據

日期：`2026-06-03`

K9 candidate：

- 保留 baseline 前 9 檔
- 第 10 檔改為 `8112 至上`
- baseline 被替換：`9933 中鼎`

產物：

- `artifacts/ranking_2026-06-03.csv`
- `artifacts/baseline_ranking_2026-06-03.csv`
- `artifacts/ranking_comparison_2026-06-03.json`
- `artifacts/ranking_comparison_k8_2026-06-03.csv`
- `artifacts/candidate_persistence_2026-06-03.json`
- `artifacts/daily_report_2026-06-03.json`
- `artifacts/daily_report_2026-06-03.md`

驗證：

- `python3 -m py_compile app/agent_b_ranking.py scripts/verify_production_ranking_overlay.py`
- `uv run --with-requirements requirements.txt python scripts/verify_production_ranking_overlay.py --date 2026-06-03 --expected-keep 9 --expected-comparison-keep 8`
- `shasum -a 256 models/latest_lgbm.pkl`：`76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675`

結論：K9 可保留為 production overlay candidate；default-off guard 仍必須保護正式每日推薦，未經 promotion review 不得切換。

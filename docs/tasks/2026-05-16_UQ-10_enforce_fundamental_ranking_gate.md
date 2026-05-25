# UQ-10：Enforce Fundamental Ranking Gate

任務ID：`UQ-10`
卡片類型｜派工對象：Ranking Gate / 回歸修復｜Codex
請讀：`docs/tasks/2026-05-16_UQ-05_ranking_integration_gate.md`、`app/trading/ranking_policy.py`、`scripts/verify_review_fixes.py`
任務目的：把 UQ-05 的 `explain_only / shadow_only` 決策落到程式碼，避免 `fundamental_*` 欄位只因存在就偷渡進 `quality_score`。
證據路徑：`app/trading/ranking_policy.py`、`scripts/verify_review_fixes.py`、本卡執行紀錄。

狀態：`completed`

## 背景

UQ-05 已決定 real universe 基本面 coverage 僅約 `1.17%`，不可接入 ranking 權重。但 `RankingPolicy._quality_score()` 目前會在 `fundamental_roe / fundamental_gross_margin / fundamental_debt_ratio` 欄位存在時直接混入 `quality_score`，形成規範與實作不一致。

## 範圍

- 讓 `quality_score` 預設只使用可穩定覆蓋的流動性品質。
- 基本面維持在 shadow artifact / UI 解釋層，不參與 `risk_adjusted_score`。
- 加回歸測試，確認 fundamental 欄位存在也不會改變 ranking score。

## 不做

- 不刪除基本面 feature contract。
- 不改模型訓練 feature。
- 不調 ranking 權重。
- 不移除未來重新接入基本面的可能性。

## 驗收

- `scripts/verify_review_fixes.py` 有 regression 覆蓋 fundamental gate。
- `RankingPolicy` 不再因 `fundamental_*` 欄位存在而改變 `quality_score`。
- ranking smoke 可跑，且仍輸出 `quality_score / risk_penalty / risk_adjusted_score`。

## 執行紀錄

- 更新 `app/trading/ranking_policy.py`
  - `quality_score` 預設只使用流動性品質。
  - 基本面欄位不再因存在就自動混入 ranking。
- 更新 `scripts/verify_review_fixes.py`
  - 新增 `verify_ranking_policy_ignores_fundamentals_until_gate_passes()`。
  - 驗證加入高品質 `fundamental_*` 欄位後，`quality_score` 與 `risk_adjusted_score` 不變。

## 驗證紀錄

```bash
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python -m app.agent_b_ranking
```

結果：

- `REVIEW_FIXES_OK`
- `MODEL_FOUNDATION_OK specs=11`
- `verify_data_contracts.py` 通過
- ranking smoke 成功載入 `models/latest_lgbm.pkl`，並輸出 `artifacts/ranking_2026-05-15.csv`

## 結論

UQ-05 的 `explain_only / shadow_only` 決策已落實到 ranking policy。基本面仍可留在 feature/model/shadow/UI 解釋層，但不會偷渡進 `quality_score` 排序權重。

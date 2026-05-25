# UQ-05：基本面分數接入 Ranking 決策閘門

任務ID：`UQ-05`
卡片類型｜派工對象：模型決策 / Ranking Gate｜Codex
請讀：`docs/tasks/2026-05-16_UQ-04_fundamental_shadow_rerun.md`、`docs/architecture/TRADING_DECISION_LAYER.md`、`app/trading/ranking_policy.py`、`scripts/verify_review_fixes.py`
任務目的：根據 shadow score 證據決定基本面分數是否接入 `quality_score` 或 `risk_penalty`，並寫下明確 gate，不讓人工拍腦袋調權重。
證據路徑：新增或更新 `artifacts/fundamental_ranking_gate_decision.md`，必要時更新 `docs/architecture/MODEL_ROADMAP.md`。

## 背景

基本面可能有助於降低財務品質差的動能候選，但是否能改善報酬必須由 coverage、IC、分組報酬與 ranking sensitivity 支持。

## 接入門檻

最低建議門檻：

- stock-level coverage >= 80%
- latest feature coverage >= 80%
- IC 或分組報酬有穩定方向
- Top10 sensitivity 不造成不可解釋的大幅換股
- 無明顯資料 leakage

## 可能決策

1. `explain_only`：只留 UI / 個股詳情，不進排序。
2. `risk_only`：只把嚴重財務警訊接入 `risk_penalty` 或暫停操作原因。
3. `quality_shadow`：ranking artifact 顯示 shadow score，但不排序。
4. `quality_integrated`：小權重接入 `quality_score`，並有回測證據。

## 不做

- 不在沒有證據時調權重。
- 不改模型訓練流程。
- 不用單一股票案例當作接入理由。

## 驗收

- 決策文件明確列出採用 / 不採用理由。
- 若接入，必須有 regression test 保證舊欄位仍存在。
- 若不接入，UI 解釋層仍保留基本面資訊。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

## Review 重點

- 是否違反 No Vibe Coding。
- 是否把 shadow score 直接當成績效證據。
- 是否保留回退與監控路徑。

## 執行紀錄

- 狀態：`completed`
- 完成時間：`2026-05-16`
- 決策文件：`artifacts/fundamental_ranking_gate_decision.md`
- 採用決策：`explain_only`

## 結論

- 不接入 `quality_score` / `risk_adjusted_score`。
- 不改 `RankingPolicy`。
- 保留基本面資訊在 UI 個股解釋層與 shadow artifact。
- 下一步若要重新評估，需先完成備份後全量 universe 重建與更長期回測。

## Real Universe 補充

- UQ-07 後正式 `data/clean` 已更新為 real universe：features `1967` 檔、universe `1151` 檔。
- Real-universe fundamental coverage 只有 `1.17%`，低於接入門檻 `80%`。
- 決策維持：`explain_only` / `shadow_only`，不進 ranking 權重。

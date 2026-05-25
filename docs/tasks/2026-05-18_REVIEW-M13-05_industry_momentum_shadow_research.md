# REVIEW-M13-05：產業動能 shadow research review

任務ID：`REVIEW-M13-05`
卡片類型｜派工對象：Review｜另一個 AI
請讀：
- `docs/tasks/2026-05-18_M13-05_industry_momentum_shadow_research.md`
- `scripts/research_industry_momentum_shadow.py`
- `artifacts/industry_momentum_shadow_research.md`
- `artifacts/industry_momentum_shadow_research.json`
- `app/labels.py`
- `app/monitoring/factor_monitor.py`

任務目的：review M13-05 產業動能與 sector rotation shadow research 是否成立，確認沒有 lookahead、沒有改 production ranking/model，且是否足以開 M13-06 walk-forward shadow ranking。

證據路徑：
- `artifacts/industry_momentum_shadow_research.md`
- `artifacts/industry_momentum_shadow_research.json`

## Review 問題

1. `industry_momentum_20d` / `industry_breadth_ma20` / `sector_rotation_score_20d` 是否只使用當日以前資料？
2. `LabelGenerator(horizon=10)` 與 factor 計算是否有 lookahead bias？
3. `industry_relative_strength_20d` 與 `industry_momentum_20d` 在橫斷面 IC 上等價，是否應在下一張卡移除或改成 z-score / rolling relative version？
4. IC 與 top-bottom spread 是否足以支持 `shadow_candidate`，而不是 production integration？
5. 是否確認沒有修改 `risk_adjusted_score`、LightGBM feature list、API contract、weekly recommendation wording？

## 已跑驗證

```bash
uv run --with-requirements requirements.txt python scripts/research_industry_momentum_shadow.py
uv run --with-requirements requirements.txt python -m py_compile scripts/research_industry_momentum_shadow.py scripts/research_industry_etf_risk.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

已知輸出：

- `INDUSTRY_MOMENTUM_SHADOW_OK`
- `industry_momentum_20d` IC=`0.1259`，days=`55`，coverage=`0.6625`
- `industry_breadth_ma20` IC=`0.1180`，days=`56`，coverage=`1.0`
- `sector_rotation_score_20d` IC=`0.1286`，days=`55`，coverage=`0.6752`
- `weekly_primary_reasons_no_industry_signal=True`

## Review 標準

- P0/P1/P2：任何 lookahead、production score 泄漏、或把研究訊號輸出成推薦理由。
- P3：命名、文件、後續研究設計建議。
- 若無 blocker，請明確說：`M13-05 可以過，下一張可開 M13-06 industry momentum shadow ranking / walk-forward 評估。`

## Review 結果（2026-05-18）

Findings：

- `[P2]` 產業 / sector group factor 目前有「自我納入」污染。
  - `industry_momentum_20d`、`industry_breadth_ma20`、`sector_rotation_score_20d` 使用同日 group mean merge 回個股，個股自己的 20D return / MA20 狀態會進到自己的產業訊號。
  - 這不是 lookahead，也沒有進 production，但會讓 IC / spread 偏樂觀。
  - `M13-06` 必須改成 leave-one-out / ex-self group aggregate，或至少加 member threshold 後再做 walk-forward。
- `[P3]` `industry_relative_strength_20d` 在每日橫斷面排序上等價於 `industry_momentum_20d`。
  - 因為只是扣掉同一天共同 market mean，Spearman IC 與 top/bottom bucket 排序會相同。
  - `M13-06` 建議移除其中一個，或改 rolling z-score / rolling market-relative strength。

結論：

- 未發現 production ranking / model / API 被改動。
- `risk_adjusted_score` 沒接入這些 factor。
- LightGBM feature list 沒有 industry / sector 特徵。
- ranking CSV header 仍是原 production 欄位。
- `LabelGenerator` 是 D 訊號、D+1 open entry、D+10 close exit；在收盤後產訊號、隔日進場假設下，D 日 close / MA20 不算 lookahead。
- `M13-05 可以過，下一張可開 M13-06 industry momentum shadow ranking / walk-forward 評估。`

# M13-05：產業動能與 sector rotation shadow research

狀態：`completed`
完成日期：`2026-05-18`

任務ID：`M13-05`
卡片類型｜派工對象：研究 / shadow factor｜Codex
請讀：`docs/tasks/2026-05-17_M13-04_formal_industry_mapping_expansion.md`、`scripts/research_industry_etf_risk.py`、`app/monitoring/factor_monitor.py`、`app/labels.py`
任務目的：在不修改 production ranking / model 的前提下，評估 `industry_momentum`、`industry_relative_strength`、`industry_breadth`、`sector_rotation` 是否有初步訊號，決定是否值得進下一張 walk-forward shadow ranking 卡。
證據路徑：`scripts/research_industry_momentum_shadow.py`、`artifacts/industry_momentum_shadow_research.md`、`artifacts/industry_momentum_shadow_research.json`。

## 背景

`M13-04` 已把本地產業 reference mapping 補齊到 active tradable universe 100%。但 M13 系列仍維持原則：

- 產業 / ETF 資訊先做風險揭露與研究。
- 不直接改 `risk_adjusted_score`。
- 不直接改 LightGBM feature list。
- 新 factor 必須先做 IC / coverage / shadow 驗證，再考慮進 production。

## 範圍

- 新增 `scripts/research_industry_momentum_shadow.py`。
- 從 `data/clean/features.parquet` 與本地 `stock_industry_map.csv` 建立 shadow frame。
- 產生候選因子：
  - `industry_momentum_20d`
  - `industry_relative_strength_20d`
  - `industry_breadth_ma20`
  - `sector_rotation_score_20d`
- 使用 `LabelGenerator(horizon=10)` 產生 future return。
- 評估：
  - daily cross-sectional IC。
  - coverage / latest coverage。
  - top-bottom bucket spread。

## 不做

- 不修改 ranking score。
- 不修改模型訓練 feature list。
- 不更新 API contract。
- 不把研究因子輸出到 weekly candidate 推薦理由。

## 完成紀錄

- 產出：
  - `artifacts/industry_momentum_shadow_research.md`
  - `artifacts/industry_momentum_shadow_research.json`
- 決策：`shadow_candidate`
- 理由：部分產業 / sector 因子有初步 IC 訊號，但樣本天數與 coverage 還不足以直接接 production；下一步需做 walk-forward shadow ranking / 回測驗證。

## 驗證結果

```bash
uv run --with-requirements requirements.txt python scripts/research_industry_momentum_shadow.py
uv run --with-requirements requirements.txt python -m py_compile scripts/research_industry_momentum_shadow.py scripts/research_industry_etf_risk.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

結果：通過。

重點輸出：

- `INDUSTRY_MOMENTUM_SHADOW_OK`
- 樣本：`95632` rows、`1959` stocks、`75` trade days。
- `industry_momentum_20d` IC=`0.1259`，days=`55`，coverage=`0.6625`。
- `industry_breadth_ma20` IC=`0.1180`，days=`56`，coverage=`1.0`。
- `sector_rotation_score_20d` IC=`0.1286`，days=`55`，coverage=`0.6752`。
- `weekly_primary_reasons_no_industry_signal=True`，確認產業研究仍未進推薦理由。

## 已知限制

- `industry_relative_strength_20d` 在每日橫斷面排序上與 `industry_momentum_20d` 等價，因為只扣同日市場均值；後續若要保留，需改成跨日或 z-score 版本。
- 產業 / sector group factor 目前使用同日 group mean merge 回個股，尚未 leave-one-out；因此每檔股票自己的 20D return / MA20 狀態會進入自己的產業訊號。這不是 lookahead，也未進 production，但會使 IC / spread 偏樂觀，尤其小產業更明顯。
- 目前 features history 短，20D 因子 coverage 約 66%；正式進 production 前需更長歷史與 walk-forward shadow ranking。
- sector 分類仍是本地 reference / keyword grouping，不是交易所權威分類。

## 下一步

- 開 `M13-06`：產業動能 shadow ranking / walk-forward 評估。
- 驗證 candidate ranking 加上產業動能後，是否改善命中率、top bucket return、drawdown，且不造成單一產業過度集中。
- `M13-06` 必須使用 leave-one-out / ex-self 產業與 sector factor，否則不得用 IC / spread 作為 production integration 依據。

## Review 紀錄（2026-05-18）

Review finding：

- `[P2]` 產業 / sector group factor 有「自我納入」污染。
  - 影響：可能讓 IC / spread 偏樂觀。
  - 處置：M13-05 可過，但 M13-06 驗收需明寫 leave-one-out / ex-self。
- `[P3]` `industry_relative_strength_20d` 在每日橫斷面排序上等價於 `industry_momentum_20d`。
  - 處置：M13-06 移除其中一個，或改 rolling z-score / rolling market-relative strength。

Review 結論：

- 未發現 production ranking / model / API 被改動。
- `risk_adjusted_score` 未接入產業因子。
- LightGBM feature list 未接入 industry / sector 特徵。
- `weekly_primary_reasons_no_industry_signal=True` 仍成立。
- `M13-05 可以過，下一張可開 M13-06 industry momentum shadow ranking / walk-forward 評估。`

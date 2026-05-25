# REVIEW-M13-04：產業 mapping 與 M13 研究修正 review

任務ID：`REVIEW-M13-04`
卡片類型｜派工對象：Review｜另一個 AI
請讀：
- `docs/tasks/2026-05-14_M13-03_industry_neutral_research.md`
- `docs/tasks/2026-05-17_M13-04_formal_industry_mapping_expansion.md`
- `scripts/research_industry_etf_risk.py`
- `scripts/build_stock_industry_map_from_concepts.py`
- `app/data/reference_repository.py`
- `scripts/verify_data_contracts.py`

任務目的：review M13-03 / M13-04 的研究證據與 reference mapping 補齊是否成立，確認沒有把不穩定產業資料誤當模型訊號，也沒有把外部抓取塞進 request path。

證據路徑：
- `artifacts/industry_etf_risk_research.md`
- `artifacts/industry_etf_risk_research.json`
- `artifacts/stock_industry_map_build_summary.json`
- `data/reference/stock_industry_map.csv`

## 背景

M13-03 原本研究發現產業 / ETF 維度暫時只能做風險揭露，不應直接改 ranking 或模型權重。過程中發現研究腳本對「本地 reference mapping 覆蓋率」有錯算，將 `unavailable` 誤算為有效 mapping。

已修正：

- `scripts/research_industry_etf_risk.py`
  - 本地 reference mapping ratio 現在排除 `code_prefix_fallback` 與 `unavailable`。
  - mapping 高於 95% 時仍只建議 `risk_disclosure_only`，不直接改 ranking。
- `scripts/build_stock_industry_map_from_concepts.py`
  - 只讀本地 `stock_concept_membership.csv` 與 `tradable_universe.csv`。
  - 產出完整 `stock_industry_map.csv`。
- `data/reference/stock_industry_map.csv`
  - 從 19 筆補到 1967 筆。
  - active tradable universe 覆蓋率 100%。

## Review 問題

1. `build_stock_industry_map_from_concepts.py` 的產業選擇邏輯是否合理？
   - 優先 `電子產業 / ...`
   - 其次 `上市類股 / ...`、`上櫃類股 / 櫃...`
2. `sector_name` keyword mapping 是否足夠保守？
   - 是否有明顯錯分會影響風險揭露？
3. `research_industry_etf_risk.py` 的 mapping coverage 修正是否正確？
4. M13-03 的結論 `risk_disclosure_only` 是否成立？
5. 是否有任何路徑在 API request path 即時抓外部資料？
6. 是否有把產業 / ETF 維度偷偷接進 `risk_adjusted_score`？

## 已跑驗證

```bash
uv run --with-requirements requirements.txt python scripts/build_stock_industry_map_from_concepts.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python scripts/research_industry_etf_risk.py
uv run --with-requirements requirements.txt python -m py_compile scripts/build_stock_industry_map_from_concepts.py scripts/research_industry_etf_risk.py
```

已知輸出：

- `STOCK_INDUSTRY_MAP_BUILD_OK rows=1967 coverage=100.00%`
- `reference_industry: rows=1967, path=True`
- `industry_valid=True unique=True nonblank=True`
- `/api/rankings/latest` smoke status：`200`
- `/api/stocks/{stock_id}/detail` smoke status：`200`
- `INDUSTRY_ETF_RISK_RESEARCH_OK`

## Review 標準

- 若發現 P0/P1/P2 問題，請列明檔案與原因。
- 若只有命名、文件或後續研究建議，標 P3。
- 若無 blocker，請明確說：`M13-04 可以過，下一張可開 M13-05 industry momentum / sector rotation shadow research。`

## Review 修正紀錄（2026-05-18）

Review finding：

- `[P2] 產業 mapping 被當成推薦理由「共振」輸出`
- 位置：`app/services/weekly_decision_service.py`
- 問題：`M13-03 / M13-04` 結論仍是 `risk_disclosure_only`，但 weekly candidate 的 `primary_reasons` 會輸出 `{industry} 共振`，語意像是產業動能已通過驗證。

修正：

- `app/services/weekly_decision_service.py`
  - `primary_reasons` 不再放 `industry_name` / `sector_name`。
  - 產業資訊只保留在 ranking item、`dominant_groups` 與 reference summary，作為中性揭露。
- `scripts/verify_data_contracts.py`
  - 新增 regression：weekly candidate 的 `primary_reasons` 不得包含 `共振`。

驗證：

```bash
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python -m py_compile app/services/weekly_decision_service.py scripts/verify_data_contracts.py
```

結果：通過。

重點輸出：

- `weekly_candidates: status=200`
- `weekly_primary_reasons_no_industry_signal=True`

抽樣確認：

- `3030 ['綜合技術指標轉強'] 設備或廠務工程`
- `6451 ['模型初選 + 動能排序'] IC生產製造`
- `dominant_groups ['其他', '設備或廠務工程', '科技']`

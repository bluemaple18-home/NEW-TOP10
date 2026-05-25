# M13-06：產業動能 shadow ranking / walk-forward 評估

狀態：`completed`
完成日期：`2026-05-18`

任務ID：`M13-06`
卡片類型｜派工對象：研究 / shadow ranking / walk-forward｜Codex 或另一個 AI
請讀：`docs/tasks/2026-05-18_M13-05_industry_momentum_shadow_research.md`、`scripts/research_industry_momentum_shadow.py`、`app/agent_b_ranking.py`、`app/trading/ranking_policy.py`、`app/labels.py`
任務目的：把 M13-05 的產業動能候選訊號改成 leave-one-out / ex-self 版本，做 shadow ranking 與 walk-forward 評估，判斷是否值得另開 production integration 卡。
證據路徑：新增 `scripts/research_industry_momentum_walkforward.py`，輸出 `artifacts/industry_momentum_walkforward_shadow.md` / `.json`。

## 前置結論

M13-05 已通過 review，但有一個重要限制：

- group factor 不能直接用 group mean merge 回個股，否則會把個股自己的 20D return / MA20 狀態納入自己的產業訊號。
- 這會污染 IC / spread，尤其小產業更明顯。

因此 M13-06 必須先修研究方法，再談 shadow ranking。

## 範圍

- 建立 leave-one-out / ex-self factor：
  - `industry_momentum_20d_ex_self`
  - `industry_breadth_ma20_ex_self`
  - `sector_rotation_score_20d_ex_self`
- 每個 group factor 必須輸出 group member count：
  - `industry_member_count`
  - `sector_member_count`
- 設定最小 group size threshold，例如：
  - industry 至少 5 檔。
  - sector 至少 20 檔。
- 移除或重定義 `industry_relative_strength_20d`：
  - 不再保留與 `industry_momentum_20d` 等價的每日 market-mean subtraction。
  - 若要保留，改 rolling z-score 或 rolling market-relative strength。
- 做 shadow ranking：
  - 不改 production `risk_adjusted_score`。
  - 建立 shadow score 欄位，例如 `industry_shadow_score`、`shadow_risk_adjusted_score`。
  - 只在 artifact 中評估。
- 做 walk-forward 或日頻分段評估：
  - top bucket return。
  - hit rate。
  - drawdown proxy 或 downside return。
  - industry concentration。
  - 與 production ranking 對照。

## 不做

- 不修改 `app/trading/ranking_policy.py` 的 production score。
- 不修改 LightGBM feature list。
- 不讓 weekly candidate 推薦理由出現產業「共振」。
- 不把 shadow score 寫進正式 ranking CSV/API。

## 驗收

- factor 計算有明確 ex-self / leave-one-out。
- 小 group 不得使用 contaminated group mean；低於 threshold 時回 null 或降級。
- 研究報告需同時顯示：
  - 原 production 排序結果。
  - shadow ranking 結果。
  - shadow 是否改善 hit rate / top bucket return。
  - 是否增加單一產業集中風險。
- `verify_data_contracts.py` 仍通過，且 `weekly_primary_reasons_no_industry_signal=True`。
- 結論只能是：
  - `reject`
  - `monitor_only`
  - `production_candidate_needs_card`

## Review 重點

- 是否仍有 self-inclusion contamination。
- 是否有 lookahead。
- 是否偷改 production ranking score。
- 是否把研究訊號包成推薦文案。
- 是否用太短樣本直接宣告可 production。

## 完成紀錄（2026-05-18）

- 新增 `scripts/research_industry_momentum_walkforward.py`。
- 產出：
  - `artifacts/industry_momentum_walkforward_shadow.md`
  - `artifacts/industry_momentum_walkforward_shadow.json`
- factor 已改為 leave-one-out / ex-self：
  - `industry_momentum_20d_ex_self`
  - `industry_breadth_ma20_ex_self`
  - `sector_rotation_score_20d_ex_self`
- group threshold：
  - industry 至少 5 檔。
  - sector 至少 20 檔。
- shadow score 只存在研究 artifact：
  - `industry_shadow_score`
  - `shadow_risk_adjusted_score`
  - `shadow_rank`

## 研究結果

決策：`monitor_only`

原因：ex-self shadow ranking 有些微正向結果，但 hit rate / return uplift 還不夠強，且 shadow top industry concentration 上升；先保留監控，不開 production integration。

Walk-forward 摘要：

- days：`75`
- production mean return：`0.0508`
- shadow mean return：`0.0558`
- return uplift：`0.0050`
- production hit rate：`0.5200`
- shadow hit rate：`0.5293`
- hit rate uplift：`0.0093`
- production downside：`-0.0347`
- shadow downside：`-0.0342`
- production top industry concentration：`0.2360`
- shadow top industry concentration：`0.2640`
- average overlap count：`8.9467`

Factor quality：

- `industry_momentum_20d_ex_self` coverage=`0.6382`，latest coverage=`0.9456`，member_count_min=`5`
- `industry_breadth_ma20_ex_self` coverage=`0.9683`，latest coverage=`0.9456`，member_count_min=`5`
- `sector_rotation_score_20d_ex_self` coverage=`0.6662`，latest coverage=`0.9746`，member_count_min=`28`

Review 後補充的有效 peer 統計：

- `industry_momentum_20d_ex_self` valid_peer_count_min=`1`，p10=`9.0`，lt2=`238`，lt3=`377`，lt5=`1317`
- `industry_breadth_ma20_ex_self` valid_peer_count_min=`4`，p10=`11.0`，lt2=`0`，lt3=`0`，lt5=`475`
- `sector_rotation_score_20d_ex_self` valid_peer_count_min=`7`，p10=`51.0`，lt2=`0`，lt3=`0`，lt5=`0`

## 驗證結果

```bash
uv run --with-requirements requirements.txt python scripts/research_industry_momentum_walkforward.py
uv run --with-requirements requirements.txt python -m py_compile scripts/research_industry_momentum_walkforward.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

結果：通過。

重點輸出：

- `INDUSTRY_MOMENTUM_WALKFORWARD_OK`
- `weekly_primary_reasons_no_industry_signal=True`
- production ranking CSV header 無 `industry` / `sector` / `shadow` 欄位。

## 後續建議

- 暫不開 production integration。
- 可以另開低優先級 monitoring 卡，追蹤更長歷史資料後 M13-06 是否仍維持正向。
- 若未來要重啟 production candidate，需先改善樣本長度、確認 concentration 風險未升高。
- 若要進一步嚴格化 monitoring，建議增加 `min_valid_peers` 門檻，例如 3 或 5，避免有效 peer 過少的產業動能估計過度樂觀。

## Review 紀錄（2026-05-18）

Review finding：

- `[P3]` member threshold 是用掛牌成員數，不是有效 peer 數。
- ex-self 本身正確，已排除個股自身；但 `industry_momentum_20d_ex_self` 有部分列只剩 1 個有效 peer。
- 這不構成 self-inclusion，不影響 `monitor_only` 結論。

修正：

- `scripts/research_industry_momentum_walkforward.py` 增加 valid peer 統計。
- `artifacts/industry_momentum_walkforward_shadow.md/json` 補：
  - `valid_peer_count_min`
  - `valid_peer_count_p10`
  - `rows_with_lt_2_valid_peers`
  - `rows_with_lt_3_valid_peers`
  - `rows_with_lt_5_valid_peers`

驗證：

```bash
uv run --with-requirements requirements.txt python scripts/research_industry_momentum_walkforward.py
uv run --with-requirements requirements.txt python -m py_compile scripts/research_industry_momentum_walkforward.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

結果：通過。

結論：

- `M13-06 可以過；結論 monitor_only 成立，暫不開 production integration。`

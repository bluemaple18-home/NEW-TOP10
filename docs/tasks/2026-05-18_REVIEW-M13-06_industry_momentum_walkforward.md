# REVIEW-M13-06：產業動能 ex-self shadow ranking review

任務ID：`REVIEW-M13-06`
卡片類型｜派工對象：Review｜另一個 AI
請讀：
- `docs/tasks/2026-05-18_M13-06_industry_momentum_shadow_ranking_walkforward.md`
- `scripts/research_industry_momentum_walkforward.py`
- `artifacts/industry_momentum_walkforward_shadow.md`
- `artifacts/industry_momentum_walkforward_shadow.json`
- `scripts/verify_data_contracts.py`

任務目的：review M13-06 的 leave-one-out / ex-self shadow ranking 是否真的消除 self-inclusion contamination，並確認 `monitor_only` 結論是否合理、production ranking/model/API 是否未被修改。

證據路徑：
- `artifacts/industry_momentum_walkforward_shadow.md`
- `artifacts/industry_momentum_walkforward_shadow.json`

## Review 問題

1. `industry_momentum_20d_ex_self`、`industry_breadth_ma20_ex_self`、`sector_rotation_score_20d_ex_self` 是否真正排除個股自身？
2. industry / sector member threshold 是否有落實？
3. shadow ranking 是否只存在 artifact，沒有寫回 production ranking CSV/API？
4. `monitor_only` 是否合理？
   - return uplift `0.0050`
   - hit rate uplift `0.0093`
   - shadow top industry concentration 從 `0.2360` 升到 `0.2640`
5. 是否仍有 lookahead 或 D+1 entry 假設問題？
6. 是否仍維持 `weekly_primary_reasons_no_industry_signal=True`？

## 已跑驗證

```bash
uv run --with-requirements requirements.txt python scripts/research_industry_momentum_walkforward.py
uv run --with-requirements requirements.txt python -m py_compile scripts/research_industry_momentum_walkforward.py
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
```

已知輸出：

- `INDUSTRY_MOMENTUM_WALKFORWARD_OK`
- `weekly_primary_reasons_no_industry_signal=True`
- production ranking CSV header 無 `industry` / `sector` / `shadow` 欄位。

## Review 標準

- P0/P1/P2：self-inclusion 仍存在、production score 被改、研究訊號進推薦文案、或 lookahead。
- P3：門檻、命名、報告可讀性、後續監控建議。
- 若無 blocker，請明確說：`M13-06 可以過；結論 monitor_only 成立，暫不開 production integration。`

## Review 結果（2026-05-18）

Findings：

- `[P3]` member threshold 是用掛牌成員數，不是有效 peer 數。
  - ex-self 計算本身正確：`group_sum - self / valid_count - self_valid`。
  - 但 `industry_momentum_20d_ex_self` 有 238 筆只剩 1 個有效 peer。
  - 這不構成 self-inclusion，也不影響 `monitor_only` 結論。

修正：

- `scripts/research_industry_momentum_walkforward.py` 已補有效 peer 統計。
- artifact 已補：
  - `valid_peer_count_min`
  - `valid_peer_count_p10`
  - `rows_with_lt_2_valid_peers`
  - `rows_with_lt_3_valid_peers`
  - `rows_with_lt_5_valid_peers`

Review 結論：

- 未發現阻塞問題。
- leave-one-out / ex-self 已消除 self-inclusion contamination。
- shadow 欄位只在研究腳本與 artifact 內產生，沒有寫回 production ranking CSV/API。
- 沒有進 LightGBM feature list 或 weekly 推薦文案。
- `monitor_only` 合理，暫不開 production integration。

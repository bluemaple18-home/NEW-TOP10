# POST-DAILY-EXTERNAL-REVIEW-00｜Mainline

## Root Question

建立每日事後第三方審核機制，讓 ChatGPT / Gemini 在不接觸內部演算法、權重、feature engineering、訓練資料結構或模型程式碼的前提下，對每日 Top10 推薦結果提出外部操盤檢討與研究假設。

## Positioning

這條主線是 `post-daily review`，不是 ranking、model promotion、production publish 或自動改權重流程。

外部 reviewer 的輸出只能進入：

- 每日事後檢討
- 研究假設池
- 週期 pattern summary
- 後續 shadow / replay 驗證候選

不得直接進入：

- production ranking
- model promotion
- weight change
- deploy decision
- Clawd 正式推薦文案替換

## Existing Foundations

- `docs/architecture/EXTERNAL_REVIEW_CONTRACT.md`
- `scripts/review_chatgpt_chrome.sh`
- `scripts/verify_external_review_contract.py`

## Mainline Slices

1. `POST-DAILY-EXTERNAL-REVIEW-01_review_packet_and_storage`
2. `POST-DAILY-EXTERNAL-REVIEW-02_chatgpt_collector`
3. `POST-DAILY-EXTERNAL-REVIEW-03_gemini_collector`
4. `POST-DAILY-EXTERNAL-REVIEW-04_dual_reviewer_merge`
5. `POST-DAILY-EXTERNAL-REVIEW-05_periodic_research_loop`

## Shared Contract

Reviewer raw responses are stored as evidence first. The local normalizer must convert each response into `external-review.v1`, then validate it:

```bash
.venv/bin/python scripts/normalize_external_review_response.py --provider <chatgpt|gemini> --date YYYY-MM-DD --raw <raw.txt> --packet <review_packet.json> --out <response.json>
.venv/bin/python scripts/verify_external_review_contract.py <response.json>
```

## Artifact Layout

```text
artifacts/external_review/YYYY-MM-DD/
  review_packet_YYYY-MM-DD.json
  chatgpt_raw_YYYY-MM-DD.txt
  chatgpt_response_YYYY-MM-DD.json
  gemini_raw_YYYY-MM-DD.txt
  gemini_response_YYYY-MM-DD.json
  external_review_summary_YYYY-MM-DD.json
  external_review_summary_YYYY-MM-DD.md
```

Weekly / 20-trading-day outputs:

```text
artifacts/external_review/weekly/
artifacts/external_review/research_hypotheses/
```

## Hard Boundaries

- Do not send source code, model objects, training features, hidden feature lists, weights, promotion gates, or internal scoring formula.
- Do not let external reviewer output change ranking, model, report, or publish behavior.
- Do not write to `artifacts/ranking_YYYY-MM-DD.csv`.
- Do not overwrite `models/latest_lgbm.pkl`.
- Do not mark any external review output as `PROMOTION_READY`.

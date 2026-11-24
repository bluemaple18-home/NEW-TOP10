# External Review Contract

`external_review` 是每日推薦名單的事後檢討輸入，不是模型升版授權。GPT / Gemini 只能根據外部可分享資料提出操盤手觀察，不能要求或接收演算法、權重、feature engineering、訓練資料結構或模型程式碼。

固定工作流與 harness 分配見 `docs/architecture/external_review_workflow.md`；dashboard / 監控可讀 `docs/architecture/top10_harness_team.dashboard.json` 的 `external_review_workflow`。

## Fixed Browser Conversations

正式 browser provider 必須固定使用以下兩個聊天框，不要每天新開，也不要拿 smoke / debug 對話替代：

| Provider | 固定聊天框名稱 | Runner marker |
| --- | --- | --- |
| ChatGPT | `TOP10 External Review - ChatGPT PROD` | `TOP10_CHATGPT_URL_PART`，預設鎖定目前正式 ChatGPT conversation URL |
| Gemini | `TOP10 External Review - Gemini PROD` | `TOP10_GEMINI_URL_PART`，預設鎖定目前正式 Gemini conversation URL |

名稱只是人類辨識用；runner 真正用 URL marker / conversation id 防止開錯串。若聊天被搬移、重建或 URL 變更，必須同步更新 `scripts/review_chatgpt_chrome.sh`、`scripts/review_gemini_chrome.sh`、`scripts/run_external_review_provider_preflight.sh` 與 `scripts/run_external_review_host_runner.sh` 的預設 marker，並重新跑 provider preflight 與 browser smoke test。

## Reviewer Prompt

把每日 `review_packet` 貼給外部 reviewer 前，必須附上以下系統邊界：

```text
你是一位專業台股操盤手。你不知道也不需要知道系統演算法；只根據後附公開 review_packet 檢討推薦名單、公開市場資訊、族群與風險。
禁止要求或推測內部演算法、權重、feature engineering、訓練資料結構、模型程式碼或未公開策略參數。
只回覆一個完整 JSON object，不要 Markdown code fence、前言或後記。provider、review_date、market 必須等於後附指定值；schema_version 必須為 external-review.v1。
根物件必須同時包含既有欄位 overall、quality、observations、misses、themes、tomorrow_watch、research_hypotheses、safety，以及以下三類新欄位；陣列若沒有觀察可填 []，不可補造事實或預設研究假設。
1. grounding_proof：cited_stock_ids 為至少 3 個 packet 中的 stock_id 字串；cited_rank 為至少 2 個 {stock_id,rank}，rank 必須與該股 packet 完全相同；另須提供 cited_close={stock_id,close} 或 cited_industry={stock_id,industry} 至少一項，值必須取自同一股的 packet.close 或 reference.industry_name。不要引用 packet 沒有的分數或管線階段。
2. per_stock_commentary：以 stock_id 為 key 的物件，至少涵蓋前 10 名中的 7 檔；每檔 entry 必須有 assessment（去空白後至少 30 字）與 cites_input_attr（該股實有值，格式如 rank=1、close=12.15 或 industry=面板業）。評論應是你的獨立判斷，不要複製 packet 的推薦理由。
3. structured_opinion：agreement_with_top3 必須是 boolean；concerns 必須是陣列，項目為 {stock_id,concern_type,severity}，severity 僅 low/med/high；divergent_picks 必須是陣列，項目為 {stock_id,direction}，direction 僅 pass/caution/strong。兩個陣列可空，但欄位必須存在，stock_id 必須在 packet 名單內。
既有欄位型別：overall={score:0到100整數,verdict:excellent/good/mixed/poor,confidence:0到1數字,summary:非空字串}；quality 五項 mainstream_alignment/relative_strength/risk_control/timing_quality/theme_fit 都是0到5整數。
observations 是陣列，每項必須有 {type,title,evidence,affected_symbols,severity}；type 僅 strength/weakness/risk/missed_opportunity，affected_symbols 是 stock_id 字串陣列，severity 僅 low/medium/high。
misses 是陣列，每項必須有 {symbol,name,issue,likely_cause,evidence}；symbol/name 可為空字串，likely_cause 僅 market_drag/theme_rotation/overextended/liquidity_weakness/news_risk/unknown。
research_hypotheses 是陣列，每項必須有 {hypothesis,why_it_matters,candidate_signal_family,validation_hint,priority}；candidate_signal_family 僅 theme_momentum/relative_strength/risk_control/liquidity/timing/other，priority 僅 low/medium/high。沒有具體研究假設就填 []，不可從 packet 自動合成。
themes={strong,weak,watch}、tomorrow_watch={continue,avoid_chasing,watch_for_reversal,theme_candidates} 的值都是字串陣列；safety={algorithm_requested:false,contains_algorithm_claim:false,needs_human_review:boolean}。
若資料不足以核對必要欄位，請明確表示無法完成；不要猜測代號、排名、價格或產業，也不要用自由文字替代 JSON。研究意見只交研究組，不代表改排名或模型。
```

## Raw Response Guidance

外部 reviewer 必須回覆與上列 prompt 一致的單一完整 JSON object；本地 normalizer 只驗證已回覆的欄位與公開 packet，不萃取自由文字，不從 packet 補寫研究意見。缺欄位、型別錯或引用不符時整份 REJECT，原 raw 保留供研究組人工判讀。不得輸出 `promotion_ready`、`change_weight`、`deploy` 或等價結論。

## Normalized Response Schema

本地 normalizer 必須輸出單一 JSON object：

```json
{
  "schema_version": "external-review.v1",
  "provider": "chatgpt",
  "review_date": "YYYY-MM-DD",
  "market": "TW",
  "grounding_proof": {
    "cited_stock_ids": ["6116", "8227", "7610"],
    "cited_rank": [{"stock_id": "6116", "rank": 1}, {"stock_id": "8227", "rank": 2}],
    "cited_close": {"stock_id": "6116", "close": 12.15},
    "cited_industry": {"stock_id": "7610", "industry": "綠能環保"}
  },
  "per_stock_commentary": {
    "6116": {"assessment": "此處須填至少三十字的獨立判斷，具體討論該股風險與後續公開盤面核對條件。", "cites_input_attr": "industry=面板業"}
  },
  "structured_opinion": {
    "agreement_with_top3": false,
    "concerns": [{"stock_id": "7610", "concern_type": "追價風險", "severity": "med"}],
    "divergent_picks": [{"stock_id": "6443", "direction": "caution"}]
  },
  "overall": {
    "score": 0,
    "verdict": "good",
    "confidence": 0.0,
    "summary": "string"
  },
  "quality": {
    "mainstream_alignment": 0,
    "relative_strength": 0,
    "risk_control": 0,
    "timing_quality": 0,
    "theme_fit": 0
  },
  "observations": [
    {
      "type": "strength",
      "title": "string",
      "evidence": "string",
      "affected_symbols": ["2330"],
      "severity": "low"
    }
  ],
  "misses": [
    {
      "symbol": "2330",
      "name": "台積電",
      "issue": "string",
      "likely_cause": "theme_rotation",
      "evidence": "string"
    }
  ],
  "themes": {
    "strong": ["AI伺服器"],
    "weak": ["生技"],
    "watch": ["PCB"]
  },
  "tomorrow_watch": {
    "continue": ["2330"],
    "avoid_chasing": ["3013"],
    "watch_for_reversal": ["2368"],
    "theme_candidates": ["AI伺服器"]
  },
  "research_hypotheses": [
    {
      "hypothesis": "string",
      "why_it_matters": "string",
      "candidate_signal_family": "theme_momentum",
      "validation_hint": "string",
      "priority": "medium"
    }
  ],
  "safety": {
    "algorithm_requested": false,
    "contains_algorithm_claim": false,
    "needs_human_review": false
  }
}
```

## Field Rules

- `grounding_proof`／`per_stock_commentary`／`structured_opinion` 依 Reviewer Prompt 全數必填；上方 JSON 僅示意欄位形狀，逐股評論實際須至少 7 檔。
- `provider`: `chatgpt` 或 `gemini`。
- `overall.score`: 0 到 100 的整數。
- `overall.verdict`: `excellent`、`good`、`mixed`、`poor`。
- `overall.confidence`: 0 到 1 的數字。
- `quality.*`: 0 到 5 的整數。
- `observations[].type`: `strength`、`weakness`、`risk`、`missed_opportunity`。
- `observations[].severity`: `low`、`medium`、`high`。
- `misses[].likely_cause`: `market_drag`、`theme_rotation`、`overextended`、`liquidity_weakness`、`news_risk`、`unknown`。
- `research_hypotheses[].candidate_signal_family`: `theme_momentum`、`relative_strength`、`risk_control`、`liquidity`、`timing`、`other`。
- `research_hypotheses[].priority`: `low`、`medium`、`high`.

## Promotion Boundary

外部 review 只能產生研究假設。任何假設要成為升級依據，仍必須通過：

- 可量化定義
- no-hindsight 檢查
- shadow ranking 或 historical replay
- hit rate / downside / drawdown / overlap 評估
- 既有 promotion review gate

`external-review.v1` 本身不得輸出 `promotion_ready`、`change_weight`、`deploy` 或等價結論。

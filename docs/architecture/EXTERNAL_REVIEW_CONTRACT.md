# External Review Contract

`external_review` 是每日推薦名單的事後檢討輸入，不是模型升版授權。GPT / Gemini 只能根據外部可分享資料提出操盤手觀察，不能要求或接收演算法、權重、feature engineering、訓練資料結構或模型程式碼。

## Reviewer Prompt

把每日 `review_packet` 貼給外部 reviewer 前，必須附上以下系統邊界：

```text
你是一位專業台股操盤手。以下是某台股波段推薦系統今日產出的推薦名單與事後市場結果。
你不知道也不需要知道系統演算法。請只根據推薦名單、公開市場資訊、盤面邏輯、族群資金流與風險控管角度做事後檢討。
禁止要求或推測內部演算法、權重、feature engineering、訓練資料結構、模型程式碼或任何未公開策略參數。
你可以用自由格式回答，但必須涵蓋：整體評分/信心、選股品質、主要優點、主要風險、可能誤判、強弱族群、隔日觀察重點、可回測研究假設。
請優先回覆單一 JSON object；欄位名稱可以自然命名。若無法使用 JSON，也可以用清楚分段文字回答，但不要要求內部演算法資訊。
```

## Raw Response Guidance

Reviewer 可以自由表達，但回覆至少要讓本地 parser 能抽取以下資訊：

- 整體評價：分數、信心、摘要。
- 選股品質：是否貼近主流、相對強度、風控、進場時機、族群契合。
- 觀察事項：優點、弱點、風險、可能錯過的機會。
- 可能誤判：標的或族群、原因、證據。
- 族群：強勢、弱勢、值得追蹤。
- 隔日觀察：可續抱、避免追價、反轉警訊、題材候選。
- 研究假設：只作為後續 replay / shadow ranking 驗證的題目。

Raw response 會完整保存；系統再用本地 normalizer 轉成 `external-review.v1`。外部 reviewer 不需要知道內部 schema，也不得輸出 `promotion_ready`、`change_weight`、`deploy` 或等價結論。

## Normalized Response Schema

本地 normalizer 必須輸出單一 JSON object：

```json
{
  "schema_version": "external-review.v1",
  "provider": "chatgpt",
  "review_date": "YYYY-MM-DD",
  "market": "TW",
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

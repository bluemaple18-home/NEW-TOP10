# M4-01：技術 + 事件 + 基本面訓練資料契約

狀態：`completed`
完成日期：`2026-05-17`

任務ID：`M4-01`
卡片類型｜派工對象：模型資料契約｜另一個 coding model
請讀：`app/agent_b_modeling.py`、`app/pipeline/validation.py`、`app/fundamentals/`、`app/data/fundamental_repository.py`、`docs/architecture/MODEL_ROADMAP.md`
任務目的：建立 LightGBM 可使用的合併特徵資料框，包含技術、事件、基本面，且不破壞日頻 `trade_date + stock_id` 唯一鍵。
證據路徑：新增或更新 `scripts/verify_model_foundation.py` / `scripts/verify_review_fixes.py`，輸出可被 review 引用。

## 範圍

- 建立清楚的 feature group 定義：`technical`、`event`、`fundamental`。
- 基本面資料只讀 `data/fundamentals/{stock_id}.json` 或現有 cache/repository，不可在訓練流程即時爬 Goodinfo。
- 合併鍵一律使用 `trade_date + stock_id`；若基本面是年度或季度資料，必須明確 forward-fill / as-of join 規則，且不可偷看未來。
- 缺基本面 cache 的股票不能讓流程炸掉；應產生缺值或預設欄位，並在 metadata 記錄 coverage。

## 不做

- 不訓練新模型。
- 不改 UI。
- 不改排名分數。

## 驗收

- 有一個可重用的資料準備入口，讓 `M4-02` 可以直接取得合併後訓練 frame。
- 合併後資料仍通過 `trade_date + stock_id` 唯一性檢查。
- 基本面欄位有固定命名，例如 `fundamental_roe`、`fundamental_gross_margin`、`fundamental_debt_ratio`。
- 產出 feature metadata：各 group 欄位清單、coverage、缺值比例。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate
```

## 完成紀錄（2026-05-17）

- `app/modeling/feature_contract.py` 提供 `build_m4_feature_frame()` 與 `candidate_feature_columns()`。
- feature group 已拆為 `technical`、`event`、`pattern`、`fundamental`。
- 基本面只讀 `FundamentalRepository` cache，沒有在訓練 path 即時爬外部資料。
- 合併鍵維持 `trade_date + stock_id`，並有 duplicate key regression。
- 基本面 as-of 規則保留 `available_from`，驗證 early date 不偷看未來資料。
- 缺基本面資料會保留 nullable 欄位，不讓流程炸掉。

### 驗證結果

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate
```

結果：通過。

重點輸出：

- `MODEL_FOUNDATION_OK specs=11`
- `REVIEW_FIXES_OK`
- `features: rows=115283, cols=96, stocks=1967, ok=True`
- `events: rows=115283, cols=15, stocks=1967, ok=True`
- `universe: rows=65128, cols=96, stocks=1151, ok=True`

已知非阻塞 warning：

- 最新日期 `ma20` / `bb_middle` 長週期覆蓋率偏低，屬 UQ-09 已 gate 的資料源 coverage warning，不影響本卡 feature contract 驗收。

## Review 重點

- 是否有任何未來基本面資料 leakage。
- 是否在 request path 或訓練 path 即時爬外部網站。
- 是否讓同股同交易日多筆資料重新混進 label。

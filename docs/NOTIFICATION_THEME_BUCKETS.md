# 訊息版資金主題分類

`config/notification_industry_buckets.csv` 是 New Clawd 訊息版使用的全量產業主題對照表。

`config/notification_theme_buckets.csv` 是 fallback 規則表，只在未來出現新產業、但全量表還沒補上時輔助判斷。

它只用在每日通知的「今日大盤與資金」段落，不影響模型分數、排名、頁面資料或原始產業概念。

## 設計目的

每日通知不能直接把模型資料或細產業全部攤開，否則會變成一串小白看不懂的分類。

主表把原始 `industry_name` 聚合成比較像操盤手會講的盤面主題，例如：

- `機殼`、`電子連接相關`、`電池或電源` -> `AI硬體零組件`
- `IC生產製造`、`IC設計服務` -> `半導體/IC`
- `網通設備組件` -> `網通光通訊`

## 主表欄位

`config/notification_industry_buckets.csv`

- `industry_name`：來自 `data/reference/stock_industry_map.csv` 的原始產業名稱。
- `notification_bucket`：訊息中顯示的資金主題名稱。
- `notes`：給維護者看的說明，不會出現在通知訊息。

## Fallback 欄位

`config/notification_theme_buckets.csv`

- `priority`：比對順序，數字越小越優先。
- `bucket`：訊息中顯示的資金主題名稱。
- `industry_keywords`：用 `|` 分隔的產業關鍵字，對應 `industry_name`。
- `concept_keywords`：用 `|` 分隔的概念關鍵字，對應 `concept_tags`。
- `notes`：給維護者看的說明，不會出現在通知訊息。

## 覆蓋驗證

修改對照表後請跑：

```bash
uv run --with-requirements requirements.txt python scripts/verify_notification_theme_buckets.py
```

這個檢查會確認 `stock_industry_map.csv` 裡所有股票的 `industry_name` 都能對到 `notification_bucket`。

## 維護原則

- 每個 `industry_name` 都必須在主表有一列。
- fallback 只處理新資料過渡期，不應取代主表。
- 不要在 fallback 放太泛的詞，例如單獨的 `台積電`、`Apple`、`電子`。
- 若一個主題每天都只吃到一檔，代表分類可能太細，要考慮合併。
- 這是訊息版分類，不是研究報告分類；名稱要讓股市新手看得懂。

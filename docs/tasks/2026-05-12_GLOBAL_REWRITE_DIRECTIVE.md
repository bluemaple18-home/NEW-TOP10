# GLOBAL：全專案翻修授權指令

任務ID：`GLOBAL-REWRITE-DIRECTIVE`
用途：給任何接手模型先讀，避免被舊架構綁住。

## 核心原則

本專案允許大幅重構，必要時可以翻掉既有 code。不要為了維持舊技術債而扭曲新架構。

## 可以翻掉或重寫

- Streamlit 舊 UI、舊頁面結構、舊互動方式。
- 前端 component/layout/state/API loader。
- 後端 API routing、service/data 分層的 glue code。
- ranking 輸出格式，只要保留或提供相容欄位讓 UI 不斷線。
- 報告產生器、CLI wrapper、automation glue。
- 技術債很重、測試不足、命名混亂的非核心模組。

## 需要保護

- 核心演算法語意：label 定義、walk-forward、purge、ranking / risk / portfolio 的金融邏輯。
- 回測績效隔離：read API / UI 不可同步觸發回測長任務。
- 資料契約：日頻資料必須守 `trade_date + stock_id` 唯一鍵。
- 無 leakage：基本面、事件、label、validation 不可偷看未來。
- 外部資料：Goodinfo / 外部來源只允許離線匯入或 cache，不可在 UI/API request path 即時爬。
- 驗證腳本：改完必須補或更新 regression check。

## 改寫紀律

- 先看舊 code 再改，不准憑印象亂翻。
- 可以重寫，但要能說清楚取代了什麼、為什麼舊做法不保留。
- 每次只做當前任務卡範圍；不要順手跨卡做完全部。
- 若核心演算法也要調整，必須明確列出金融假設、資料影響、回測/驗證方式。
- 不追求向舊 UI 相容；追求新架構清楚、可測、可 review。

## 對接手模型的短指令

```text
這個專案允許翻修。請先讀任務卡與相關舊 code，再決定保留或重寫。
除了核心演算法語意、回測隔離、trade_date+stock_id 資料契約、無 leakage 原則與驗證腳本外，其餘架構/UI/glue code 都可以重構或重寫。
做完一張卡就停，回報改動、驗證、風險，等待 review。
```


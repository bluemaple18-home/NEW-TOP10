# UI Refactor Architecture

## 目標

本文件說明 UI 大翻修後的分層邊界。核心原則是：前端只依賴穩定 contract，後端用 service/API 包住既有資料與演算法，回測績效獨立成 domain，避免和即時看盤、排行、圖表資料流互相耦合。

本階段只定義架構與責任邊界，不要求一次完成所有實作。

## 分層總覽

```text
web/frontend/src/{app,components,features,charts,lib}
  ↓ 只消費 API 回傳的圖表資料 contract
app/api
  ↓ HTTP routing，只做 request/response 邊界
app/services
  ↓ 組裝 use case 與 API response
app/data
  ↓ 讀取既有檔案、快取、外部資料來源
app/contracts
  ↓ 定義前後端共享資料形狀
app/backtesting
  ↓ 回測績效 domain，與 market ranking / chart flow 隔離
```

## `app/contracts`

`app/contracts` 是前後端可以依賴的資料契約層，負責定義 API response 的穩定形狀，例如：

- ranking summary / ranking item
- stock OHLCV / candle series
- indicator series metadata
- backtesting summary / equity curve / trade statistics

此層不讀檔、不查 API、不執行策略，也不包含 UI 狀態。所有跨層資料都應先落在 contract，再由 service 組裝，避免前端直接理解 parquet、csv、DataFrame 欄位或內部模型欄位。

## `app/data`

`app/data` 是資料存取層，只負責讀取和轉換既有資料來源，例如本機檔案、快取、外部市場資料 API 或預先產出的回測結果。

此層應保持薄而可替換：

- 可以知道資料在哪裡。
- 可以處理資料來源格式差異。
- 不決定 UI 要顯示什麼。
- 不組裝最終 API response。
- 不同步觸發長時間任務。

## `app/services`

`app/services` 是 use case 組裝層，負責把 data repository 回來的資料整理成 contract。UI 需要的 ranking、K 線資料、指標資料與回測摘要，都應由 service 做邊界整理後再交給 API。

此層可以處理：

- 欄位命名與 contract 對齊。
- 缺值、排序、時間窗、筆數上限等 API 層規則。
- 將多個資料來源組合成單一 response。
- 將 domain error 轉成 API 可理解的錯誤狀態。

此層不應直接綁定前端元件，也不應把長時間訓練、抓取、回測流程塞進同步 request path。

## `app/api`

`app/api` 是 HTTP routing 層，只做薄邊界：

- 接收 request。
- 呼叫 service。
- 回傳 contract。
- 處理 HTTP status / error envelope。

API 不直接讀 parquet/csv，不直接操作 DataFrame，不包含策略或回測核心邏輯。所有 read API 都必須保持可快速回應；如果資料不存在，應回報狀態或讀取已產出的 artifact，不應在 request 中同步啟動長任務。

## `app/backtesting`

`app/backtesting` 是回測績效 domain，必須和 market ranking、即時看盤、K 線圖表資料流隔離。

隔離原因：

- 回測通常是長任務，不能被只讀頁面載入同步觸發。
- 回測資料有自己的 artifact、版本、期間、策略參數與績效口徑。
- 即時排行或 K 線資料更新，不應隱性改變已產出的回測績效。
- UI 檢視績效時應讀取已完成結果，而不是重新計算。

建議邊界：

- `app/backtesting` 負責回測 domain model、結果讀取、績效統計口徑與 artifact metadata。
- `app/services` 提供 backtesting read service，將回測結果轉成 contract。
- `app/api` 提供只讀績效 API，例如 summary、equity curve、trades、drawdown。
- 長時間回測任務應由離線 job、CLI、排程或明確任務入口觸發，不由 UI read API 觸發。

## `web/frontend/src/{app,components,features,charts,lib}`

前端分層以 `app`、`components`、`features`、`charts`、`lib` 為主：

- `app`：App shell、頁面組裝與頂層狀態。
- `components`：不含業務耦合的共用 UI 元件。
- `features`：ranking、stock-detail、backtesting 等業務畫面模組。
- `charts`：K 線工作台與圖表互動元件。
- `lib`：formatters、純函式與共用工具。

`charts` 與 `lib` 建議放置和圖表互動、座標換算、資料轉換、viewport 控制相關的純前端邏輯。

此層可以包含：

- candle / indicator series 的前端轉換工具。
- pan / zoom / visible range 計算。
- chart scale、crosshair、tooltip 的純函式。
- chart component 可共用的 formatting helper。

此層不應：

- 直接呼叫後端 API。
- 理解後端檔案格式。
- 觸發回測、訓練或資料抓取。
- 混入 ranking 或 backtesting domain 的商業規則。

前端 component 應透過 feature-level loader 或 hook 取得 API contract，再把資料交給 `charts/lib` 做純圖表轉換，讓圖表互動可以獨立測試。

## 只讀 API 與長任務邊界

UI refactor 後，API 需要明確分成「讀取已存在狀態」與「觸發長任務」兩類。一般頁面載入、切換股票、讀取排行、讀取 K 線、讀取回測績效，都應屬於只讀 API。

只讀 API 的規則：

- 不同步觸發回測。
- 不同步觸發模型訓練。
- 不同步觸發大量市場資料抓取。
- 不在 request path 內產生不可預期的大型 artifact。
- 只讀取已存在資料或回報資料尚未就緒。

長任務應有明確入口與狀態追蹤，例如 CLI、排程、背景 worker 或單獨的 command API。若未來需要 UI 觸發長任務，也必須走非同步 job model：先建立 job，回傳 job id，再由 UI 輪詢狀態或讀取完成 artifact。

## 推薦資料流

### 市場排行 / K 線

```text
app/data
  → app/services
  → app/contracts
  → app/api
  → frontend feature loader
  → chart/list components
```

### 回測績效

```text
offline backtesting job
  → backtesting artifact
  → app/backtesting
  → app/services
  → app/contracts
  → app/api read endpoint
  → frontend performance view
```

重點是 UI 只讀 `backtesting artifact` 的結果，不在績效頁面載入時重新執行回測。

## 架構守則

- Contract 先行：前端依賴 contract，不依賴後端內部資料格式。
- API 保持薄：routing 不承擔資料處理或 domain 邏輯。
- Service 組裝 use case：跨資料來源整合放在 service。
- Data 只管來源：資料位置、格式與讀取細節留在 data layer。
- Backtesting 隔離：績效資料、artifact、統計口徑與即時 market flow 分開。
- Read API 不觸發長任務：頁面載入必須可預期、快速、可重試。
- Chart lib 純前端：圖表互動邏輯可測，不知道後端檔案或任務流程。

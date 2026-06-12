# RESEARCH-MAP-01 遊戲化研究戰爭迷霧地圖

## Root Question

如何把 autonomous research 的大量策略組合研究，做成一個像遊戲開圖一樣的進度地圖，讓 PM 一眼看懂：

- 目前總研究宇宙多大
- 已探索多少
- 哪些組合已淘汰
- 哪些組合有有效 insight
- 哪些組合值得下一步追
- 哪些區域仍是戰爭迷霧

## 背景

目前已建立：

- `scripts/run_daily_research_quota.sh`
- `scripts/verify_daily_research_quota.py`
- `scripts/build_research_campaign_progress.py`

目前 campaign snapshot 類似：

```text
total topics: 73
processed topics: 24
pending topics: 49
progress: ########................
follow-up signals: 1
```

但這只是文字/JSON，不夠直覺。PM 想要的是遊戲化介面：

- 像星圖 / 科技樹 / 戰情室
- 每個研究節點會亮燈
- 有效 insight 亮不同顏色
- 跑完後整張地圖逐步點亮
- 未來可以擴增更大的理論組合宇宙

## 目標

建立第一版靜態 HTML dashboard：

```text
artifacts/research_map/index.html
```

第一版不需要 server，不接正式 UI，不接 live 排程。

## 視覺方向

採用：

```text
太空星圖 + 科技樹 + 操盤戰情室
```

氣氛：

```text
遊戲化但仍是金融研究工具
```

## 資料來源

優先讀：

- `artifacts/autonomous_research/research_campaign_progress_YYYY-MM-DD.json`
- `artifacts/autonomous_research/autonomous_research_daily_quota_YYYY-MM-DD.json`
- `artifacts/autonomous_research/topic_registry.json`
- `artifacts/autonomous_research/run_history.json`

資料不存在時可產生 fixture fallback，但頁面必須清楚標示 `fixture`，不可偽裝真資料。

## 燈號規則

節點狀態顏色：

```text
fog gray: 未探索
blue: 已探索，但只有普通資訊
red: 明確淘汰
yellow: 有報酬但風險也升高，需要 follow-up
green: 有有效 insight
purple: 可進下一階段研究
gold: 候選主線突破口
```

第一版至少要支援：

- 未探索
- 已淘汰
- 有 follow-up signal
- pending
- low information

## 地圖層級

第一版採兩層：

1. 外層：topic / strategy family 節點
2. 內層：點選 topic 後顯示該 topic 的 scenario summary

第一版不要求畫出完整 5,913 個 scenario 小點，但需在 inspector 顯示：

- ranking topic 數
- 每個 topic 的 scenario count，例如 81
- 估算 scenario universe，例如 `topic_count * 81`
- 已處理 topic 數與 scenario 估算數

## 必要畫面

### 1. HUD 總覽

需顯示：

- total topics
- processed topics
- pending topics
- follow-up signals
- rejected topics
- estimated scenario universe
- progress bar

### 2. 星圖主畫面

需顯示策略家族群：

- ranking source
- entry / setup
- exit rule
- capital / sizing
- regime
- sector / industry
- liquidity
- warning / message

每個群下面顯示 topic 節點。

### 3. 右側 Inspector

點選節點後顯示：

- topic id
- family
- status
- last decision
- run count
- candidate dir
- next action
- score / return / drawdown delta，如果資料有
- scenario grid summary

### 4. Mission Queue

顯示下一批建議研究：

- topic id
- family
- score
- ranking file count
- 為什麼排進下一批

### 5. Legend

必須有燈號說明，讓 PM 不用猜顏色。

## 邊界

不得：

- 修改模型
- 修改 `models/latest_lgbm.pkl`
- 修改 production ranking
- 修改 `risk_adjusted_score`
- 修改 Clawd live 推播
- 宣稱任何策略可 promotion

可以：

- 新增 dashboard builder script
- 新增靜態 HTML / CSS / JS artifact
- 新增 verifier
- 新增 fixture sample，只能標示 fixture

## 建議實作

新增：

```text
scripts/build_research_fog_map.py
scripts/verify_research_fog_map.py
```

產出：

```text
artifacts/research_map/index.html
artifacts/research_map/research_fog_map_YYYY-MM-DD.json
artifacts/research_map/research_fog_map_verification_latest.json
```

## 驗收條件

必須通過：

```text
.venv/bin/python -m py_compile scripts/build_research_fog_map.py scripts/verify_research_fog_map.py
.venv/bin/python scripts/build_research_fog_map.py --date 2026-06-11
.venv/bin/python scripts/verify_research_fog_map.py --date 2026-06-11
git diff --check
```

若有開 browser 驗收，需確認：

- HTML 可打開
- HUD 數字與 source JSON 對齊
- 節點燈號有顯示
- 點選節點 inspector 會更新
- legend 存在
- 沒有 production / promotion 誤導文案

## 第一版成功定義

PM 打開頁面後，3 秒內能知道：

```text
現在研究地圖開了多少
哪裡有有效 insight
下一批要打哪裡
還有多少霧沒開
```

## 派工卡

```text
任務ID：RESEARCH-MAP-01
卡片類型｜派工對象：Gamified Research Dashboard｜Codex
請讀：docs/tasks/2026-06-11_RESEARCH-MAP-01_gamified_fog_of_war_dashboard.md、scripts/build_research_campaign_progress.py、scripts/run_daily_research_quota.sh
任務目的：建立 artifacts/research_map/index.html，把 autonomous research campaign 變成遊戲化戰爭迷霧進度地圖
證據路徑：artifacts/research_map/index.html、artifacts/research_map/research_fog_map_YYYY-MM-DD.json、artifacts/research_map/research_fog_map_verification_latest.json
```

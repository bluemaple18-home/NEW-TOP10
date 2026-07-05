# MARKET-DEFENSE-01｜大盤壓力防守閘門研究

日期：2026-06-29

## Root Question

每日 Top10 在大盤快速轉弱時，不應只回答「今天還有哪 10 檔」。

本研究要回答：

```text
當大盤進入短線壓力狀態時，Top10 是否仍可列出？
若可以列出，哪些檔只能當候補？
總曝險、主攻檔數、推播語氣應該如何降級？
```

這不是使用者指定「幾根黑 K」後直接寫規則。研究團隊要自己定義候選壓力指標，提出可回測的防守 policy，交給 PM 審核。

## 背景

2026-06-22 到 2026-06-26 的正式 artifacts 顯示：

```text
2026-06-22 ~ 2026-06-25：market_regime = NEUTRAL，gross_exposure = 65%，cash = 35%
2026-06-26：market_regime = RISK_OFF，gross_exposure = 35%，cash = 65%
```

系統不是完全沒有風控，但正式防守狀態到 2026-06-26 才出現。PM 的質疑是合理的：大盤連續轉弱時，推播層應更早進入防守語言與降曝險，而不是等到 market breadth 慢慢跌破既有門檻。

## 前置研究結論

既有 exit / capital 研究不能直接拿來當大盤防守規則，但提供三個邊界：

1. 個股機械停損不是預設解。
   - `CAPITAL-REALISM-02` 顯示初版 drawdown state 18 組測試全輸 fixed40，不能直接上。
   - 下一步應拆成 warning channel，不做個人化賣出指令。
2. 粗暴降低總曝險是風控候選，不是 alpha 候選。
   - `gross55` 長區間可降低回撤，但會犧牲報酬。
3. 小白配置已有候選節奏。
   - `CAPITAL-REALISM-06` 建議下一輪 shadow 使用 `p12_open8_new2`：每檔最多 12%、最多 8 檔、每天最多新進 2 檔。

## 初步資料切片

用現有資料做 quick slice：

```text
ranking source：artifacts/backtest/historical_rankings_current_model_batch_dense_2023-11-21_2026-05-15
feature source：data/clean/features.parquet
sample：253 ranking days，2025-05-02 ~ 2026-05-15
market proxy：全股票等權日報酬、MA20 廣度、20 日高點回撤
outcome：Top10 D+1 進場後 1D / 3D / 5D / 10D 平均報酬
```

Baseline：

```text
Top10 fwd 1D：+2.92%
Top10 fwd 3D：+5.01%
Top10 fwd 5D：+6.15%
Top10 fwd 10D：+8.21%
```

較像防守候選的壓力條件：

```text
20 日高點回撤 <= -4%
sample days：11
Top10 fwd 5D：-2.66%
delta vs baseline：-8.81pp

全市場等權 3 日跌幅 <= -2%
sample days：14
Top10 fwd 5D：+1.77%
delta vs baseline：-4.38pp

連跌天數 >= 3
sample days：13
Top10 fwd 5D：+1.71%
delta vs baseline：-4.44pp

連跌 >= 3 且 3 日跌幅 <= -1.5%
sample days：10
Top10 fwd 5D：+1.64%
delta vs baseline：-4.51pp
```

初步判斷：

```text
不要把「三黑」本身當主規則。
它可以是訊號成分，但核心應是「短線跌幅 / 高點回撤 / 廣度」的組合。
```

## 候選 Policy

### Level 0：NORMAL

條件：

```text
未觸發 Level 1 / Level 2 / Level 3。
```

動作：

```text
沿用既有 Top10 / market_regime / portfolio policy。
```

### Level 1：CAUTION

候選觸發條件：

```text
任一成立：
- 全市場等權 3 日跌幅 <= -1.5%
- 20 日高點回撤 <= -3%
- 連跌天數 >= 2 且 MA20 廣度 <= 45%
```

動作候選：

```text
Top10 照列，但推播改為防守讀法。
主攻最多 5 檔。
每天最多新進 2 檔。
採用 p12_open8_new2 配置語言。
```

### Level 2：DEFENSIVE

候選觸發條件：

```text
任一成立：
- 全市場等權 3 日跌幅 <= -2%
- 20 日高點回撤 <= -4%
- 連跌天數 >= 3 且 3 日跌幅 <= -1.5%
```

動作候選：

```text
Top10 可列出，但不稱為攻擊名單。
主攻最多 3 檔，其餘候補或只等確認。
總曝險上限先測 35% / 45% / 55% 三組。
推播標題需明示「大盤防守」。
```

### Level 3：RISK_OFF_BLOCK

候選觸發條件：

```text
任一成立：
- 全市場等權 5 日跌幅 <= -4%
- 20 日高點回撤 <= -6%
- MA20 廣度 <= 35% 且全市場等權 3 日跌幅 <= -2%
```

動作候選：

```text
Top10 只作觀察清單。
主攻 = 0 或最多 1 檔，由 replay 決定。
總曝險上限先測 20% / 30% / 35%。
禁止使用追價語言。
```

## 必跑驗證

下一輪不可只看命中案例，必須跑完整 replay：

```text
window：
- 2023-11-21 ~ 2026-05-15 長區間
- 2025-11-17 ~ 2026-05-15 近半年
- 2026-06-22 ~ 2026-06-26 事件回放，只做 post-check，不當調參來源

variants：
- baseline production Top10
- defense_message_only：只改主攻/候補/推播語氣，不改買入
- defense_gross_cap_55
- defense_gross_cap_45
- defense_gross_cap_35
- defense_block_primary：Level 3 主攻歸零

metrics：
- total_return
- max_drawdown
- fwd 1D / 3D / 5D / 10D Top10 return
- warning precision / recall
- missed rebound cost
- drawdown avoided
- days in each defense level
- average cash weight
- trade count
```

## 上線邊界

第一階段只允許改「讀法與風控呈現」：

```text
可改：
- market defense level artifact
- daily report risk notes
- publish message wording
- main / confirm / pullback / backup role cap

不可改：
- model
- production ranking score
- Top10 排序
- 個人化賣出通知
- Clawd live send 預設行為
```

若 replay 證明 gross cap 有效，第二階段才考慮接入 portfolio sizing。

## PM 審核點

請 PM 審核的是研究團隊定義的問題與驗證邊界，不是要求 PM 指定門檻：

```text
1. 是否同意把大盤防守從個股出場規則拆出來？
2. 是否同意第一階段只改讀法/警示，不改 ranking score？
3. 是否同意候選門檻以 3 日跌幅、20 日高點回撤、廣度組合為主，而不是單看幾根黑 K？
4. 是否同意 2026-06-22 ~ 2026-06-26 只作事件回放，不拿來調參？
```

## Dispatch Card

```text
任務ID：MARKET-DEFENSE-01
卡片類型｜派工對象：Market Stress Guard Replay｜Research Harness
請讀：docs/tasks/2026-06-29_MARKET-DEFENSE-01_market_stress_guard_research.md
任務目的：建立大盤壓力防守閘門，驗證何時降級 Top10 讀法、主攻檔數與總曝險
證據路徑：artifacts/model_experiments/market_defense_guard_replay_*.json
```

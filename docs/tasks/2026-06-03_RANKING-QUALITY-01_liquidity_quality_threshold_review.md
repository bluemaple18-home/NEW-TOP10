# RANKING-QUALITY-01｜大牛市流動性品質門檻檢討

日期：2026-06-03

## Root Question

`quality_score = avg_value_20d / 30,000,000` 並 clip 到 `0~1`，在大牛市環境下是否太容易滿分，導致排名分數失去區分能力？

## 結論

是，若把 `quality_score` 視為「品質分數」，3000 萬 20 日均成交金額作為滿分門檻偏低。

但不建議直接把 3000 萬硬改成 1 億或 3 億後上 production。比較正確的調整方向是：

1. 將 3000 萬保留為「最低可交易流動性 gate」。
2. 將 `quality_score` 改為「能區分中高流動性股票」的分數。
3. 先做 shadow ranking / replay 驗證，再決定是否接入 production `risk_adjusted_score`。

## 現況證據

目前 `risk_adjusted_score` 的核心公式：

```text
risk_adjusted_score =
  prediction_score
  + setup_score
  + quality_score
  - risk_penalty
```

來源：`app/trading/ranking_policy.py`

目前 `quality_score` 實作：

```text
quality_score = clip(avg_value_20d / 30,000,000, 0, 1)
```

這代表：

- 20 日均成交金額 3000 萬以上，`quality_score = 1.0`
- 20 日均成交金額 3 億、30 億，也同樣是 `quality_score = 1.0`
- 在多頭或大牛市，太多股票會同時拿滿分，欄位失去排序區分能力

8043 蜜望實案例：

```text
2026-06-01:
model_prob=1.0, setup_score=0.6391, quality_score=1.0, risk_penalty=0.0
risk_adjusted_score=2.6391

2026-06-02:
model_prob=1.0, setup_score=0.6643, quality_score=1.0, risk_penalty=0.0
risk_adjusted_score=2.6643
```

8043 排第一的主因仍是 `model_prob=1.0`，但 `quality_score=1.0` 讓它在分數上沒有受到任何流動性區分。

## 專家視角

專家視角：做過交易模型 ranking / portfolio construction 的量化產品負責人。

目前問題不是「3000 萬完全錯」，而是「3000 萬同時扮演最低流動性門檻與滿分品質門檻」。這兩件事應該拆開。

最低流動性門檻回答的是：這檔可不可以交易？

品質分數回答的是：在候選股票裡，它的流動性是否相對更好？

現在的 `quality_score` 比較像前者，但在公式裡卻當成後者使用，且權重最高可到 1 分，與 `prediction_score` 同級。

## 已經對的地方

- 不把基本面硬塞進 `quality_score` 是對的。UQ-05 / UQ-10 已指出基本面 coverage 未通過 ranking gate，不能因為欄位存在就加入正式分數。
- 保留流動性概念也是對的。Top10 若完全不看成交金額，會有可買但不可執行的問題。
- 3000 萬可以作為最低 tradability gate，但不適合作為大牛市滿分品質門檻。

## 建議方案

### 方案 A：拆成 Gate + Percentile Score

類型：品質修正

建議：

```text
liquidity_gate = avg_value_20d >= 30,000,000
quality_score = percentile_rank(avg_value_20d within daily tradable universe)
```

可加保守下限：

```text
quality_score = 0.5 + 0.5 * percentile_rank(avg_value_20d)
```

理由：

- 3000 萬仍可保留為最低可交易門檻。
- `quality_score` 改成相對分數後，在大牛市仍能區分 3000 萬、1 億、10 億成交金額。
- 不需要拍腦袋決定固定滿分門檻。

影響：高

成本：中

風險：

- 大型高流動性股票可能被偏好，需要看是否壓掉中小型強勢股。
- 需要搭配 replay 檢查 Top10 是否過度集中在高成交金額族群。

### 方案 B：Regime-aware 分層門檻

類型：方向升級

建議：

```text
RISK_OFF / NEUTRAL:
  3000 萬 = 0.6
  1 億 = 0.85
  3 億以上 = 1.0

RISK_ON / BIG_BULL:
  5000 萬 = 0.5
  2 億 = 0.85
  5 億以上 = 1.0
```

理由：

- 大牛市資金水位高，流動性門檻應自然提高。
- 小型股仍可入選，但不會因為剛過 3000 萬就拿滿分。

影響：中高

成本：中

風險：

- 需要明確定義 BIG_BULL 或沿用既有 market_regime，避免規則變成第二套流程引擎。
- 固定門檻仍可能隨市場成交金額水位失效。

### 方案 C：Log-scaled 流動性分數

類型：品質修正

建議：

```text
quality_score = log1p(avg_value_20d) normalized between 30M and 500M
```

例如：

```text
30M -> 0.5
100M -> 約 0.7~0.8
500M -> 1.0
```

理由：

- 成交金額通常是長尾分布，log scale 比線性門檻自然。
- 不會讓超大成交金額股票過度壓制其他股票。

影響：中

成本：低中

風險：

- 可解釋性比分層門檻略差。
- 仍需決定 normalization 上下界。

## 建議採用

判斷：微調，但需 shadow-first，不直接上 production。

第一優先建議採用「方案 A：Gate + Percentile Score」。

理由：

- 它最少依賴拍腦袋門檻。
- 能適應牛市、盤整、量縮市場。
- 保留 3000 萬作最低可交易條件，不會破壞原本的風險控制語意。
- 比直接把滿分門檻調到 1 億或 3 億更穩。

## 不建議做的事

- 不建議直接把 `30_000_000` 改成 `100_000_000` 後上線。
- 不建議把基本面欄位重新混入 `quality_score`，除非 UQ gate 重新通過。
- 不建議只因 8043 這個個案而調權重；8043 的主要問題更像 `model_prob=1.0` 是否校準飽和。

## 驗證條件

Shadow 實驗應至少產出：

```text
production_rank
shadow_rank
rank_delta
production_quality_score
shadow_quality_score
avg_value_20d
model_prob
setup_score
risk_penalty
```

最小驗收：

- 不修改 production `risk_adjusted_score`。
- 不覆蓋 `artifacts/ranking_*.csv`。
- 對 2026-05-26 到 2026-06-02 既有 ranking artifacts 做 replay。
- 檢查 Top10 churn：單日 Top10 替換過多需標記風險。
- 檢查是否把中小型強勢股全部擠出。
- 檢查高流動性股是否改善後續表現或降低不可交易風險。

建議觀察指標：

```text
top10_overlap_rate
top5_overlap_rate
average_avg_value_20d
median_avg_value_20d
hit_rate_if_available
average_forward_return_if_available
max_sector_concentration
top1_change_count
```

## 需要拆出的主線卡

任務ID：RANKING-QUALITY-02
卡片類型｜派工對象：shadow research｜Codex/Clawd
請讀：`app/trading/ranking_policy.py`、本報告
任務目的：建立 liquidity quality shadow score，比較現行 3000 萬滿分與 percentile/log 分數的 ranking 差異
證據路徑：`artifacts/liquidity_quality_shadow_2026-06-03.json`、`artifacts/liquidity_quality_shadow_2026-06-03.md`

## 下一步

先做 shadow，不改正式 ranking。

最小實作方向：

```text
新增研究腳本：
scripts/research_liquidity_quality_shadow.py

輸入：
artifacts/ranking_2026-*.csv
data/clean/features.parquet

輸出：
artifacts/liquidity_quality_shadow_2026-06-03.json
artifacts/liquidity_quality_shadow_2026-06-03.md
```

若 shadow 顯示：

- Top10 變動合理
- 命中或 forward return 不退化
- 流動性明顯改善
- 沒有過度偏向大型股

再考慮開下一張 production integration 卡。

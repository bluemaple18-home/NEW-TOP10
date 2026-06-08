# CAPITAL-REALISM-01｜零股有限本金矩陣

日期：2026-06-04

## Root Question

使用者可以買零股，不一定要買一張。

所以「小白照每日 Top10 買」的主測試口徑，不能再用固定 100 股或資金無上限。

本卡把資金 replay 改成：

```text
買進單位：1 股
賣出單位：1 股
本金：300,000 / 500,000 / 1,000,000
排名：baseline / K8 / K9
出場：fixed40 / TP15 partial runner
盤勢曝險：regime gross
```

## 邊界

```text
research_only = true
不改模型
不改 ranking score
不改 production ranking
不改推播
只整理 replay artifact
```

## 主要結論

```text
odd_lot_policy = ADOPT_AS_DEFAULT_CAPITAL_REPLAY_ASSUMPTION
ranking_decision = KEEP_K9_MINIMAL_OVERLAY_WITH_BASELINE_CONTROL
tp15_partial_runner = REJECT_AS_DEFAULT_EXIT_RULE
```

白話：

```text
零股要當主線，因為小白真的可以零股買。

但零股回測後，K9 不是每個本金都報酬勝出。
K9 比較像「保守替換 1 檔」的排名微調，不是資金與出場規則的解法。

TP15 partial runner 目前也不能當預設。
它太早處理獲利，報酬明顯被吃掉，回撤也沒有穩定改善。
```

## 後續用途

可以做：

```text
之後所有 capital-aware replay 預設 buy_lot_size=1 / sell_lot_size=1
K9 繼續作 official minimal overlay，baseline / K8 留比較組
下一輪主測 entry-zone guard 與 dynamic exit state machine
```

不能做：

```text
不能把 TP15 partial runner 上正式
不能宣稱 K9 解決資金管理
不能用 100 股限制淘汰高價股
```

證據：

```text
artifacts/model_experiments/odd_lot_capital_matrix_report_2026-06-04.json
artifacts/model_experiments/odd_lot_capital_matrix_report_2026-06-04.md
scripts/build_odd_lot_capital_matrix_report.py
scripts/verify_odd_lot_capital_matrix_report.py
```

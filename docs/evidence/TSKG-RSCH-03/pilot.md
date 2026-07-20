# TSKG 概念導入試行

本次只取三種代表情境，不重跑任何研究：

| 案例 | 類型 | 結果 | 解讀 |
|---|---|---|---|
| `research:candidate_ranking` | active research | `NEEDS_EVIDENCE`、非 hard block | 研究可繼續；下一 checkpoint 補 identity/source/time/conflict。 |
| `runtime:base_regime_risk_multiplier` | production reuse | `BLOCKED`、hard block | 現況不受影響；若要再利用或改動 production，先補證據。 |
| `research:overlap_first` | rejected archive | `GRANDFATHERED` | 不重跑、不改寫舊結論。 |

三例共 12 個尚未評估的核心維度；active research 的阻擋率為 0%，reuse checkpoint 的阻擋率為 100%，archive 的重跑率為 0%。這正是期望邊界：研究形成期提示，正式採用時把關，歷史案不翻修。

Checkpoint 建議：`ADOPT`。只採用 evidence layer 與 checkpoint 語意；不接 TSKG runtime，不自動改 queue 狀態，也不改模型或交易訊號。

# Industry overlay quick multi-window diagnostic — 2026-07-23

這份 evidence 回答「能否先快速回測」。可以，但資料契約必須標成 current-model historical research，不能冒充當時真實 production 或 time-split OOS。

| Window | Eligible days | Return uplift | Hit-rate uplift | Concentration |
|---|---:|---:|---:|---:|
| sealed 60 files | 59 | `+0.0034` | `+0.0102` | `0.3356 → 0.3525` |
| recent 100 files | 99 | `-0.0004` | `-0.0263` | `0.3152 → 0.3273` |
| recent 6M / 120 files | 119 | `-0.0017` | `-0.0269` | `0.3109 → 0.3261` |
| long available window | 234 | `-0.0010` | `-0.0145` | `0.3145 → 0.3308` |

固定輸入、來源目錄與 manifest SHA-256 見同目錄 `quick_multiwindow_diagnostic.json`。運算沿用 `research_industry_momentum_walkforward.py` 的 leave-one-out 產業因子與 production-artifact overlay scorer；每日本來 Top10 內比較 Top5，兩臂皆未套交易成本。

## 正確結論

- `industry-shadow-overlay-0.12-v1`：`REJECT_CURRENT_OVERLAY`。短窗 uplift 未達 `+0.005`，且四個窗口集中度都惡化；較長三窗報酬與命中率皆不支持加權。
- 產業 feature family：`UNRESOLVED_RESEARCH_CANDIDATE`。本證據不能推論所有週期、門檻、regime、法人流、非線性交互作用都無效。
- Production：維持 `NO_RANKING_OR_WEIGHT_CHANGE`。
- 下一步不是被動等同一方案累積日期，而是提出不同候選，再跑 time-split／walk-forward、sealed OOS 與成本後驗證。

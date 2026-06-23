# BORROW-SQUEEZE-02 IC design sector history replay

## 任務目的

承接 `BORROW-SQUEEZE-01` 的結果：

```text
2379 replay:
2026-06-16 cap-hit, price / sector not confirmed
2026-06-17 cap-hit + 60/120D high + IC design sector turning strong, composite_signal=True
2026-06-18 cap-hit + high + sector turning strong + volume confirm, strong_composite_signal=True
decision: MONITOR_ONLY
reason: forward return immature; features latest date only 2026-06-18
```

本卡要把 `borrow_squeeze` 從單檔觀察擴大成「IC 設計全族群 + 長歷史 replay」。

目標不是升正式排名，而是判斷這個訊號是否真的有可交易價值。

## 請讀

- `scripts/build_borrow_squeeze_replay_report.py`
- `scripts/verify_borrow_squeeze_replay_report.py`
- `scripts/verify_borrow_squeeze_materialized_features.py`
- `artifacts/model_experiments/borrow_squeeze_replay_2026-06-22.json`
- `artifacts/model_experiments/borrow_squeeze_replay_2026-06-22.md`
- `data/raw/borrow_squeeze/`
- `data/reference/`

## 要回答

```text
IC 設計族群裡，cap-hit + price breakout + sector strength 是否比單純 cap-hit 更有用？
訊號發生後 D+1 / D+3 / D+5 / D+10 forward return 是否有 edge？
false positive 主要發生在哪些條件？
只有 2379 有效，還是族群內多檔都有效？
量能確認是否必要？
60D high / 120D high 哪個更有辨識力？
sector 5D strength 是否真的增加訊號品質？
```

## Replay 範圍

優先順序：

1. IC 設計全族群。
2. 借券 cap-hit 有資料的全期間。
3. 若資料不足，至少覆蓋最近 6 個月。
4. forward return 只使用已成熟日期，不得用未來資料補判斷。

## 訊號分層

至少拆：

```text
borrow_cap_hit_only
borrow_cap_hit_plus_60d_high
borrow_cap_hit_plus_120d_high
borrow_cap_hit_plus_sector_strength
borrow_cap_hit_plus_price_and_sector
borrow_cap_hit_plus_price_sector_volume
```

每層要輸出：

```text
sample_count
stock_count
date_count
forward_return_D1
forward_return_D3
forward_return_D5
forward_return_D10
win_rate
drawdown_proxy / worst_forward_return
false_positive_examples
```

## 明確禁止

- 不准改 production ranking。
- 不准改 `models/latest_lgbm.pkl`。
- 不准改 Clawd live publish。
- 不准把 MONITOR_ONLY 包裝成 promotion evidence。
- 不准用未成熟 forward return 補結論。
- 不准只看 2379 就宣稱族群有效。

## 預期產物

- `artifacts/model_experiments/borrow_squeeze_ic_design_sector_replay_YYYY-MM-DD.json`
- `artifacts/model_experiments/borrow_squeeze_ic_design_sector_replay_YYYY-MM-DD.md`
- `artifacts/model_experiments/borrow_squeeze_ic_design_sector_replay_verification_latest.json`

若需要新增腳本：

- `scripts/build_borrow_squeeze_ic_design_sector_replay.py`
- `scripts/verify_borrow_squeeze_ic_design_sector_replay.py`

## 驗收標準

Verifier 必須確認：

```text
research_only: true
decision in {MONITOR_ONLY, KEEP_FOR_NEXT_REPLAY, REJECT_FOR_NOW}
sample_count present by signal layer
forward return maturity checked
production_impact == NO_PRODUCTION_CHANGE
no PROMOTION_READY
```

若 replay 結果不足：

```text
decision: MONITOR_ONLY
next_action: collect more matured forward returns or widen sector/history window
```

若 replay 結果有明確 edge：

```text
decision: KEEP_FOR_NEXT_REPLAY
next_action: run finite-capital / same-exit / ranking-isolation replay
```

## 完成後下一步

若 `KEEP_FOR_NEXT_REPLAY`：

開 `BORROW-SQUEEZE-03_finite_capital_and_ranking_isolation_replay`。

若仍 `MONITOR_ONLY`：

保留為 warning / research feature，不進 ranking score。

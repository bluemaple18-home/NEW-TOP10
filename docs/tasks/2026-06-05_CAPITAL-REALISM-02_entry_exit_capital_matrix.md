# CAPITAL-REALISM-02｜零股進場 / 出場 / 本金分層矩陣

日期：2026-06-05

## Root Question

每日 Top10 對小白不是只有「挑哪 10 檔」。

還要回答：

```text
小本金可不可以買？
是不是要等比較好的進場狀態？
停利 / 停損 / 續抱怎麼設才不像靠感覺？
```

本卡只做研究，不改正式 ranking / model。

## 測試範圍

```text
variants: baseline / K9
本金: 300,000 / 500,000 / 1,000,000
買賣單位: 1 股
進場 filter: all / non_worsening / improved_only
出場:
  - fixed40
  - TP20 賣 1/3 + 8% close stop + runner drawdown 10%
```

## 邊界

```text
research_only = true
不訓練模型
不覆蓋 models/latest_lgbm.pkl
不改 production ranking
不改 risk_adjusted_score
不改推播
```

## 主要結論

```text
decision = ENTRY_EXIT_POLICY_NOT_READY
fixed40_all = KEEP_AS_CURRENT_COMPARISON_BASELINE
k9_non_worsening = CAPITAL_TIER_CANDIDATE_FOR_500K_ONLY
tp20_runner_stop8 = REJECT_AS_DEFAULT_FOR_NOW
entry_filter_policy = DO_NOT_USE_SINGLE_GLOBAL_FILTER
```

白話：

```text
固定持有 40 天仍是目前最強比較組。

進場 filter 不是不能用，但它跟本金層互動很大：
30 萬 / 100 萬不該直接套 non_worsening；
50 萬的 K9 non_worsening 反而很強。

TP20 runner stop8 目前不能當預設出場。
它有壓風險的能力，但平均報酬被砍太多。
```

## 後續

下一輪不要再只調 TP%。

應測：

```text
entry price guard：D+1 開盤若追太高就不進
分段停損：跌破警戒先降曝險，不一定全出
capital-tier policy：不同本金層可有不同 entry filter / 持股數 / 現金水位
```

## Follow-up 結果

已補測：

```text
entry price guard：D+1 開盤相對入榜日收盤最多追 3% / 5% / 8%
stop policy：8% close stop 全出 / 8% close stop 半出 / 12% close stop 全出
```

結論：

```text
entry_price_guard = NO_EFFECT_IN_CURRENT_HALF_YEAR_SAMPLE
stop_policy = REJECT_MECHANICAL_STOP_AS_DEFAULT
partial_stop = RESEARCH_ONLY
```

白話：

```text
D+1 追價 guard 沒觸發，代表目前問題不是隔天開太高。

機械停損多數降低報酬，而且不穩定降低回撤。
不能直接變成小白預設賣出規則。

下一步要測的是 drawdown state：
只有當個股跌破、排名/族群/大盤也同步轉弱時，才降曝險。
```

## Drawdown State 結果

已補測：

```text
drawdown state：fixed40 + all entry
variants：baseline / K9
本金：300,000 / 500,000 / 1,000,000
runner drawdown：15% / 20% / 25%
```

結論：

```text
drawdown_state = TOO_AGGRESSIVE_CURRENT_ENGINE
decision = DRAWDOWN_STATE_REJECT_AS_DEFAULT
recommendation_channel = NO_CHANGE
warning_channel = NEXT_RESEARCH_TARGET
```

白話：

```text
這版不能直接上。

18 組測試全部輸 fixed40；
平均報酬差 -54.35 個百分點；
回撤也沒有改善。

問題不是「不該停損」。
問題是目前這套 drawdown state 太粗，
會在牛市 / 高檔震盪裡把原本該抱的波段行情太早洗掉。

下一步要把推薦和警告拆開：
推薦仍然是每日 Top10；
警告只追蹤近 7 天入榜股票是否轉弱，
不做個人持倉賣出指令。
```

證據：

```text
artifacts/model_experiments/capital_realism02_report_2026-06-05.json
artifacts/model_experiments/capital_realism02_report_2026-06-05.md
artifacts/model_experiments/capital_realism02_followup_report_2026-06-05.json
artifacts/model_experiments/capital_realism02_followup_report_2026-06-05.md
artifacts/model_experiments/capital_realism02_drawdown_state_report_2026-06-05.json
artifacts/model_experiments/capital_realism02_drawdown_state_report_2026-06-05.md
scripts/build_capital_realism02_report.py
scripts/verify_capital_realism02_report.py
scripts/build_capital_realism02_followup_report.py
scripts/verify_capital_realism02_followup_report.py
scripts/build_capital_realism02_drawdown_state_report.py
scripts/verify_capital_realism02_drawdown_state_report.py
```

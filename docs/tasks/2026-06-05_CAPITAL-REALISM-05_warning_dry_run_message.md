# CAPITAL-REALISM-05｜Warning-only Dry-run Message

日期：2026-06-05

## Root Question

`CAPITAL-REALISM-04` 判定沒有乾淨的 `RISK_ALERT`。

本卡只做：

```text
用已驗證較有方向性的 WEAKENING，
產生一份 warning-only dry-run 訊息。
```

## 邊界

```text
research_only = true
dry_run_only = true
不送推播
不接第二頻道
不改每日推薦
不改 production ranking
不改 risk_adjusted_score
不改模型
不處理個人持倉
RISK_ALERT 暫停輸出
```

## 驗收

```text
scripts/build_capital_realism05_warning_dry_run_message.py 可產 JSON / MD
scripts/verify_capital_realism05_warning_dry_run_message.py 通過
selected_items 只允許 WEAKENING
message 不得出現直接交易指令
```

## 本輪結果

已完成。

```text
decision = WARNING_DRY_RUN_MESSAGE_READY
source_items = 61
weakening_items = 49
selected_items = 12
message_chars = 929
RISK_ALERT = suppressed
```

訊息特性：

```text
只列 WEAKENING
不列 RISK_ALERT
不送推播
不處理個人持倉
不出現直接交易指令
每檔使用原因標籤，避免罐頭句
```

產物：

```text
artifacts/model_experiments/capital_realism05_warning_dry_run_message_2026-06-05.json
artifacts/model_experiments/capital_realism05_warning_dry_run_message_2026-06-05.md
scripts/build_capital_realism05_warning_dry_run_message.py
scripts/verify_capital_realism05_warning_dry_run_message.py
```

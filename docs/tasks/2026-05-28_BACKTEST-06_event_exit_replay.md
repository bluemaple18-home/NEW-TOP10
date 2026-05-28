# BACKTEST-06：Stop / Target Event Exit Replay

## 五行派工卡

任務ID：BACKTEST-06
卡片類型｜派工對象：Backtest / Exit Engine｜Codex
請讀：`scripts/run_portfolio_replay.py`、`scripts/verify_portfolio_replay.py`、`docs/tasks/2026-05-28_BACKTEST-04_overlap_portfolio_replay.md`
任務目的：在 overlap portfolio replay 加入可選停損 / 停利事件出場，驗證動能策略不是只能固定 horizon 到期才賣
證據路徑：`artifacts/portfolio_replay_verification_latest.json`、`artifacts/backtest/portfolio_replay_YYYY-MM-DD.json`

## 範圍

- 新增 `--stop-loss-pct` 與 `--take-profit-pct`，未指定時維持固定 horizon 出場。
- 每個市場 bar 先檢查停損 / 停利事件，再檢查 scheduled horizon close。
- 同一根 bar 同時碰停損與停利時，預設採 `--same-day-hit-priority stop_loss` 的保守假設。
- trade artifact 記錄 `exit_reason` 與 `ambiguous_intraday_order`。
- daily artifact 記錄 `scheduled_exits`、`stop_loss_exits`、`take_profit_exits`。

## 非範圍

- 不做 intraday tick / 分鐘資料路徑推估。
- 不做追蹤停利。
- 不做部分停利。
- 不接 production ranking / model feature。

## 驗收

- synthetic 驗證 stop loss 會在 horizon 到期前出場。
- synthetic 驗證 take profit 會在 horizon 到期前出場。
- synthetic 驗證 event exit contract 寫入 artifact。
- 原本 D+1 open、重疊持倉、gross cap、group cap、OHLC skip regression 仍通過。
- `py_compile` 與 `git diff --check` 通過。

## Review 重點

- 檢查停損 / 停利是否只使用當日 OHLC，不偷看未來。
- 檢查同日雙觸發是否採保守規則，而不是自動挑較好結果。
- 檢查 event exit 是否不會再被 scheduled close 重複出場。
- 確認仍是 replay 研究層，沒有寫回模型或 production ranking。

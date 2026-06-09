# GUARDED-TOP10-REPLAY-02｜Performance Backtest

## Root Question

Guarded Top10 selection replay 已能產出 shadow 名單，但尚未證明它比 production Top10 更可操盤。這張卡只回答績效問題：用固定 Top80 候選池套 tape / RR / chase guard 後選出的 Top10，是否比現行 production Top10 更符合每日推薦產品目標。

## Goal

建立 performance replay，比較 `production Top10` vs `guarded Top10`。

## Required Preconditions

- `GUARDED-TOP10-REPLAY-01A` 已完成。
- `candidate_pool_size` 固定為 `80`。
- Replay 僅使用既有 features 與現有 `models/latest_lgbm.pkl` 做 inference，不重訓。

## Scope

- 可新增 `scripts/backtest_guarded_top10_performance.py`。
- 可新增 `scripts/verify_guarded_top10_performance.py`。
- 可讀取 `artifacts/research/guarded_top10_replay_YYYY-MM-DD.json`。
- 可在缺少 guarded replay artifact 時批次呼叫 replay 腳本產生 shadow artifact。
- 輸出 performance research artifact 到 `artifacts/research/`。

## Test Windows

至少包含：

- 最近 100 個交易日。
- 最近 6 個月。

若資料不足，artifact 必須明確列出可用日期範圍與缺口，不可硬補。

## Metrics

比較 `production Top10` 與 `guarded Top10`：

- D+1 / D+3 / D+5 / D+10 forward return。
- daily Top10 bucket average return。
- hit rate。
- worst daily bucket return。
- max drawdown proxy。
- turnover。
- industry / theme concentration。
- guarded added vs removed performance。
- guard hit quality：被 tape / RR guard 擋掉的股票後續是否比補進股票差。
- regime slice：至少分 BIG_BULL / HIGH_CHOPPY_CONTEXT / OTHER，若 regime artifact 不足則明確標示。

## Decision Output

Artifact 必須給出明確但保守的狀態：

- `GUARDED_OUTPERFORMS_RESEARCH_ONLY`
- `MIXED_MONITOR_ONLY`
- `GUARDED_UNDERPERFORMS`
- `INSUFFICIENT_DATA`

不得輸出 `PROMOTION_READY`。

## Out Of Scope

- 不改正式 `artifacts/ranking_YYYY-MM-DD.csv`。
- 不改 `models/latest_lgbm.pkl`。
- 不改自動推播正式來源。
- 不把 guarded Top10 切成正式 daily ranking。
- 不用此卡調整 guard 門檻；若發現門檻問題，另開 follow-up。

## Acceptance

必須通過：

```bash
.venv/bin/python scripts/backtest_guarded_top10_performance.py --window recent_100
.venv/bin/python scripts/backtest_guarded_top10_performance.py --window recent_6m
.venv/bin/python scripts/verify_guarded_top10_performance.py
.venv/bin/python -m py_compile scripts/backtest_guarded_top10_performance.py scripts/verify_guarded_top10_performance.py
git diff --check
```

## Evidence

- `artifacts/research/guarded_top10_performance_recent_100_YYYY-MM-DD.json`
- `artifacts/research/guarded_top10_performance_recent_100_YYYY-MM-DD.md`
- `artifacts/research/guarded_top10_performance_recent_6m_YYYY-MM-DD.json`
- `artifacts/research/guarded_top10_performance_recent_6m_YYYY-MM-DD.md`

## Result｜2026-06-09

Status: `COMPLETED_RESEARCH_ONLY`

Conclusion: `GUARDED_UNDERPERFORMS`

This card completed the performance backtest boundary. It does not approve production switching.

Evidence produced:

- `artifacts/research/guarded_top10_performance_recent_100_2026-06-09.json`
- `artifacts/research/guarded_top10_performance_recent_100_2026-06-09.md`
- `artifacts/research/guarded_top10_performance_recent_6m_2026-06-09.json`
- `artifacts/research/guarded_top10_performance_recent_6m_2026-06-09.md`

Observed windows:

- `recent_100`: 100 comparable trading days, `2025-12-24` ~ `2026-06-08`.
- `recent_6m`: 112 comparable trading days, `2025-12-08` ~ `2026-06-08`.

Summary:

- D+1 guarded selection improved versus production.
- D+3 / D+5 / D+10 guarded selection underperformed production.
- Guard replacements underperformed blocked model Top10 names at D+5 / D+10.
- `promotion_ready=false`.

Decision:

- Do not promote guarded Top10 as the formal daily selection.
- Keep tape / RR / chase guard available for risk labeling, publish grouping, and copy safety.
- Any future selection change must use a new hypothesis and pass a separate replay/performance card.

Validation run:

```bash
.venv/bin/python scripts/verify_guarded_top10_performance.py
.venv/bin/python -m py_compile scripts/backtest_guarded_top10_performance.py scripts/verify_guarded_top10_performance.py
git diff --check
```

Validation status: `OK`

## Review Fix Rerun｜2026-06-09

Review finding status: `RESOLVED`

The verifier now checks guarded replay date alignment:

- `guarded_top10_replay_YYYY-MM-DD.json` filename date.
- `ranking_date`.
- `regime_history_boundary.end_date`.
- `window.comparable_dates`.
- `guarded_replay_outputs`.

Both performance artifacts were rerun after the verifier hardening:

- `recent_100`: `GUARDED_UNDERPERFORMS`, 100 comparable dates, 100 guarded replay outputs.
- `recent_6m`: `GUARDED_UNDERPERFORMS`, 112 comparable dates, 112 guarded replay outputs.

Validation run:

```bash
.venv/bin/python scripts/backtest_guarded_top10_performance.py --window recent_100
.venv/bin/python scripts/backtest_guarded_top10_performance.py --window recent_6m
.venv/bin/python scripts/verify_guarded_top10_performance.py
.venv/bin/python -m py_compile scripts/backtest_guarded_top10_performance.py scripts/verify_guarded_top10_performance.py
git diff --check
```

Validation status: `OK`

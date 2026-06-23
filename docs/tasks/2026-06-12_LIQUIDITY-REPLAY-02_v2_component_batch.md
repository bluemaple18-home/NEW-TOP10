# LIQUIDITY-REPLAY-02｜V2 星圖流動性 Component Batch Replay

## Root Question

`LIQUIDITY-REPLAY-01` 顯示 liquidity quality universe 有報酬訊號，但嚴格 replay 下回撤與集中度風險太高，不能直接上 production。

現在要把它接到 research map v2 的 `144` 顆 active queue，逐格跑 replay，判斷哪些維度組合值得保留、淘汰或補資料。

## 與星圖關係

本卡不是新世界線。

所有 scenario 必須來自：

```text
artifacts/research_map/research_fog_map_latest.json
active_expansion_queue
stage == LIQUIDITY-REPLAY-02
```

每個完成 scenario 必須回寫：

```text
artifacts/autonomous_research/run_history.jsonl
```

並可由 `scripts/refresh_research_map_from_history.sh` 刷新星圖點燈。

## 本批次範圍

active queue 現況：

```text
total: 144
topic: liquidity_quality_candidate_universe
group_exposure: none / 0.35 / 0.55
regime_gate: ALL / BIG_BULL_ONLY / BIG_BULL_HIGH_CHOPPY / EXCLUDE_RISK_OFF_PANIC
risk_guard: NONE / RISK_OFF_CASH_RAISE / RISK_OFF_DISABLE / PANIC_DISABLE
entry_filter: LOG_GATE / PERCENTILE_GATE / LOG_GATE_NON_WORSENING
```

## Runner 規則

使用：

```text
scripts/run_capital_aware_replay.py
```

每個 scenario 需要跑兩份：

- production baseline ranking
- liquidity candidate ranking

然後比較：

- total return delta
- max drawdown delta
- turnover delta
- concentration delta
- trade count
- skipped reason

## 對應規則

```text
entry_filter=LOG_GATE
  candidate rankings_dir = .../log_gate
  replay entry_filter = all

entry_filter=PERCENTILE_GATE
  candidate rankings_dir = .../percentile_gate
  replay entry_filter = all

entry_filter=LOG_GATE_NON_WORSENING
  candidate rankings_dir = .../log_gate
  replay entry_filter = non_worsening
```

```text
group_exposure=none
  max_group_pct = 0.30

group_exposure=0.35
  max_group_pct = 0.35

group_exposure=0.55
  max_group_pct = 0.55
```

`regime_gate` 以 gross exposure gate 實作：

```text
ALL
  all regimes tradable

BIG_BULL_ONLY
  only BIG_BULL gross > 0

BIG_BULL_HIGH_CHOPPY
  BIG_BULL and HIGH_CHOPPY gross > 0

EXCLUDE_RISK_OFF_PANIC
  risk-off / panic gross = 0
```

`risk_guard` 用 risk-off gross 調整；若與 `regime_gate` 衝突，以更保守者為準。

## 禁止事項

- 不准改 production ranking。
- 不准改模型。
- 不准改 Clawd live push。
- 不准把 batch winner 直接宣稱 production-ready。
- 不准把 unsupported scenario 包裝成已完成。

## 輸出

- `scripts/run_liquidity_replay_v2_batch.py`
- `scripts/verify_liquidity_replay_v2_batch.py`
- `artifacts/research_reviews/liquidity_replay_v2_batch_YYYY-MM-DD.json`
- `artifacts/research_reviews/liquidity_replay_v2_batch_YYYY-MM-DD.md`
- `artifacts/research_reviews/liquidity_replay_v2_batch_verification_latest.json`

## 驗證

Verifier 至少檢查：

- batch source 是 research map v2 active queue。
- batch scenario count <= active queue count。
- 每筆 scenario 都有 v2 dimensions。
- completed scenario 必須有 baseline / candidate artifact。
- completed scenario 必須有 return / drawdown delta。
- run_history append row 必須使用同一個 combo_id。
- `production_impact == NO_PRODUCTION_CHANGE`。
- report 不得包含 `PROMOTION_READY`。

## 第一批執行

先跑 smoke batch：

```bash
.venv/bin/python scripts/run_liquidity_replay_v2_batch.py --date 2026-06-12 --limit 12 --append-run-history
.venv/bin/python scripts/verify_liquidity_replay_v2_batch.py --date 2026-06-12
bash scripts/refresh_research_map_from_history.sh
```

若 smoke 通過，再把 `--limit` 提高到 `144`。


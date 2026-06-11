# STRATEGY-COMPOSE-02｜Ranking Isolation + Regime Normalization

## Root Question

`candidate_ranking + trail10` 不能上線已由 STRATEGY-COMPOSE-01 判定；下一步要拆清楚：

- candidate ranking 本身是否比 production ranking 好？
- BIG_BULL gate 是否真的有價值？
- HIGH_CHOPPY 是負面條件，還是只是樣本不足？

## Scope

### A. Same-Exit Ranking Isolation

production ranking 和 candidate ranking 必須使用同一個 exit rule 比較，至少包含：

- production ranking + trail10
- candidate ranking + trail10
- production ranking + production exit proxy
- candidate ranking + production exit proxy

目的：拆開 ranking source 與 exit rule 的貢獻。

### B. Regime-Gated Equity Normalization

BIG_BULL-only 不可直接和全期 production total return 比。

至少要補：

- same-active-day return comparison
- exposure-adjusted return comparison
- trade-level regime attribution
- BIG_BULL / HIGH_CHOPPY / non-BIG_BULL-non-HIGH_CHOPPY slices

## Non-Goals

- 不改 production ranking。
- 不改 `models/latest_lgbm.pkl`。
- 不改 Clawd 推播。
- 不做 production switch。
- 不新增第二套 promotion gate。

## Expected Outputs

- `scripts/build_strategy_composition_isolation.py`
- `scripts/verify_strategy_composition_isolation.py`
- `artifacts/model_experiments/strategy_composition_isolation_YYYY-MM-DD.json`
- `artifacts/model_experiments/strategy_composition_isolation_YYYY-MM-DD.md`
- `artifacts/model_experiments/strategy_composition_isolation_verification_latest.json`

## Acceptance Criteria

1. 同 exit rule 下比較 production ranking 與 candidate ranking。
2. regime gate 比較不得只用全期 total return。
3. BIG_BULL / HIGH_CHOPPY 都要有樣本數、active-day、exposure-adjusted 指標。
4. 若樣本不足，decision 必須標為 monitor / needs data，不可宣稱有效。
5. Verifier 必須阻擋 production/model/message 變更與 promotion-ready。

## Dispatch Card

```text
任務ID：STRATEGY-COMPOSE-02
卡片類型｜派工對象：Ranking Isolation + Regime Normalization｜Codex
請讀：docs/tasks/2026-06-10_STRATEGY-COMPOSE-01_candidate_trail10_conditional_switch.md
任務目的：補 same-exit ranking isolation 與 regime-gated equity normalization，拆清楚 candidate ranking、trail10 exit、BIG_BULL/HIGH_CHOPPY gate 各自貢獻
證據路徑：artifacts/model_experiments/strategy_composition_isolation_*.json、strategy_composition_isolation_verification_latest.json
```

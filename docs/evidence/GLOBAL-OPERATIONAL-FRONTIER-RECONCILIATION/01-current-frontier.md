# Global Operational Frontier Reconciliation Evidence

日期：2026-09-02

| Lane | Evidence | Reconciled state |
|---|---|---|
| Research A5 | review handoff P0/P1=0；merge `bb617e9` | `MAINLINE_ACCEPTED / INTEGRATED` |
| Research A6 | review handoff P0/P1=0；merge `2b9eccd` | `MAINLINE_ACCEPTED / INTEGRATED` |
| Research B0/C0/BC | `docs/RESEARCH_SPINE_BACKLOG.md` | no active implementation frontier |
| Forecast | merges `ff3d30b`、`9abc159`、`02730a7` | vendor-neutral baseline accepted |
| TimesFM 3 | restricted-shadow preflight only | `DEFERRED / LAST / HOLD` |
| TPEx TSKG | `bc61e5d`、`78134f4`、`c081e36` 與既有 review/reconciliation | `INTEGRATED_CURRENT_DAY_ONLY / REVIEW_GO` |
| Daily incident | separate Codex task | isolated; not duplicated here |
| Overlay shadow | `artifacts/model_experiments/overlay_shadow_daily_status.json`，generated `2026-09-02T03:14:48Z` | background only；Chip `22/60`、Event `9/60`；非 frontier |
| Overlay frozen backtest | `docs/evidence/OVERLAY-ROBUSTNESS-REPLAY-01/artifact.json`；verifier=`OVERLAY_ROBUSTNESS_REPLAY_OK` | Chip historical support uncertain；Event historical support robust；兩者均不直接 promotion |

## Verification

- `tests/test_parameter_learning.py`
- `tests/test_native_evidence_replay.py`
- `tests/test_adaptive_shadow_queue.py`
- `tests/test_research_spine_a6_closure.py`
- `tests/test_research_spine_a6_bridge_removals.py`
- Result：`77 passed`。

本 receipt 只證明 control-state reconciliation；不宣稱遠端即時狀態、production load 或新的模型能力。

# OVERLAY-ROBUSTNESS-REPLAY-01 Evidence

status: GO（historical robustness replay）／PROSPECTIVE WAITING

## Evidence

- artifact：`docs/evidence/OVERLAY-ROBUSTNESS-REPLAY-01/artifact.json`
- artifact SHA-256：`de9efd4d413e83d5cd46dd14147105848919b554a0cc724ecf805edde4e26894`
- generated report：`docs/evidence/OVERLAY-ROBUSTNESS-REPLAY-01/artifact.md`
- paired statistic：overlay 日平均淨報酬減 baseline 日平均淨報酬
- fold-stratified circular block length：10 個 ranking days；不得跨 fold
- bootstrap repetitions：10,000
- deterministic seed：20260723

## Results

| Candidate | Days | Mean delta | 95% CI | P(mean>0) | LOFO positive | Decision |
|---|---:|---:|---:|---:|---:|---|
| Chip 10% | 114 | +0.002740 | [-0.001251, +0.006371] | 0.9115 | 5/5 | HISTORICAL_SUPPORT_UNCERTAIN |
| Event constrained 10% | 55 | +0.005819 | [+0.002715, +0.008958] | 1.0000 | 5/5 | ROBUST_HISTORICAL_SUPPORT |

## Verification

```bash
.venv/bin/python -m py_compile \
  scripts/build_overlay_robustness_replay.py \
  scripts/verify_overlay_robustness_replay.py
.venv/bin/python scripts/build_overlay_robustness_replay.py
.venv/bin/python scripts/verify_overlay_robustness_replay.py
git diff --check
```

## Interpretation

- Event constrained overlay 在固定歷史 replay 上通過較嚴格的相依性調整後不確定性檢查，應優先等待新 prospective 日期。
- Chip overlay 的平均增量與所有 leave-one-fold-out 都為正，但 95% CI 穿越零，不能視為穩健歷史支持。
- 本卡不新增獨立資料；它只量化既有 walk-forward replay 的不確定性。

## Boundary

- prospective shadow 仍為 `0/60`，本卡不得填入或取代該計數。
- `promotion_allowed=false`。
- production model、ranking、feature、weights 未修改。

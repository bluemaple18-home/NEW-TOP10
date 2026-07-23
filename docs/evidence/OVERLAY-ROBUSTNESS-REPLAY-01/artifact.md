# Overlay Historical Robustness Replay

- block length：10
- repetitions：10000
- seed：20260723
- prospective acceptance replacement：false

| Candidate | Days | Mean delta | 95% block-bootstrap CI | P(mean>0) | LOFO positive | Decision |
|---|---:|---:|---:|---:|---:|---|
| chip_overlay_0.10 | 114 | 0.002740 | [-0.001251, 0.006371] | 0.911 | 5/5 | HISTORICAL_SUPPORT_UNCERTAIN |
| event_constrained_overlay_0.10 | 55 | 0.005819 | [0.002715, 0.008958] | 1.000 | 5/5 | ROBUST_HISTORICAL_SUPPORT |

本結果只描述既有歷史 replay 的不確定性；不得取代 seal 後 60 個 prospective OOS 日期。

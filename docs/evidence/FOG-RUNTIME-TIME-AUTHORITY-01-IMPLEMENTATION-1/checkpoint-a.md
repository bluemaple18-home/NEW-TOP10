---
card_id: FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1
checkpoint: A
status: PASS
completed_slices:
  - FRTA-I1-AUTHORITY
  - FRTA-I2-PRODUCER
---

# Checkpoint A

## Evidence

```bash
.venv/bin/python -m pytest -q \
  tests/test_fog_runtime_time_authority.py \
  tests/test_fog_closed_regime_runtime.py
```

Result：`22 passed in 0.06s`。

## Acceptance mapping

- canonical policy hash：
  `67327c40206251adf4d377e76833dfd6261ce4fb3f56c7de0b0bf92c7231e357`
- strict RFC3339 UTC `Z`、Taipei projection、signed exact boundaries：PASS
- `FRTA-REG-RRV-P1-01-PROCESSED-ID`：GREEN
- `FRTA-REG-RRV-P1-03-SOURCE-BASELINE`：GREEN
- `FRTA-REG-TIME-DATE-LINEAGE`：GREEN
- `FRTA-REG-RECEIPT-V3-EXACT`：GREEN
- deterministic v3 producer／canonical weekend fixture：PASS
- v2 relabel：REJECT
- worker／daily shell／plist diff：none at checkpoint
- live LaunchAgent／queue／circuit／scheduler：not touched

status: PASS
next_step: FRTA-I3-VERIFIER
limits: 尚未完成 shell/plist static wiring或 full acceptance

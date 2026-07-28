---
card_id: FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1
checkpoint: B
status: PASS
completed_slices:
  - FRTA-I3-VERIFIER
  - FRTA-I4-WIRING
---

# Checkpoint B

## Evidence

Targeted Python：

```bash
.venv/bin/python -m pytest -q \
  tests/test_fog_runtime_time_authority.py \
  tests/test_fog_closed_regime_runtime.py \
  tests/test_daily_research_quota_verifier.py
```

Result：`32 passed in 0.09s`。

Static／shell：

```bash
bash tests/test_fog_research_retry_circuit.sh
bash tests/test_fog_runtime_time_wiring.sh
bash -n scripts/run_fog_research_worker.sh
bash -n scripts/run_daily_research_quota.sh
plutil -lint scripts/com.new-top10.fog-research-worker.plist
```

Result：all exit `0`；plist `OK`。

## Acceptance mapping

- verifier 自有 clock、repo policy、canonical source artifacts重算：PASS
- `generated_at_utc.date() == run_date` trust path：不存在
- `-5`／`-5.001`／`900`／`900.001`：deterministic
- UTC／Taipei／Los Angeles host identity：一致
- market-midnight rollover：fail closed
- worker sample immutable context一次，daily child只驗證／傳遞：PASS
- worker／daily shell `date +%F` authority fallback：不存在
- legacy date env mismatch：fail closed
- plist date／timezone／freshness injection：不存在
- `fog_worker` queue owner wiring：維持唯一
- live LaunchAgent／queue／circuit／scheduler：not touched

status: PASS
next_step: full verification and candidate evidence
limits: 尚未完成 full pytest、allowlist、protected after hash與 commit

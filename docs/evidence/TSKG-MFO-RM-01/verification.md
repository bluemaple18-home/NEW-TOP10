# TSKG-MFO-RM-01 Verification

## Status

```text
status: GO
scope: source-neutral local read-model projection
external_calls: 0
runtime_wiring_changes: 0
ranking_or_model_changes: 0
```

## Evidence

- Public implementation：`app/tskg/flow_read_model.py`
- Contract tests：`tests/test_tskg_flow_read_model.py`
- Input contract regression：`tests/test_tskg_mfo01.py`
- Full TSKG test discovery：`62/62 PASS`
- Python compile gate：PASS
- `git diff --check`：PASS

## Acceptance mapping

| Acceptance | Evidence | Result |
|---|---|---|
| deterministic output/hash | reversed logical input produces identical output and SHA-256 | PASS |
| preserve observation/provenance/freshness | exact item contract tests | PASS |
| partial without zero fill | missing DEALER emits warning and no synthetic row | PASS |
| stale propagation | stale child sets item `STALE/is_stale=true` | PASS |
| defensive lookup | mutation does not alter subsequent lookup | PASS |
| no strategy fields | recursive prohibited-field scan | PASS |

## Limits

本 read model 只消費既有 integer-TWD `SecurityFlowObservation`。T86 官方資料是 `SHARE`，不可直接灌入；Theme aggregation、圖譜擴散與 ranking feature 不在本卡。

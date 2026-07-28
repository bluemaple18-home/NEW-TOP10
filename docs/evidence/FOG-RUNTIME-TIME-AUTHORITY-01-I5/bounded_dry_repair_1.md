---
id: FOG-RUNTIME-TIME-AUTHORITY-01-I5-BOUNDED-DRY-REPAIR-1
status: VERIFIED_REPAIR
type: evidence
---

# Bounded dry Repair 1

## Failure receipt

首次 bounded dry command：

```bash
TOP10_WEEKEND_CLEANUP_ENABLED=0 \
  .venv/bin/python scripts/run_controlled_grid_drain_host_runner.py \
  --date 2026-07-28
```

Result：exit `1`、`status=FAILED`。失敗停在
`build_research_progress_before_inventory`，尚未建立 inventory、尚未 circuit
recovery，也未載入 LaunchAgent。

Primary artifacts：

- `artifacts/host_runner/2026-07-28/controlled_grid_drain_host_runner_status_2026-07-28.json`
- `artifacts/host_runner/2026-07-28/controlled_grid_drain_host_runner_summary_2026-07-28.json`
- `artifacts/weekend_training/controlled_grid_drain_gates_2026-07-28.json`

Exact exception：

```text
AttributeError: 'types.SimpleNamespace' object has no attribute 'date'
```

Path：

`build_research_campaign_progress.build_payload` →
`run_autonomous_research.generate_topics` →
`generate_all_topics`。

## Root cause

Exact-regime eligibility正確要求 caller提供 explicit `args.date`，但兩個非 CLI
callers仍用舊的無 date `SimpleNamespace`：

- `scripts/build_research_campaign_progress.py`
- `scripts/research_map_linkage_smoke.py`

不在 `generate_topics`加入 current-date fallback，避免重新引入隱式 host-time
authority。

## RED

```bash
.venv/bin/python -m pytest -q tests/test_research_topic_date_wiring.py
```

Result：`2 failed`。

- Campaign progress：missing `args.date`。
- Linkage smoke：public helper尚未接收 explicit date。

## GREEN

最小修復：

- Campaign progress把既有 CLI `args.date`傳入 topic-generation namespace。
- Linkage smoke改為`load_topics(date, ...)`，由`smoke_rows(date, ...)`顯式傳遞。

Verification：

```text
tests/test_research_topic_date_wiring.py: 2 passed
I5 affected suite: 98 passed
full suite: 589 passed, 4 warnings, 246 subtests passed
py_compile: PASS
git diff --check: PASS
debug marker audit: clean
```

原失敗 CLI：

```bash
.venv/bin/python scripts/build_research_campaign_progress.py --date 2026-07-28
```

Result：exit `0`、`status=OK`。

## Runtime boundary

- Circuit仍為原`attempts=3`／`circuit_open=1`。
- LaunchAgent仍 unloaded。
- 沒有 research、replay、external write、model/ranking/weights/baseline/
  promotion mutation。
- 下一個合法動作是以新 code lineage重新執行一次 bounded dry；若同一 caller
  blocker重現，立即`NO_GO`，不再重試。

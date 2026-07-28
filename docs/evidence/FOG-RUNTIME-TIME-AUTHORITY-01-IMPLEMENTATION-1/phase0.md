---
card_id: FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1
evidence_kind: phase0_baseline_and_red
status: RED_CAPTURED
---

# Phase 0 baseline 與 RED

## Isolated worktree／capability preflight

- worktree：registered isolated detached worktree
- starting HEAD：`87e4da7dd63bafe82b16c28990e7be6db137b4e6`
- starting parent／mainline accepted tree：
  `408f3e0cced14bca451503cc35f845b403f72822`
- starting worktree：clean
- unrelated dirty paths：`[]`
- rejected `acd835df3a4fe40a149333dca0b55e62cc8eded9`：
  non-ancestor；未 merge、cherry-pick、copy patch或採用 stored PASS
- git metadata：PASS
- `plutil`：`/usr/bin/plutil`
- `.venv/bin/python`：missing at preflight
- `uv`：available
- CodeGraph：degraded；worktree 未初始化 index，為遵守 exact allowlist 不建立
  `.codegraph`，改用唯讀 `rg`
- network／live runtime：不需要、未操作

## Existing／missing allowlist inventory

Existing：

- `scripts/verify_daily_research_quota.py`
- `scripts/run_fog_research_worker.sh`
- `scripts/run_daily_research_quota.sh`
- `scripts/com.new-top10.fog-research-worker.plist`
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_fog_research_retry_circuit.sh`

Missing：

- `config/fog_runtime_time_authority_v1.json`
- `scripts/fog_authority_contracts.py`
- `scripts/fog_runtime_time_authority.py`
- `scripts/verify_processed_id_authority.py`
- `scripts/verify_closed_regime_runtime.py`
- `scripts/verify_fog_closed_regime_recovery.py`
- `tests/test_fog_runtime_time_authority.py`
- `tests/test_fog_closed_regime_runtime.py`
- `tests/test_fog_runtime_time_wiring.sh`

Baseline wiring finding：

- worker 與 daily shell 仍以 `date +%F` 作 contract identity fallback。
- LaunchAgent plist 未注入 timezone/date/freshness policy。
- `fog_worker` 是既有 queue owner。

## Protected hash contract

Protected inventory command：

```bash
git ls-files |
  rg '(^models/|ranking|weight|baseline|promotion)' |
  xargs shasum -a 256 |
  sort |
  shasum -a 256
```

- before aggregate SHA-256：
  `2aa2345f567d982634a1cf7a770cea96a77f0d8e3d5d9bd16b211e7abe75d126`
- after aggregate SHA-256：`PENDING`
- protected surface：tracked model、ranking、weight、baseline與 promotion paths
- expected：before／after byte-identical

## Required public-behavior RED ledger

| Regression ID | Test | RED reason |
|---|---|---|
| `FRTA-REG-RRV-P1-01-PROCESSED-ID` | forged inventory ID 與兩份獨立 source lineage | authority module 尚不存在 |
| `FRTA-REG-RRV-P1-03-SOURCE-BASELINE` | attacker self-reported 五角色 path/hash | trusted role-path module 尚不存在 |
| `FRTA-REG-RECEIPT-V3-EXACT` | missing／unknown／type／forged source lineage | receipt v3 verifier 尚不存在 |
| `FRTA-REG-TIME-DATE-LINEAGE` | 台北跨 UTC 日界與合法休市日 source lineage | time authority module 尚不存在 |

RED command：

```bash
python3 -m unittest -v tests.test_fog_closed_regime_runtime
```

- exit：`1`
- result：`Ran 4 tests`；`FAILED (errors=4)`
- `FRTA-REG-RRV-P1-01-PROCESSED-ID`：
  `ModuleNotFoundError: scripts.verify_processed_id_authority`
- `FRTA-REG-RRV-P1-03-SOURCE-BASELINE`：
  `ModuleNotFoundError: scripts.fog_authority_contracts`
- `FRTA-REG-RECEIPT-V3-EXACT`：
  `ModuleNotFoundError: scripts.verify_closed_regime_runtime`
- `FRTA-REG-TIME-DATE-LINEAGE`：
  `ModuleNotFoundError: scripts.fog_runtime_time_authority`

上述 missing modules 是四個獨立 public-behavior tests 的實作前 RED；不得被解讀
為 GREEN。

---
card_id: FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-REPAIR-1
evidence_kind: repair_phase0_red
status: RED_CAPTURED
---

# Repair-1 Phase 0

## Lineage與capability

- isolated worktree：registered、detached、starting clean
- starting Review HEAD：
  `8b4b6e33cad066a884b486c284cd5f707d09cf83`
- blocking Review：`15a87e56c21d7031ddb5891666aab331d3003c39`
- Reviewer-owned probe correction：`8b4b6e3`
- Dispatcher amendment：`32798bd4df355315a39fe9ee4a693cfd1c90f9af`
- base Implementation candidate：
  `f7d51a3d994707c819198fd1edcdcf0db4dd0775`
- Python：CPython 3.12.12；pytest 9.1.1
- bash：`/bin/bash`；plutil：`/usr/bin/plutil`
- worktree `.venv`：missing；測試只借用 trusted main-repo `.venv`
- CodeGraph：worktree未初始化；為遵守 exact allowlist未建立 index，改用唯讀
  `rg`
- network／live runtime：不需要、未操作

## Corrected hostile probe RED

Command：

```text
<trusted-main-repo>/.venv/bin/python \
  docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/hostile_probe.py
```

Exit：`1`

唯一三個 failure：

```text
processed_authority.self_reported_distinct_sources_rejected
baseline_authority.self_reported_baseline_rejected
receipt_and_time.missing_daily_source_rejected
```

Canonical baseline control、hash drift、path escape、receipt/time與static wiring
其餘 checks均為 PASS。

## Public-behavior RED

新增 regression後、production修改前：

```text
pytest -q tests/test_fog_closed_regime_runtime.py \
  -k 'caller_selected or source_baseline or missing_daily_source'
```

Exit：`1`，`4 failed`：

- caller-selected distinct sources仍被接受；
- caller-selected baseline只因稍後的 protected hash drift拒絕，尚未由 repo
  authority拒絕；
- producer缺 daily lineage沒有丟出
  `DAILY_ARTIFACT_SCHEMA_REJECT`；
- verifier只看到 source hash drift，沒有辨識 missing daily lineage。

`tests/test_fog_research_retry_circuit.sh`在第一個 invocation後因自身 context
殘留而 exit `1`；foreign context仍存在。上述 RED均走既有 public modules／shell，
不是 missing module。

## Protected與read-only hashes

- protected model／ranking／weight／baseline／promotion aggregate before：
  `2aa2345f567d982634a1cf7a770cea96a77f0d8e3d5d9bd16b211e7abe75d126`
- time policy JSON：
  `d7bb19851d1e33e5245803bee4a7ef7d8534d97f58fc95c62e386aad5d60a058`
- time authority Python：
  `a2598480f268ec8bf5c8534dd1daae3cd867a6f90fab29a2e6daf15601efe59d`
- corrected hostile probe：
  `d2253a5e62c9d46f0079312a939d2e8c3cf1338c80ef107587d523eca5a6a33c`
- corrected review.md：
  `aa5415790cc78b5eb03f24fd7e4ffafa2fef752802c4ec39cd12b352dbc18229`
- accepted architecture：
  `b68c254f763a67b0c21ad90cb1c971fa7a7f7e1f188e5e26ee3ed30f0917f03b`
- receipt schema：
  `7c7d9836d418c84c6de046a5c8a063dc4af092aa5ff5fd10000257e3a8928ecc`

Starting changed-file baseline：empty。

---
card_id: FOG-RUNTIME-TIME-AUTHORITY-01-REPAIR-1
evidence_kind: phase0_contract_red
reviewed_candidate_sha: 26d8471d15572f216095122f2462df79bc96edc1
review_evidence_sha: 3102e1385760227e53ef0d2eb37b918e17418d90
starting_head: 5ffc0a33874fe742ba7ffa2170ad6236612817e4
---

# Phase 0 RED contract evidence

本證據在修改 architecture 前保存，只比較 fixed candidate、正式 Review evidence
與 Repair contract；未執行或修改 production runtime。

## Capability preflight

```text
worktree: isolated / detached
starting_head: 5ffc0a33874fe742ba7ffa2170ad6236612817e4
starting_head_parent: 3102e1385760227e53ef0d2eb37b918e17418d90
starting_head_delta: Repair card only
reviewed_candidate: 26d8471d15572f216095122f2462df79bc96edc1
review_evidence: 3102e1385760227e53ef0d2eb37b918e17418d90
starting_worktree_clean: PASS
unrelated_dirty_paths: []
git_metadata: PASS
python: existing repo .venv
zoneinfo: available
sha256: available
network_needed: NO
live_runtime_needed: NO
production_acceptance: NOT_RUN
```

## FRTA-P1-01 RED：合法休市日 source lineage 被拒

Candidate §4 與 invariant 11 要求 daily artifact
`source_date == market_run_date`。以下合法休市日 lineage 因此無法通過 candidate
contract：

```text
market_run_date=2026-08-08
artifact_run_date=2026-08-08
daily_source_date=2026-08-07
source_trade_date=2026-08-07
candidate_result=REJECT
required_result=ACCEPT when all lineage/hash/freshness gates pass
```

RED 原因：civil run identity、artifact identity 與 artifact data source date
共用同一 equality invariant，無法表達「週六執行、artifact 綁週六 run、資料取最近
可信週五來源」。

## FRTA-P1-02 RED：successor allowlist 缺少前鏈安全能力

Candidate I1–I5 changed-file allowlist 沒有完整納入：

```text
scripts/fog_authority_contracts.py
scripts/verify_fog_closed_regime_recovery.py
scripts/verify_processed_id_authority.py
scripts/verify_closed_regime_runtime.py
tests/test_fog_closed_regime_runtime.py
```

也未固定 `RRV-P1-01` processed-ID authority、`RRV-P1-03`
source-lineage／baseline authority與 time authority 的 successor regression IDs。
`acd835df…` 不是 reviewed candidate ancestor，且是 rejected candidate；現有文件
未提供合法 successor base、clean-room reimplementation policy或
keep／reimplement／reject matrix。

RED 結果：若逐字遵守 I1–I5 上限，successor 無法重建前鏈已 Review 關閉的安全
能力；若直接採用 `acd835df…`，則繞過 rejected-code boundary。

## FRTA-P1-03 RED：receipt v3 exact schema 未閉合

Candidate §7.4 只有 `minimum fields` 範例，另以自然語言要求 queue owner、
runner identity、research contract、exact regime、state transition、
topic-run lineage與 production impact，卻未提供：

- 完整 top-level／nested key manifest；
- 每一欄 type、required／optional、nullability；
- 所有 object layer 的 unknown-field policy；
- canonical complete v3 fixture；
- v2→v3 可重算／需查 authority／無法補造的逐欄 mapping。

RED 結果：producer 與 verifier 沒有單一 machine-readable authority，可各自選出
不同完整 schema；同時要求 exact-schema reject unknown／missing fields時，合法
receipt 也沒有唯一可判定結果。

## Phase 0 status

```text
FRTA-P1-01: RED_CAPTURED
FRTA-P1-02: RED_CAPTURED
FRTA-P1-03: RED_CAPTURED
architecture_modified_before_capture: NO
runtime_or_production_probe: NOT_RUN
```

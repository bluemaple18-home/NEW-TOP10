# BC-CP2 R4 Full-720 Capacity-only Benchmark Receipt

## Scope receipt

- 工作名稱：`BC-CP2 R4 Full-720 Capacity-only Benchmark`
- Slice ID：`BC-CP2-R4-FULL-720-CAPACITY-ONLY-BENCHMARK`
- Verdict：`CAPACITY_ONLY_MEASUREMENT_RECORDED / NOT_RESEARCH_EVIDENCE / NOT_ADMISSION`
- Candidate SHA：`044780189581323ffe11cc84caec4a12b65e6974`
- Canonical main：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- R2 fixed SHA：`931f4b5c2b539940f0b1b8e5957dddd7df1a1505`
- R3 accepted SHA：`044780189581323ffe11cc84caec4a12b65e6974`
- Dispatch card SHA-256：`sha256:54d3230a7c5a2ca5655637f1285af29e0b5d65b432bcfd687a2a4e8b5a09b435`
- Observed at：`2026-09-01T10:08:14.766754+00:00`
- Boundary：本 receipt 只記錄一次 synthetic `CAPACITY_ONLY / NOT_RESEARCH_EVIDENCE` full-family 720 量測。不得外推為研究有效性、production readiness、B0 Phase 2、B1 或 C1 准入。未 merge、未 push、未改 Issue、未 deploy、未 production invocation、未 external write。

## Command and runtime boundary

| Item | Evidence |
|---|---|
| Command shape | `<temp-python> scripts/run_capacity_only_strategy_matrix_harness.py --work-root <temp-work-root>/harness-work --output <temp-work-root>/harness-work/full-720-receipt.json --full-family` |
| Work root policy | `<temp-work-root>` was outside `<repo-root>` and not a broad root; harness work root was empty before execution. |
| Repo pre-run gate | `git rev-parse HEAD` returned `044780189581323ffe11cc84caec4a12b65e6974`; `git status --short` was empty after removing the dispatch-only untracked card copy. |
| Terminal stdout | `{"status": "OK", "output": "<temp-work-root>/harness-work/full-720-receipt.json", "scenario_count": 720, "parity": "PASS"}` |
| Terminal stderr | Arrow emitted sandbox CPU-cache `sysctlbyname` warnings; process still exited `0` and receipt gates passed. |
| Repo runtime artifact check | Harness runtime outputs stayed under `<temp-work-root>/harness-work`; repo change allowlist is only this Markdown receipt. |

## Full-720 receipt summary

| Gate | Observed result | Status |
|---|---:|---|
| Harness schema | `capacity-only-strategy-matrix-harness.v1` | `PASS` |
| Requested scenario count | `720` | `PASS` |
| Executed scenario count | `720` | `PASS` |
| Parity ID count | `720` | `PASS` |
| Requested/executed ID set parity | `requested_executed_match=true` | `PASS` |
| Requested IDs hash | `sha256:79899da01ead21b31ebd48571e2e3b6460f65946dad86bab7e5a1d546a0b4baa` | `PASS` |
| Executed IDs hash | `sha256:79899da01ead21b31ebd48571e2e3b6460f65946dad86bab7e5a1d546a0b4baa` | `PASS` |
| Canonical family count | `720` | `PASS` |
| Canonical family hash | `sha256:78cd9b8b6fa39935f9037d5b4c8dde3fcc2ae39955414aa51bda96dafb69f6b4` | `PASS` |
| Global family size | `720` | `PASS` |
| Global combination IDs hash | `sha256:78cd9b8b6fa39935f9037d5b4c8dde3fcc2ae39955414aa51bda96dafb69f6b4` | `PASS` |
| Formal contract hash | `sha256:5459cf232f1db8c31d45a2270a05407ed5bb8e5084632064047c8651240e379d` | `RECORDED` |
| Parameter catalog hash | `sha256:49be0593c9f2be2025761e1e14a086dde2a8a8ac55bd0006e4c9b42aed1f0f4c` | `RECORDED` |

Hash interpretation：`sha256:78cd9b8b6fa39935f9037d5b4c8dde3fcc2ae39955414aa51bda96dafb69f6b4` is the canonical-order formal family hash. `sha256:79899da01ead21b31ebd48571e2e3b6460f65946dad86bab7e5a1d546a0b4baa` is the sorted requested/executed set-parity hash used by the harness because the strategy-matrix output is score-sorted.

## Resource metrics

| Metric | Value |
|---|---:|
| Wall time seconds | `8.11430141699384` |
| Candidate/sec | `88.73222265222967` |
| CPU user seconds | `2.7145560000000004` |
| CPU system seconds | `0.12945500000000004` |
| Peak RSS | `234520576` |
| Read I/O delta (`ru_inblock`) | `0` |
| Write I/O delta (`ru_oublock`) | `0` |

## I/O, fixture, and cleanup

| Item | Value | Status |
|---|---:|---|
| Fixture purpose | `CAPACITY_ONLY` | `PASS` |
| Fixture research status | `NOT_RESEARCH_EVIDENCE` | `PASS` |
| Fixture ranking file count | `1` | `PASS` |
| Fixture stock count | `10` | `PASS` |
| Fixture trade day count | `23` | `PASS` |
| Fixture max horizon | `20` | `PASS` |
| Pre-fixture manifest hash | `sha256:e3338180e267fa5da7596378f3e5339b1949efa6fb9c9e6df4cd1fbcc247c796` | `RECORDED` |
| Post-fixture manifest hash | `sha256:e3338180e267fa5da7596378f3e5339b1949efa6fb9c9e6df4cd1fbcc247c796` | `RECORDED` |
| Fixture manifest parity | `PASS` | `PASS` |
| Fixture file count | `3` | `RECORDED` |
| Temporary fixture cleanup | `temp_fixture_removed=true` | `PASS` |
| Cleanup status | `PASS` | `PASS` |

## Output sizes and hashes

| Output | Size | SHA-256 |
|---|---:|---|
| Harness JSON receipt | `3228` bytes | `sha256:034769fe32b3260b1392457f2ae849f5d7944a409a7d3dee36b6a5491b120179` |
| Strategy matrix JSON | `1851118` bytes | `sha256:d9e9d171e473a05a3b7a4b840ce9b4bbd1c3fe315f5d7b278198ba3f872d3b5d` |
| Strategy matrix Markdown | `1653` bytes | `sha256:d3897332cad0d483ebd10c2375f3e78e7a9acd1473ccae952a7f47ed698f5526` |

## Protected hashes

R3 protected source/config hashes were checked before and after the full-720 run and remained byte-identical.

| Path | Expected from R3 receipt | Observed after R4 run | Status |
|---|---|---|---|
| `scripts/run_capacity_only_strategy_matrix_harness.py` | `sha256:b99f7c58a130aa7a705f25b28e99c4f5b3100fdefbb23dbbb5d5a4040aec2400` | `sha256:b99f7c58a130aa7a705f25b28e99c4f5b3100fdefbb23dbbb5d5a4040aec2400` | `PASS` |
| `tests/test_capacity_only_strategy_matrix_harness.py` | `sha256:1932b1058a30f452f72e2751947788d6cbbb002c977272aeaba8dcceb4e48597` | `sha256:1932b1058a30f452f72e2751947788d6cbbb002c977272aeaba8dcceb4e48597` | `PASS` |
| `scripts/run_backtest_strategy_matrix.py` | `sha256:39b42aac6d7c232c9bbb4f1d8981b55ca43826758d91cd3a45281ff19f590b43` | `sha256:39b42aac6d7c232c9bbb4f1d8981b55ca43826758d91cd3a45281ff19f590b43` | `PASS` |
| `scripts/run_autonomous_research.py` | `sha256:2c5b9b11c22b13aeae78045a721c362f1ad65390ea69eac075e69f0807df951c` | `sha256:2c5b9b11c22b13aeae78045a721c362f1ad65390ea69eac075e69f0807df951c` | `PASS` |
| `config/research_parameter_catalog.json` | `sha256:e88079414dfae381b96bd4a46326e38b8288447710008ecfe9c1d73b6ec66500` | `sha256:e88079414dfae381b96bd4a46326e38b8288447710008ecfe9c1d73b6ec66500` | `PASS` |
| `config/regime_research_contract.json` | `sha256:e3ada41e5a9de4f471750f298718ba815582db550abd9b537a73b66bd818bc34` | `sha256:e3ada41e5a9de4f471750f298718ba815582db550abd9b537a73b66bd818bc34` | `PASS` |
| `<canonical-main-checkout>/artifacts/market_regime_history_2026-05-29.json` | `sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70` | `sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70`; `216519` bytes | `PASS_READ_ONLY_PARITY_NOT_BENCHMARK_INPUT` |

## Verification

| Check | Result | Status |
|---|---|---|
| Dispatch card hash gate | `sha256:54d3230a7c5a2ca5655637f1285af29e0b5d65b432bcfd687a2a4e8b5a09b435` matched before removal. | `PASS` |
| Pre-run clean gate | HEAD `044780189581323ffe11cc84caec4a12b65e6974`; `git status --short` empty. | `PASS` |
| Full-family benchmark | Single invocation exited `0`; stdout reported `scenario_count=720`, `parity=PASS`. | `PASS` |
| Identity/hash gates | Canonical full-family count/hash and requested/executed parity matched. | `PASS` |
| Cleanup gate | Harness removed temporary fixture and reported cleanup `PASS`. | `PASS` |
| Protected source/config/configured-data drift | No drift against R3 receipt for tracked protected paths listed above; configured-data parity was checked read-only from canonical main checkout and was not used as benchmark input. | `PASS` |
| Repo write allowlist | `git status --short` showed only `docs/evidence/BC-CP2-R4-FULL-720-CAPACITY-ONLY-BENCHMARK/`; this directory contains only `01-full-720-capacity-only-benchmark-receipt.md`. | `PASS` |
| Diff hygiene | `git diff --check` exited `0` after this receipt was written. | `PASS` |

## Remaining unknowns

- This is a synthetic capacity-only fixture, not a production/configured rankings workload and not research-valid evidence.
- The benchmark does not validate ranking quality, model behavior, configured data freshness, queue behavior, scheduler behavior, retry/idempotency, or production canary readiness.
- Arrow CPU-cache `sysctlbyname` warnings appeared under the sandboxed runtime; they did not prevent completion, but hardware cache detection should not be inferred from this run.
- `<canonical-main-checkout>/artifacts/market_regime_history_2026-05-29.json` parity was checked read-only against R3 (`sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70`, `216519` bytes), but it was not a benchmark input for this synthetic capacity-only run.

## R5 / BC-CP2 checkpoint suggestion

Next checkpoint should be Mainline-owned verification only: independently read this receipt, verify the single changed-file allowlist, re-check `git diff --check`, confirm protected hashes and final candidate SHA, and decide GO/NO-GO for the R4 evidence artifact. Do not use this R4 result to admit B0 Phase 2, B1, C0 Phase 2, C1, production canary, or external writes.

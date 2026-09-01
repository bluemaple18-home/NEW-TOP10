# BC-CP2 完整 720 E3 容量量測 Receipt

## Scope receipt

- 工作名稱：`BC-CP2 完整 720 E3 容量量測`
- Slice ID：`BC-CP2-E3-720-01`
- Verdict：`FAIL_CLOSED_CONFIGURED_SNAPSHOT_AS_OF_INVALID`
- Candidate 起點：BC-CP2 prior `0b6b27854e9a64616db6ded9dee99f03e9e86c67`
- Repair 起點：`14396c6df640531aec7e1b4aa0d80eecd07d2c7f`
- Canonical main：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- B0 authority：`1e9ed61e2e5c86adf2159e095ff241ef13127e80`
- C0 Phase 2：`a61f143ea5223b6af812e27aac0082121f781343`
- Dispatch card file hash：`sha256:f454a2fa43a5be72054c524a5bf72aacfb4a79c150b54f3f11bbd5a73513b366`
- Observed at：`2026-09-01T08:10:43Z`
- Boundary：本次只做 configured snapshot trace/input preflight 與 runner fail-closed reproduction。未執行 720 E3 benchmark、未產生 strategy matrix output、未修改 code/config/workflow/queue/runner/scheduler/backtest/production、未修改既有 evidence 或原始資料、未 merge/push/改 Issue/external write，未准入 B0 Phase 2、B1 或 C1。

## Direct answer

本次仍不能執行完整 720 E3 容量 benchmark，但此 receipt 只聲稱 canonical configured snapshot 的結果，不再聲稱全 repo 沒有任何 legal workload。

Configured snapshot 由 `config/research_shadow_runs.yaml` 固定：`data/clean/features.parquet`、`artifacts/market_regime_history_2026-05-29.json`、`artifacts/backtest/historical_rankings_current_model`、`data/reference/stock_industry_map.csv`，加上必要 runner / catalog / contract source。preflight manifest 共 `36` 筆，包含 ranking root 內 `25` 個 strict `ranking_YYYY-MM-DD.csv` 檔，pre/post parity 為 `PASS`。

阻擋點發生在最早 authority gate：完整 runner command 以 configured `artifacts/market_regime_history_2026-05-29.json` 進入 `validate_development_scope(...) → statistical_lineage_authority(...)` 時，因 market-regime history rows 缺 `as_of_date` 而回傳 exit code `1`，錯誤為 `market regime history 不符合 as-of 契約` / `MISSING_AS_OF_DATE`。因此依 dispatch 卡 fail closed；不得改用其他 history、其他 ranking root、validation profiles 或便利樣本。

## Configured snapshot source

`config/research_shadow_runs.yaml` 指定的容量 preflight snapshot：

| Field | Configured value |
|---|---|
| `features` | `data/clean/features.parquet` |
| `market_regime_history` | `artifacts/market_regime_history_2026-05-29.json` |
| `dates_from_dir` | `artifacts/backtest/historical_rankings_current_model` |
| `industry_map` | `data/reference/stock_industry_map.csv` |
| `top_n` | `10` |
| `window_id` | `2026-04-08_2026-05-13` |

## Reproducible runner command

Token mapping / cwd contract:

- `<repo-root>`：isolated clean worktree root for this candidate.
- `<local-data-root>`：Owner-authorized local snapshot root that contains configured data paths from `config/research_shadow_runs.yaml`.
- `<temp-output>`：isolated temporary JSON output probe path outside source/data roots; it must not exist after this fail-closed command.
- CWD：`<repo-root>`.

The following tokenized command preserves the complete executable parameter set used for the fail-closed reproduction:

```bash
<local-data-root>/.venv/bin/python scripts/run_backtest_strategy_matrix.py \
  --rankings-dir <local-data-root>/artifacts/backtest/historical_rankings_current_model \
  --features <local-data-root>/data/clean/features.parquet \
  --require-exact-regime \
  --market-regime-history <local-data-root>/artifacts/market_regime_history_2026-05-29.json \
  --base-regime BROAD_RISK_ON \
  --allowed-episode-ids FAIL_CLOSED_PREFLIGHT_PROBE \
  --development-only \
  --horizons 3,5,10,20 \
  --stop-loss-pcts none,0.05,0.06,0.08,0.10,0.12 \
  --take-profit-pcts none,0.10,0.15,0.20,0.25,0.30 \
  --max-group-exposures none,0.25,0.35,0.45,0.55 \
  --output <temp-output>
```

Observed command result:

```text
exit_code: 1
output_probe_exists: false
failing_frame: scripts/run_backtest_strategy_matrix.py build_payload → validate_development_scope; scripts/run_autonomous_research.py statistical_lineage_authority
error: ValueError: market regime history 不符合 as-of 契約：[{'index': 0, 'reason_code': 'MISSING_AS_OF_DATE'}, {'index': 1, 'reason_code': 'MISSING_AS_OF_DATE'}, {'index': 2, 'reason_code': 'MISSING_AS_OF_DATE'}]
```

This is the first configured-snapshot fail-closed gate. No benchmark output was created.

## Preflight receipt

| Gate | Result | Evidence |
|---|---|---|
| Dispatch authority | `AUTHORIZED_FOR_CAPACITY_ONLY` | Dispatch card hash `sha256:f454a2fa43a5be72054c524a5bf72aacfb4a79c150b54f3f11bbd5a73513b366`，lines 5-13。 |
| Configured snapshot routing | `PASS` | `config/research_shadow_runs.yaml` routes to one features file, one market-regime history, one ranking root, and one industry map. |
| Runner syntax | `PASS` | `<local-data-root>/.venv/bin/python -m py_compile scripts/run_backtest_strategy_matrix.py` return code `0`。 |
| Canonical formal 720 | `PASS` | Earlier preflight from this candidate regenerated `scenario_count=720` and `unique_combination_ids=720`; this configured repair did not rerun benchmark after the as-of gate failed. |
| Configured snapshot manifest | `PASS` | `36` records; manifest digest `sha256:fad1ea8f2e2172d9b149022d7baf034335816a322865e99466666a78e5b55dd2`；preflight summary hash `sha256:adabe16698646633375856c6b58be76ee56c0dccf7ea02dbc2c67a0f2870551d`。 |
| Pre/post manifest parity | `PASS` | Manifest before and after runner command was identical. |
| Ranking root list | `PASS` | `25` strict files from `ranking_2026-04-08.csv` through `ranking_2026-05-13.csv`；all listed below. |
| Exact development workload | `FAIL_CLOSED` | Configured history fails as-of validation before legal development episodes or horizon-safe dates can be accepted. |

## Immutable configured snapshot manifest

Manifest digest over all `36` records：`sha256:fad1ea8f2e2172d9b149022d7baf034335816a322865e99466666a78e5b55dd2`

| Root | Relpath | Size bytes | SHA-256 |
|---|---:|---:|---|
| `<worktree>` | `config/research_shadow_runs.yaml` | `2584` | `sha256:6b1ab4d074c4d9ddd8ab8e62dd26ab79c078bb05f7323aeb75d616cc07b7116d` |
| `<worktree>` | `scripts/run_backtest_strategy_matrix.py` | `35846` | `sha256:39b42aac6d7c232c9bbb4f1d8981b55ca43826758d91cd3a45281ff19f590b43` |
| `<worktree>` | `scripts/run_backtest_replay.py` | `23040` | `sha256:2df70b6efe3920cb5c709cafc9ae0cb2597d60753a28ab7fc068eee739285c77` |
| `<worktree>` | `scripts/run_portfolio_replay.py` | `34972` | `sha256:5909f56e749aad562c470fd9f965fff5db34f8444d136bb894dec0ed1adbc85f` |
| `<worktree>` | `scripts/run_autonomous_research.py` | `178280` | `sha256:2c5b9b11c22b13aeae78045a721c362f1ad65390ea69eac075e69f0807df951c` |
| `<worktree>` | `app/research/parameter_catalog.py` | `7453` | `sha256:da7c69d738a528def4aea9747610084c46b78bc62bb9a7fe187c5f24a943c23f` |
| `<worktree>` | `config/research_parameter_catalog.json` | `7243` | `sha256:e88079414dfae381b96bd4a46326e38b8288447710008ecfe9c1d73b6ec66500` |
| `<worktree>` | `config/regime_research_contract.json` | `5562` | `sha256:e3ada41e5a9de4f471750f298718ba815582db550abd9b537a73b66bd818bc34` |
| `<local-data-root>` | `data/clean/features.parquet` | `137774296` | `sha256:93e8432987b6037db243b2864f7bc8d09f12acd50249d9238d2acddacd2561d2` |
| `<local-data-root>` | `data/reference/stock_industry_map.csv` | `207126` | `sha256:86ca58072c0db0581df741e212b0bccc641848638b52b4ae1e3b1a0b4e96cb20` |
| `<local-data-root>` | `artifacts/market_regime_history_2026-05-29.json` | `170288` | `sha256:10bde4543a13558aa01df7764ff168c461ff78daf2e38989ed3fa467c99c5485` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-08.csv` | `4968` | `sha256:adb7f49ae0d220b15b2fe962296cfdfe7afa84a53812cbfd3c454fd406987e3d` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-09.csv` | `4989` | `sha256:f5faeede9025de98d6971cc0218658bd2ccd5da4396328a6d6848d0729b5400f` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-10.csv` | `4927` | `sha256:e606fbfcfb8694663ab39c6028d9c941c6acba42617eb6f9d646f9a1a56d1eed` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-13.csv` | `4893` | `sha256:7af3dfa3d3838f7d93542ecf0d957e1baf1da546a0f17c972f2abc21d50f9faf` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-14.csv` | `5073` | `sha256:f0d68776b2efcac69b34e4951d703554f7867bae4d596b83af738ee0758608c7` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-15.csv` | `5072` | `sha256:d72d3653455679a6ce929ed2da7306ec099ca1f99d55f4b9066e65d1181dae42` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-16.csv` | `5117` | `sha256:e55b22abe94dccff96649fdcc234430a6de00fd2d1b736a4df195fd31889922a` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-17.csv` | `5048` | `sha256:f479ecec27f21737195ccece215b88ae064583054d8fcd3430788bce5facf348` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-20.csv` | `5134` | `sha256:06ecaf4e08b9eb9a47cb14f37e11aaa675a36695daa426c8dbd3c62027f88d4d` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-21.csv` | `5049` | `sha256:3767eb4883f100f669aaeb57c92b83e87a53d6f407303a3c143eec2af01a9da6` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-22.csv` | `5102` | `sha256:d095518f95a55b78c996bf5f5a3899d15c74b59d20d44c632fd54f822dc6dbbb` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-23.csv` | `4917` | `sha256:f8e8e6d0055d42d60ac1620c293753cd6d9d982c8816ac7ff16c14b9ece11285` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-24.csv` | `4869` | `sha256:86b8897126c5bb0269ef5552f2e5bfa78a4d49f6927d9ae8584f8913bc2f960e` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-27.csv` | `4833` | `sha256:92619d878c32412de186625f01a1b211eedfdfaed2b737b7771a9693f283fdf6` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-28.csv` | `4806` | `sha256:a42b11f4ec09b4189b828dabc8762e2e4c4bdbbf69d642f7aed30ddce309f2fc` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-29.csv` | `4966` | `sha256:80678dec5704260875b7e37291579cb824116e6b1a225f35a22c4795d81f05b9` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-04-30.csv` | `4899` | `sha256:68327e169cdc5f75cf430b02f1acb50d06d9c350f1aca171922fb25d95ab990f` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-05-04.csv` | `4948` | `sha256:b576a9d8ea984c347c070389819dfca647fea5bb16e3bee8f14a438ea3f5a7fc` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-05-05.csv` | `4879` | `sha256:49d15da2cc993b05f26e599daa41a7967afb028732db5e10cec1abfd95c6f09d` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-05-06.csv` | `4907` | `sha256:c5750306ee534aaf15026a4148ccb2d603c62df265d0eb3c36158a6aec615f2d` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-05-07.csv` | `4870` | `sha256:c8bdb90949e9e411dbb59c2b57524547e777065a1d005a584d9caf3e401fad79` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-05-08.csv` | `4895` | `sha256:5b8c52a6fff1504482eb8762c6139bee251ca3066b9765441b1d98a706ae57b6` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-05-11.csv` | `4906` | `sha256:3a6efcfd4c3cbb549dfd975c3a482bb7a33062c69eaa28d508cd079d53dad9c4` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-05-12.csv` | `4855` | `sha256:964658bf888fc8fb764826c54e0a141f6543b8ff9a4178828a6753f393274ee4` |
| `<local-data-root>` | `artifacts/backtest/historical_rankings_current_model/ranking_2026-05-13.csv` | `4897` | `sha256:1d1bcf8ebb0a573d76cbee9442be963ba2acf29ff74e6366d82a0b1232fc8598` |

## Measurement receipt

- Measurement status：`NOT_EXECUTED_FAIL_CLOSED`
- Benchmark command status：`NOT_EXECUTED_AFTER_AUTHORITY_GATE`
- Gate command exit code：`1`
- Failing gate：`CONFIGURED_MARKET_REGIME_HISTORY_AS_OF_INVALID`
- Actual scenario count：`0`
- Authorized scenario count：`720 candidate-space only; 0 workload-authorized`
- Unique canonical IDs：`720 candidate-space only; 0 executed`
- Wall time：`UNMEASURED`
- Candidate/sec：`UNMEASURED`
- CPU user/sys：`UNMEASURED`
- Peak RSS：`UNMEASURED`
- Read/write I/O：`UNMEASURED`
- Output size：`NO_STRATEGY_MATRIX_OUTPUT`
- Output probe：`<temp-output>` did not exist after the fail-closed command.
- Non-extrapolation boundary：本 receipt 只證明 configured snapshot 在 as-of gate fail closed；不得外推全 repo workload availability、daily concurrency、larger matrix、research validity、ranking provenance、production readiness 或 B0/B1/C1 admission。

## Minimum next authority

1. Repair or replace the configured `artifacts/market_regime_history_2026-05-29.json` with an as-of valid history for this configured snapshot.
2. After as-of validity passes, derive the trusted development episode IDs from `regime_research_contract.json` and use those IDs directly, not `FAIL_CLOSED_PREFLIGHT_PROBE`.
3. Confirm the configured `artifacts/backtest/historical_rankings_current_model` files overlap every horizon-safe date required by horizons `3,5,10,20`.
4. Only after those configured snapshot gates pass, run the full 720 E3 benchmark and record wall time, candidate/sec, CPU, peak RSS, I/O, output size, manifest parity and cleanup.

## Claim Ledger

### Claim BC-CP2-E3-720-001

```yaml
claim_id: BC-CP2-E3-720-001
claim: The dispatch card authorizes current local snapshot inputs for capacity-only benchmarking, but requires fail-closed behavior if no legal exact development workload with horizon-safe ranking dates exists.
classification: DISPATCH_AUTHORITY_AND_STOP_RULE
source_repo: local dispatch input
source_sha_or_version: sha256:f454a2fa43a5be72054c524a5bf72aacfb4a79c150b54f3f11bbd5a73513b366
source_path_or_official_url: docs/tasks/2026-09-01_DISPATCH-NEW-TOP10-BC-CP2-FULL-720-E3-CAPACITY-BENCHMARK.md
source_range_or_section: lines 5-13
observed_at: 2026-09-01T08:10:43Z
confidence: HIGH
conflict_with: using validation profiles, non-configured histories, or arbitrary ranking files as convenience workload.
implication: This worker must not run benchmark unless exact development workload authority is established from the configured snapshot.
open_question: none for this dispatch stop rule.
owner: Owner / Mainline dispatcher
```

### Claim BC-CP2-E3-720-002

```yaml
claim_id: BC-CP2-E3-720-002
claim: The configured snapshot is exactly the snapshot routed by config/research_shadow_runs.yaml: features=data/clean/features.parquet, market_regime_history=artifacts/market_regime_history_2026-05-29.json, dates_from_dir=artifacts/backtest/historical_rankings_current_model, industry_map=data/reference/stock_industry_map.csv.
classification: CONFIGURED_SNAPSHOT_ROUTING
source_repo: bluemaple18-home/NEW-TOP10; local configured snapshot manifest
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070; sha256:fad1ea8f2e2172d9b149022d7baf034335816a322865e99466666a78e5b55dd2
source_path_or_official_url: config/research_shadow_runs.yaml; configured snapshot manifest in this receipt
source_range_or_section: research_shadow_runs.yaml lines 1-9; Configured snapshot source section; Immutable configured snapshot manifest section
observed_at: 2026-09-01T08:10:43Z
confidence: HIGH
conflict_with: claiming this receipt inspected all repo histories, all ranking roots, or non-configured workload candidates.
implication: The fail-closed verdict is scoped only to the configured snapshot.
open_question: none for configured snapshot routing.
owner: BC-CP2 capacity worker
```

### Claim BC-CP2-E3-720-003

```yaml
claim_id: BC-CP2-E3-720-003
claim: The configured snapshot manifest has 36 records, including all 25 strict ranking_YYYY-MM-DD.csv files in artifacts/backtest/historical_rankings_current_model, and pre/post manifest parity remained identical around the fail-closed runner command.
classification: CONFIGURED_MANIFEST_PARITY_GO
source_repo: local configured snapshot manifest
source_sha_or_version: sha256:fad1ea8f2e2172d9b149022d7baf034335816a322865e99466666a78e5b55dd2; preflight summary sha256:adabe16698646633375856c6b58be76ee56c0dccf7ea02dbc2c67a0f2870551d
source_path_or_official_url: configured snapshot manifest in this receipt; preflight command output summarized in this receipt
source_range_or_section: Preflight receipt table; Immutable configured snapshot manifest section
observed_at: 2026-09-01T08:10:43Z
confidence: HIGH
conflict_with: fixed local snapshot claims that omit files needed to support the configured snapshot verdict.
implication: Reproducibility is bounded to the listed configured files and manifest digest, not to unrelated local files.
open_question: whether a future repaired configured history should replace the manifest digest.
owner: BC-CP2 capacity worker
```

### Claim BC-CP2-E3-720-004

```yaml
claim_id: BC-CP2-E3-720-004
claim: The executable runner command failed before benchmark execution because the configured market_regime_history_2026-05-29.json does not satisfy the as-of contract, producing MISSING_AS_OF_DATE for the first rows and exit code 1.
classification: FAIL_CLOSED_CONFIGURED_HISTORY_AS_OF_INVALID
source_repo: bluemaple18-home/NEW-TOP10; local runner command output
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070; sha256:adabe16698646633375856c6b58be76ee56c0dccf7ea02dbc2c67a0f2870551d
source_path_or_official_url: scripts/run_backtest_strategy_matrix.py; scripts/run_autonomous_research.py; artifacts/market_regime_history_2026-05-29.json; runner command output summarized in this receipt
source_range_or_section: strategy matrix lines 520-624,821-835; run_autonomous_research.py lines 784-797; Reproducible runner command section
observed_at: 2026-09-01T08:10:43Z
confidence: HIGH
conflict_with: proceeding to full 720 benchmark after the configured as-of authority gate failed.
implication: Benchmark execution is blocked for the configured snapshot; the only valid delivery is a fail-closed receipt.
open_question: whether the configured history should be regenerated with as_of_date or replaced by another explicitly authorized configured snapshot.
owner: Future workload authority owner
```

### Claim BC-CP2-E3-720-005

```yaml
claim_id: BC-CP2-E3-720-005
claim: No 720 E3 benchmark was executed or claimed in this candidate; wall time, candidate/sec, CPU, peak RSS, I/O and output size remain unmeasured because the configured snapshot authority gate failed first.
classification: BENCHMARK_NOT_EXECUTED_BOUNDARY
source_repo: local runner command output
source_sha_or_version: sha256:adabe16698646633375856c6b58be76ee56c0dccf7ea02dbc2c67a0f2870551d
source_path_or_official_url: runner command output summarized in this receipt
source_range_or_section: Reproducible runner command section; Measurement receipt section
observed_at: 2026-09-01T08:10:43Z
confidence: HIGH
conflict_with: reporting capacity numbers from preflight, source inspection, prior 1-scenario characterization, or candidate-space count.
implication: Capacity remains unknown until the configured snapshot as-of/development workload gate is repaired and benchmark is actually run.
open_question: exact future benchmark command after configured snapshot authority is repaired.
owner: BC-CP2 capacity worker
```

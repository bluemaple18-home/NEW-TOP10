# BC-CP2-R1 Configured Regime History v2 Rebuild Receipt

## Scope receipt

- 工作名稱：`BC-CP2-R1 Configured Regime History v2 可重建修復`
- Slice ID：`BC-CP2-R1-REGIME-V2-01`
- Verdict：`REBUILD_REPLACED_TARGET_GO / NEXT_GATE_FAIL_CLOSED_NO_HORIZON_SAFE_DATES`
- Candidate 起點：`c3cdd3db493e8c314ded5336181f43c520756440`
- Canonical main：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- Configured source：`config/research_shadow_runs.yaml`
- Builder：`scripts/build_market_regime_history.py`
- Target：`artifacts/market_regime_history_2026-05-29.json`
- Dispatch card hash：`sha256:6e57edbc7602d785381f1267dc7ebe8e575d5ec667b444a24bea05695c3a42c8`
- Rebuild summary hash：`sha256:c9f89594253f1c24672235d86b9172c232a6605ea799e69a2b552fd687e92e40`
- Identity matrix summary hash：`sha256:c95d4413bca480bb2c14e209e77e81a6b059d248c60e5f53ed39d4e58a25391e`
- Observed at：`2026-09-01T08:31:00Z`
- Boundary：本次只修復 configured ignored artifact target，並只重跑 configured development authority gate 到下一個真實 blocker。未執行 720 benchmark、未修改 code/config/runner/ranking/production/既有 evidence，未 merge/push/改 Issue/external write，未准入 B0 Phase 2、B1 或 C1。

## Direct answer

Configured `market-regime-history.v1` target 已以 canonical builder 重建並替換為 `market-regime-history.v2`。原 target hash 為 `sha256:10bde4543a13558aa01df7764ff168c461ff78daf2e38989ed3fa467c99c5485`；新 target hash 為 `sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70`。

雙重建通過 semantic determinism：兩次 raw artifact hash 不同，因 `generated_at` 會變；排除 `generated_at` 與 input path 字段後，兩次 semantic hash 同為 `sha256:a1052f44ab6bc6fb9aa96b2ef55274b738f2ac0c6afb30cd14617cd2bb2e4cc1`。v2 schema、date range、row count、`as_of_date == trade_date`、base regime / family tags / transition contract、future-row stability 與 JSON finite checks 全部通過。替換後 target as-of validator 也通過。

替換後從 v2 artifact 列舉實際存在且非 `UNKNOWN` / transition 的 exact identities，共 `12` 個。`10` 個不能建立 trusted split；`2` 個可建立 split：

- `NARROW_LEADER|BIG_BULL`
- `NARROW_LEADER|BIG_BULL+HIGH_CHOPPY`

兩個 split-OK identity 的 development dates 都無法通過 `exact_horizon_safe_ranking_dates(...)`，在 horizon `3` 即 fail closed。因此本卡不准入 720 benchmark；下一 frontier 是修復 configured snapshot 的 exact identity episode continuity / horizon-safe date coverage，而不是切換 history、ranking root 或使用 placeholder/便利樣本。

## Rebuild manifest and validation

| Field | Evidence |
|---|---|
| Original target hash | `sha256:10bde4543a13558aa01df7764ff168c461ff78daf2e38989ed3fa467c99c5485` |
| Original target size | `170288` bytes |
| Rollback copy hash | `sha256:10bde4543a13558aa01df7764ff168c461ff78daf2e38989ed3fa467c99c5485` |
| Rebuild #1 raw hash | `sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70` |
| Rebuild #2 raw hash | `sha256:0ee7169c9a1b849b8be230faaf40be95ab76bd994a3c6ee98829a867b716cdd4` |
| Rebuild semantic hash #1 | `sha256:a1052f44ab6bc6fb9aa96b2ef55274b738f2ac0c6afb30cd14617cd2bb2e4cc1` |
| Rebuild semantic hash #2 | `sha256:a1052f44ab6bc6fb9aa96b2ef55274b738f2ac0c6afb30cd14617cd2bb2e4cc1` |
| Future stability hash | `sha256:59f925ea51b3698d61e894406e439234b27296b629f8e23ad9463eb647f48ba6` |
| Future prefix hash | `sha256:59f925ea51b3698d61e894406e439234b27296b629f8e23ad9463eb647f48ba6` |
| New target hash | `sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70` |
| New target size | `216519` bytes |
| Rebuild summary hash | `sha256:c9f89594253f1c24672235d86b9172c232a6605ea799e69a2b552fd687e92e40` |

Validation checks:

| Check | Result |
|---|---|
| `schema_version == market-regime-history.v2` | `PASS` |
| start date `2025-07-07` | `PASS` |
| end date `2026-05-29` | `PASS` |
| row count `218` equals summary trade days | `PASS` |
| every row `as_of_date == trade_date` | `PASS` |
| base regime equals regime label and is in contract taxonomy | `PASS` |
| family tags are sorted, unique and inside contract taxonomy | `PASS` |
| transition fields exist | `PASS` |
| JSON finite check | `PASS` |
| semantic determinism | `PASS` |
| future-row stability | `PASS` |
| target replaced by verified rebuild #1 | `PASS` |
| target validator after replacement | `PASS` |

## Input/source manifest

| Root | Relpath | Size bytes | SHA-256 |
|---|---:|---:|---|
| `<repo-root>` | `scripts/build_market_regime_history.py` | `20626` | `sha256:f210caf432ca8bace98c23b4d38f46db5f3f41226564e2ecb8452c7afdf57e71` |
| `<repo-root>` | `scripts/run_backtest_strategy_matrix.py` | `35846` | `sha256:39b42aac6d7c232c9bbb4f1d8981b55ca43826758d91cd3a45281ff19f590b43` |
| `<repo-root>` | `scripts/run_autonomous_research.py` | `178280` | `sha256:2c5b9b11c22b13aeae78045a721c362f1ad65390ea69eac075e69f0807df951c` |
| `<repo-root>` | `scripts/run_backtest_replay.py` | `23040` | `sha256:2df70b6efe3920cb5c709cafc9ae0cb2597d60753a28ab7fc068eee739285c77` |
| `<repo-root>` | `scripts/run_portfolio_replay.py` | `34972` | `sha256:5909f56e749aad562c470fd9f965fff5db34f8444d136bb894dec0ed1adbc85f` |
| `<repo-root>` | `config/research_shadow_runs.yaml` | `2584` | `sha256:6b1ab4d074c4d9ddd8ab8e62dd26ab79c078bb05f7323aeb75d616cc07b7116d` |
| `<repo-root>` | `config/research_parameter_catalog.json` | `7243` | `sha256:e88079414dfae381b96bd4a46326e38b8288447710008ecfe9c1d73b6ec66500` |
| `<repo-root>` | `config/regime_research_contract.json` | `5562` | `sha256:e3ada41e5a9de4f471750f298718ba815582db550abd9b537a73b66bd818bc34` |
| `<local-data-root>` | `data/clean/features.parquet` | `137774296` | `sha256:93e8432987b6037db243b2864f7bc8d09f12acd50249d9238d2acddacd2561d2` |
| `<local-data-root>` | `data/reference/stock_industry_map.csv` | `207126` | `sha256:86ca58072c0db0581df741e212b0bccc641848638b52b4ae1e3b1a0b4e96cb20` |
| `<local-data-root>` | `artifacts/market_regime_history_2026-05-29.json` before replacement | `170288` | `sha256:10bde4543a13558aa01df7764ff168c461ff78daf2e38989ed3fa467c99c5485` |
| `<local-data-root>` | `artifacts/market_regime_history_2026-05-29.json` after replacement | `216519` | `sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70` |

Source/input parity:

- Source files and immutable inputs other than target were unchanged before/after replacement：`PASS`。
- Rollback copy matched original target bytes before replacement：`PASS`。
- Rollback path existed only inside isolated temp during replacement; temp cleanup removed rebuild and rollback temp artifacts after successful final verification。

## Rebuild commands

Token mapping / cwd contract:

- `<repo-root>`：isolated clean worktree root for this candidate.
- `<local-data-root>`：Owner-authorized local snapshot root containing configured ignored artifacts and data.
- `<temp-output-1>` / `<temp-output-2>` / `<temp-future-output>`：isolated temporary JSON output paths outside source/data roots.
- CWD：`<repo-root>`.

Canonical rebuild command #1:

```bash
<local-data-root>/.venv/bin/python scripts/build_market_regime_history.py \
  --features <local-data-root>/data/clean/features.parquet \
  --industry-map <local-data-root>/data/reference/stock_industry_map.csv \
  --end-date 2026-05-29 \
  --output <temp-output-1>
```

Canonical rebuild command #2:

```bash
<local-data-root>/.venv/bin/python scripts/build_market_regime_history.py \
  --features <local-data-root>/data/clean/features.parquet \
  --industry-map <local-data-root>/data/reference/stock_industry_map.csv \
  --end-date 2026-05-29 \
  --output <temp-output-2>
```

Future-row stability command:

```bash
<local-data-root>/.venv/bin/python scripts/build_market_regime_history.py \
  --features <local-data-root>/data/clean/features.parquet \
  --industry-map <local-data-root>/data/reference/stock_industry_map.csv \
  --output <temp-future-output>
```

Semantic hash excludes only `generated_at` and input path string fields. Rows through `2026-05-29` matched the same-row prefix of the future build.

## Per-identity lineage matrix

Rows are non-`UNKNOWN`, non-transition rows in the rebuilt configured target.

| Exact identity | Rows | Episodes | Lineage result | Horizon-safe result |
|---|---:|---:|---|---|
| `BROAD_RISK_ON|BIG_BULL` | `3` | `3` | `FAIL` — 完整盤勢 episode 不足，無法建立封閉切分 | `NOT_REACHED` |
| `CHOPPY_RANGE|BIG_BULL` | `1` | `1` | `FAIL` — 完整盤勢 episode 不足，無法建立封閉切分 | `NOT_REACHED` |
| `MIXED_NEUTRAL|` | `3` | `2` | `FAIL` — 完整盤勢 episode 不足，無法建立封閉切分 | `NOT_REACHED` |
| `MIXED_NEUTRAL|BIG_BULL+HIGH_CHOPPY` | `6` | `4` | `FAIL` — 完整盤勢 episode 不足，無法建立封閉切分 | `NOT_REACHED` |
| `MIXED_NEUTRAL|HIGH_CHOPPY` | `2` | `2` | `FAIL` — 完整盤勢 episode 不足，無法建立封閉切分 | `NOT_REACHED` |
| `NARROW_LEADER|` | `8` | `7` | `FAIL` — `development_available=0 required=2 embargo_days=7 required_embargo_days=20` | `NOT_REACHED` |
| `NARROW_LEADER|BIG_BULL` | `29` | `14` | `GO`; development dates `2025-08-13, 2025-08-15, 2025-08-18, 2025-08-27, 2025-08-28, 2025-08-29` | `FAIL` — `NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE: horizon=3 allowed_date_count=6` |
| `NARROW_LEADER|BIG_BULL+HIGH_CHOPPY` | `28` | `13` | `GO`; development dates `2025-08-12, 2025-08-14, 2025-09-08` | `FAIL` — `NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE: horizon=3 allowed_date_count=3` |
| `NARROW_LEADER|HIGH_CHOPPY` | `4` | `2` | `FAIL` — 完整盤勢 episode 不足，無法建立封閉切分 | `NOT_REACHED` |
| `PANIC_SELLING|` | `17` | `2` | `FAIL` — 完整盤勢 episode 不足，無法建立封閉切分 | `NOT_REACHED` |
| `RISK_OFF|` | `46` | `9` | `FAIL` — `development_available=0 required=2 embargo_days=30 required_embargo_days=20` | `NOT_REACHED` |
| `RISK_OFF|BIG_BULL` | `12` | `5` | `FAIL` — `development_available=0 required=2 embargo_days=9 required_embargo_days=20` | `NOT_REACHED` |

Identity matrix summary hash：`sha256:c95d4413bca480bb2c14e209e77e81a6b059d248c60e5f53ed39d4e58a25391e`。

## Next configured development authority gate

Because `NARROW_LEADER|BIG_BULL` is the first split-OK exact identity in sorted order, the next gate command used its canonical development episode IDs:

```text
sha256:ab2442b043277e8b884856d3eade50987206a335d15449eb1a7df94155c1ee8a
sha256:5b93ba0b6cbc1c00d2bae026ff2cf30cba5505e7d8106ee76a9b5d31d74d0caa
sha256:cca35396aec295940b89b961aae1b52d59c3e2290153d635858217decf3a3764
```

Tokenized command executed from `<repo-root>`:

```bash
<local-data-root>/.venv/bin/python scripts/run_backtest_strategy_matrix.py \
  --rankings-dir <local-data-root>/artifacts/backtest/historical_rankings_current_model \
  --features <local-data-root>/data/clean/features.parquet \
  --require-exact-regime \
  --market-regime-history <local-data-root>/artifacts/market_regime_history_2026-05-29.json \
  --base-regime NARROW_LEADER \
  --family-tags BIG_BULL \
  --allowed-episode-ids sha256:ab2442b043277e8b884856d3eade50987206a335d15449eb1a7df94155c1ee8a,sha256:5b93ba0b6cbc1c00d2bae026ff2cf30cba5505e7d8106ee76a9b5d31d74d0caa,sha256:cca35396aec295940b89b961aae1b52d59c3e2290153d635858217decf3a3764 \
  --development-only \
  --horizons 3,5,10,20 \
  --stop-loss-pcts none,0.05,0.06,0.08,0.10,0.12 \
  --take-profit-pcts none,0.10,0.15,0.20,0.25,0.30 \
  --max-group-exposures none,0.25,0.35,0.45,0.55 \
  --output <temp-output>
```

Observed result:

```text
exit_code: 1
output_probe_exists: false
failing_frame: scripts/run_backtest_strategy_matrix.py build_payload → exact_horizon_safe_ranking_dates
error: ValueError: NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE: horizon=3 allowed_date_count=6
```

Interpretation: R1 fixed the configured as-of failure, and at least two real exact identities can build a trusted split. The next true blocker is absence of horizon-safe exact-regime ranking dates for configured development episodes. No 720 benchmark was executed.

## Target final state and cleanup

- Target final schema：`market-regime-history.v2`
- Target final row count：`218`
- Target final date range：`2025-07-07` to `2026-05-29`
- Latest row base regime：`NARROW_LEADER`
- Latest row family tags：`["BIG_BULL"]`
- Target final hash：`sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70`
- Temp cleanup：`PASS`; rebuild temp, rollback temp, identity summary temp and gate output probe removed.
- Non-extrapolation boundary：本 receipt 只證明 configured ignored artifact target 可重建替換，並定位下一個 authority gate；不得外推為 workload authority、720 benchmark readiness、research validity、ranking provenance、production readiness、B0 Phase 2、B1 或 C1 admission。

## Minimum next authority

1. Preserve the configured snapshot route; do not switch history/ranking roots without new explicit authority.
2. Decide whether the configured window should use exact identities whose development episodes occur in `2025-08`/`2025-09`, or whether the configured history/window must be regenerated so development episodes align with configured ranking dates.
3. Establish horizon-safe ranking dates for horizons `3,5,10,20` under a split-OK exact identity.
4. Only after development authority, horizon-safe date coverage, ranking overlap and output boundary pass may a separate card admit full 720 E3 benchmark.

## Claim Ledger

### Claim BC-CP2-R1-001

```yaml
claim_id: BC-CP2-R1-001
claim: The R1 dispatch authorizes rebuilding and replacing only the configured ignored market_regime_history_2026-05-29.json target using the canonical builder, with fail-closed behavior and no benchmark admission.
classification: DISPATCH_AUTHORITY_AND_BOUNDARY
source_repo: local dispatch input
source_sha_or_version: sha256:6e57edbc7602d785381f1267dc7ebe8e575d5ec667b444a24bea05695c3a42c8
source_path_or_official_url: docs/tasks/2026-09-01_REPAIR-NEW-TOP10-BC-CP2-CONFIGURED-REGIME-HISTORY-V2-REBUILD.md
source_range_or_section: lines 5-15
observed_at: 2026-09-01T08:31:00Z
confidence: HIGH
conflict_with: modifying code/config/runner/ranking/production, switching configured inputs, or running the 720 benchmark in this repair.
implication: Only the ignored configured target and this evidence receipt are in scope.
open_question: none for R1 authority.
owner: Owner / Mainline dispatcher
```

### Claim BC-CP2-R1-002

```yaml
claim_id: BC-CP2-R1-002
claim: The configured v1 target was preserved before replacement: original target hash and rollback copy hash both equal sha256:10bde4543a13558aa01df7764ff168c461ff78daf2e38989ed3fa467c99c5485.
classification: ROLLBACK_PRESERVED_ORIGINAL_BYTES
source_repo: local configured ignored artifact
source_sha_or_version: original target sha256:10bde4543a13558aa01df7764ff168c461ff78daf2e38989ed3fa467c99c5485; summary sha256:c9f89594253f1c24672235d86b9172c232a6605ea799e69a2b552fd687e92e40
source_path_or_official_url: artifacts/market_regime_history_2026-05-29.json; rebuild summary summarized in this receipt
source_range_or_section: Rebuild manifest and validation section; Input/source manifest section
observed_at: 2026-09-01T08:31:00Z
confidence: HIGH
conflict_with: replacing an ignored artifact without preserving original bytes.
implication: The replacement was performed with a rollback copy available during the transaction.
open_question: none for original-byte preservation.
owner: BC-CP2-R1 repair worker
```

### Claim BC-CP2-R1-003

```yaml
claim_id: BC-CP2-R1-003
claim: Canonical rebuild validation passed: two temp rebuilds had identical semantic hash after excluding generated_at and input path fields; v2 schema, row/date/as-of/base-regime/family-tags/transition/finite/future-stability checks all passed.
classification: CANONICAL_REBUILD_VALIDATION_GO
source_repo: bluemaple18-home/NEW-TOP10; local rebuild summary
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070; summary sha256:c9f89594253f1c24672235d86b9172c232a6605ea799e69a2b552fd687e92e40
source_path_or_official_url: scripts/build_market_regime_history.py; config/regime_research_contract.json; rebuilt temp artifacts summarized in this receipt
source_range_or_section: builder lines 1-260; regime contract lines 15-64,136-143; Rebuild manifest and validation section; Rebuild commands section
observed_at: 2026-09-01T08:31:00Z
confidence: HIGH
conflict_with: manually patching the v1 artifact or accepting timestamp-only raw hash differences as semantic nondeterminism.
implication: The target may be replaced with the verified v2 rebuild.
open_question: none for rebuild determinism and schema validity.
owner: BC-CP2-R1 repair worker
```

### Claim BC-CP2-R1-004

```yaml
claim_id: BC-CP2-R1-004
claim: The configured target was replaced with verified v2 bytes and revalidated: final target hash is sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70, schema is market-regime-history.v2, as-of validation passes, and source inputs other than target were unchanged.
classification: TARGET_REPLACEMENT_GO
source_repo: local configured ignored artifact; bluemaple18-home/NEW-TOP10
source_sha_or_version: new target sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70; summary sha256:c9f89594253f1c24672235d86b9172c232a6605ea799e69a2b552fd687e92e40; canonical source 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: artifacts/market_regime_history_2026-05-29.json; scripts/run_autonomous_research.py; rebuild summary summarized in this receipt
source_range_or_section: run_autonomous_research.py lines 369-397,784-797; Target final state and cleanup section; Input/source manifest section
observed_at: 2026-09-01T08:31:00Z
confidence: HIGH
conflict_with: leaving the configured target at v1 or with failing as-of rows.
implication: The prior configured as-of blocker is repaired.
open_question: horizon-safe development dates still fail.
owner: BC-CP2-R1 repair worker
```

### Claim BC-CP2-R1-005

```yaml
claim_id: BC-CP2-R1-005
claim: The real post-replacement next gate is horizon-safe date failure, not placeholder duplicate episode ID: 12 exact identities were enumerated, 2 identities built trusted splits, and the first split-OK identity NARROW_LEADER|BIG_BULL failed the full configured development command at NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE before benchmark execution.
classification: NEXT_GATE_FAIL_CLOSED_NO_HORIZON_SAFE_DATES
source_repo: local identity matrix and runner command output; bluemaple18-home/NEW-TOP10
source_sha_or_version: identity matrix sha256:c95d4413bca480bb2c14e209e77e81a6b059d248c60e5f53ed39d4e58a25391e; canonical source 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: scripts/run_backtest_strategy_matrix.py; scripts/run_autonomous_research.py; app/modeling/sealed_oos.py; identity matrix and runner command output summarized in this receipt
source_range_or_section: strategy matrix lines 226-253,520-624,821-835; run_autonomous_research.py lines 740-818; sealed_oos.py lines 86-108; Per-identity lineage matrix section; Next configured development authority gate section
observed_at: 2026-09-01T08:31:00Z
confidence: HIGH
conflict_with: using placeholder episode IDs, probing a non-existent exact identity, or running benchmark after split without horizon-safe dates.
implication: The next card should repair configured horizon-safe development date coverage; full 720 E3 benchmark remains not admitted.
open_question: whether configured history/window or configured ranking dates should be re-authorized to align exact development episodes with horizon-safe replay dates.
owner: Future workload authority owner
```

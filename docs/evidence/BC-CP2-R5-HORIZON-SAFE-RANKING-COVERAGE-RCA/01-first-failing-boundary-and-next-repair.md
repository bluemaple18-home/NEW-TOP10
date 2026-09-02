# BC-CP2 R5 Horizon-safe Ranking Coverage RCA

## Scope receipt

- 工作名稱：`BC-CP2 R5 Horizon-safe Ranking Coverage RCA`
- Slice ID：`BC-CP2-R5-HORIZON-SAFE-RANKING-COVERAGE-RCA`
- Verdict：`NO-GO / FIRST_BOUNDARY_HORIZON_SAFE_EPISODE_CONTINUITY / RANKING_COVERAGE_ZERO_OVERLAP`
- Fixed parent：`6cd27cc08302d64825b8012d0181fb7a0a85e441`
- Canonical main：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- B0 authority：`1e9ed61e2e5c86adf2159e095ff241ef13127e80`
- R1：`319eee83cdf6001f094c5bd2597657aa2d3d7c40`
- R4：`6cd27cc08302d64825b8012d0181fb7a0a85e441`
- Dispatch card SHA-256：`sha256:4f4e0d2573179cd81d5cff20ee513b2de0ec8f542ae61d2a6d8f673a43fde1b9`
- Boundary：本卡只做唯讀 RCA 與暫存 characterization；未修改 code、tests、config、history、features、ranking、workflow、runner、queue、scheduler、backtest、production 或既有 evidence；未執行 full-720 benchmark；未 merge、push、改 Issue、deploy 或 external write；未准入 B0 Phase 2、B1、C0 Phase 2 或 C1。

## Direct answer

R1 failing gate 可重現，錯誤仍是：

```text
ValueError: NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE: horizon=3 allowed_date_count=6
```

第一個 runner 實際斷點是 `scripts/run_backtest_strategy_matrix.py::exact_horizon_safe_ranking_dates` 的 horizon-safe episode continuity gate：第一個 trusted identity `NARROW_LEADER|BIG_BULL` 的第一個 development ranking date `2025-08-13`，D+1 entry 是 `2025-08-14`，horizon 3 holding dates 是 `2025-08-14, 2025-08-15, 2025-08-18`，但原 episode 只有 `2025-08-13`，所以 window 立刻跨出 immutable exact-regime episode。

同時，configured ranking root 也有獨立 coverage 斷點：ranking files 只有 `2026-04-08..2026-05-13` 共 `25` 天；兩個 trusted identities 的 development dates 分別在 `2025-08` 與 `2025-09`，與 ranking files 完全零交集。這個 ranking coverage 問題在 runner 中尚未到達，因為 horizon-safe helper 先 fail closed。

## Source decision

| Check | Result |
|---|---|
| CodeGraph status | `FAILED` — isolated worktree 未初始化 CodeGraph。 |
| Fallback | 限域讀取 `scripts/run_backtest_strategy_matrix.py`、`scripts/run_autonomous_research.py`、R1 receipt 與 configured artifacts；未初始化 CodeGraph，未改 source。 |

## Fixed inputs

| Input | Size / count | SHA-256 |
|---|---:|---|
| R5 dispatch card | checked before removal | `sha256:4f4e0d2573179cd81d5cff20ee513b2de0ec8f542ae61d2a6d8f673a43fde1b9` |
| `<local-data-root>/artifacts/market_regime_history_2026-05-29.json` | `216519` bytes; `218` rows; `2025-07-07..2026-05-29` | `sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70` |
| `<local-data-root>/data/clean/features.parquet` | `282` unique trade dates; `2025-07-07..2026-08-31` | `sha256:93e8432987b6037db243b2864f7bc8d09f12acd50249d9238d2acddacd2561d2` |
| `<local-data-root>/data/reference/stock_industry_map.csv` | configured reference input | `sha256:86ca58072c0db0581df741e212b0bccc641848638b52b4ae1e3b1a0b4e96cb20` |
| `<local-data-root>/artifacts/backtest/historical_rankings_current_model` ranking files | `25` files; `2026-04-08..2026-05-13` | manifest `sha256:3a25c31e79def64736b6bc0cea57396c929151fd99f6bee72dc974b6f18175e6` |
| `scripts/run_backtest_strategy_matrix.py` | canonical helper / runner seam | `sha256:39b42aac6d7c232c9bbb4f1d8981b55ca43826758d91cd3a45281ff19f590b43` |
| `scripts/run_autonomous_research.py` | episode builder / split lineage | `sha256:2c5b9b11c22b13aeae78045a721c362f1ad65390ea69eac075e69f0807df951c` |
| `config/regime_research_contract.json` | split policy / taxonomy | `sha256:e3ada41e5a9de4f471750f298718ba815582db550abd9b537a73b66bd818bc34` |
| `config/research_parameter_catalog.json` | parameter authority | `sha256:e88079414dfae381b96bd4a46326e38b8288447710008ecfe9c1d73b6ec66500` |

## Reproduction evidence

Tokenized command shape from clean fixed parent:

```bash
<python> scripts/run_backtest_strategy_matrix.py \
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

Observed:

```text
exit_code: 1
output_probe_exists: false
failing_frame: scripts/run_backtest_strategy_matrix.py build_payload -> exact_horizon_safe_ranking_dates
error: ValueError: NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE: horizon=3 allowed_date_count=6
```

Arrow emitted sandbox CPU-cache `sysctlbyname` warnings, but the terminal failure was the expected R1 gate, not an import/environment failure.

## Trusted identity characterization

| Identity | Rows | Episodes | Development episodes | Development dates | Ranking-file overlap | Feature-date coverage | h3 | h5 | h10 | h20 |
|---|---:|---:|---:|---|---:|---:|---|---|---|---|
| `NARROW_LEADER|BIG_BULL` | `29` | `14` | `3` | `2025-08-13, 2025-08-15, 2025-08-18, 2025-08-27, 2025-08-28, 2025-08-29` | `0 / 6` | `6 / 6` | `0` safe; helper error `allowed_date_count=6` | `0` safe | `0` safe | `0` safe |
| `NARROW_LEADER|BIG_BULL+HIGH_CHOPPY` | `28` | `13` | `3` | `2025-08-12, 2025-08-14, 2025-09-08` | `0 / 3` | `3 / 3` | `0` safe; helper error `allowed_date_count=3` | `0` safe | `0` safe | `0` safe |

### `NARROW_LEADER|BIG_BULL` development boundaries

| Episode ID | Start | End | Trade dates | First h3 failing reason |
|---|---|---|---:|---|
| `sha256:ab2442b043277e8b884856d3eade50987206a335d15449eb1a7df94155c1ee8a` | `2025-08-13` | `2025-08-13` | `1` | ranking `2025-08-13` -> entry `2025-08-14`; window crosses immediately at `2025-08-14`. |
| `sha256:5b93ba0b6cbc1c00d2bae026ff2cf30cba5505e7d8106ee76a9b5d31d74d0caa` | `2025-08-15` | `2025-08-18` | `2` | h3 needs ranking date plus three holding dates; episode too short. |
| `sha256:cca35396aec295940b89b961aae1b52d59c3e2290153d635858217decf3a3764` | `2025-08-27` | `2025-08-29` | `3` | h3 needs ranking date plus three holding dates; episode ends before full window remains inside identity. |

### `NARROW_LEADER|BIG_BULL+HIGH_CHOPPY` development boundaries

| Episode ID | Start | End | Trade dates | First h3 failing reason |
|---|---|---|---:|---|
| `sha256:45bb53389aeb0c3639e89aeded85f73b72848b1e3d6c5881f6c108d733ab235d` | `2025-08-12` | `2025-08-12` | `1` | ranking `2025-08-12` -> entry `2025-08-13`; window crosses immediately at `2025-08-13`. |
| `sha256:b707c31b2893367e153d22fb3da9e58175bb3bd8afec20998c0cbd335123286b` | `2025-08-14` | `2025-08-14` | `1` | h3 needs ranking date plus three holding dates; episode has only one day. |
| `sha256:96c97a341f104a04d19cb2a3d70233422969f81a22b7ca62053c0b9574e21945` | `2025-09-08` | `2025-09-08` | `1` | h3 needs ranking date plus three holding dates; episode has only one day. |

## Layered boundary map

| Layer | Evidence | Status |
|---|---|---|
| Development split authority | Both trusted identities can build development/validation/embargo/sealed split lineage. | `PASS` |
| Development dates | `NARROW_LEADER|BIG_BULL` has `6`; `NARROW_LEADER|BIG_BULL+HIGH_CHOPPY` has `3`. | `PASS` |
| Feature trading dates | Features cover all development dates for both identities. | `PASS` |
| Episode continuity | No development episode can keep ranking date + D+1 entry + h3 holding window inside the same immutable exact-regime episode. | `FIRST_RUNNER_FAILING_BOUNDARY` |
| Ranking dates | Configured ranking root has `25` files from `2026-04-08` to `2026-05-13`; overlap with both trusted identities' development dates is `0`. | `SECOND_COVERAGE_BOUNDARY_NOT_REACHED_BY_RUNNER` |
| Horizons `3/5/10/20` | All four horizons return zero safe dates for both trusted identities. | `FAIL_CLOSED` |

## Why not less / why not more / do not absorb

- why_not_less：只重貼 R1 `horizon=3` 錯誤不足以區分是 feature dates 缺、ranking files 缺、episode continuity 缺，還是 split authority 缺；本卡用同一 helper 與 configured inputs 拆到第一可驗斷點。
- why_not_more：不需要修改 runner、重建 ranking、改 regime history、跑 full-720 或做 research replay；這些都會越過 RCA 邊界。
- do_not_absorb：不吸收新 horizon-safe 演算法、不切換 history/ranking root、不使用 placeholder ranking dates、不放寬 exact-regime episode gate、不建立 queue/scheduler/production 變更。

## Minimum next frontier

唯一最小下一卡：`BC-CP2-R6-CONFIGURED-DEVELOPMENT-RANKING-COVERAGE-AUTHORITY`

下一卡只應決定並修復 configured workload 的 authority alignment：讓 selected trusted exact identity 同時具備可用 development episodes、與 development dates 對齊的 ranking files、以及至少 horizon `3/5/10/20` 的 horizon-safe episode continuity。未通過前，不得進 B0 Phase 2、B1、C0 Phase 2、C1、production canary 或 full benchmark admission。

## Verification

| Check | Result |
|---|---|
| Card hash gate | `PASS` — dispatch card matched `sha256:4f4e0d2573179cd81d5cff20ee513b2de0ec8f542ae61d2a6d8f673a43fde1b9` before removal. |
| Fixed parent gate | `PASS` — pre-work HEAD was `6cd27cc08302d64825b8012d0181fb7a0a85e441`. |
| Clean pre-run gate | `PASS` — after removing dispatch-only untracked card copy, `git status --short` was empty. |
| R1 failing gate reproduction | `PASS` — same `NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE: horizon=3 allowed_date_count=6`, output probe absent. |
| Full-720 boundary | `PASS` — no full-720 benchmark was executed. |
| Changed-file allowlist | `PASS` — `git status --short` showed only `docs/evidence/BC-CP2-R5-HORIZON-SAFE-RANKING-COVERAGE-RCA/`; that directory contains only `01-first-failing-boundary-and-next-repair.md`. |
| Diff hygiene | `PASS` — `git diff --check` exited `0` after this evidence was written. |

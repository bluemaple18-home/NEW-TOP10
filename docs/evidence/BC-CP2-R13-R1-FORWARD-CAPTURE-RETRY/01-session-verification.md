# BC-CP2 R13-R1 forward-capture retry session verification

## Receipt

- Task：`BC-CP2-R13-R1-FORWARD-CAPTURE-RETRY`
- Fixed source：`f7f9d46fb29f0e52b3a276738370f4192a7c2d68`
- Worktree：`/private/tmp/top10new-r13-trusted-date-authority-20260902`
- Task card：`docs/tasks/2026-09-02_RUN-NEW-TOP10-BC-CP2-R13-R1-FORWARD-CAPTURE-RETRY.md`
- Original R13 task：`docs/tasks/2026-09-01_RUN-NEW-TOP10-BC-CP2-R13-MINIMAL-FORWARD-CAPTURE-SESSION-EVIDENCE.md`
- Original R13 evidence：`docs/evidence/BC-CP2-R13-MINIMAL-FORWARD-CAPTURE-SESSION-EVIDENCE/01-session-decision.md`
- Authority repair task：`docs/tasks/2026-09-02_REPAIR-NEW-TOP10-R13-TRUSTED-COMPLETED-TRADE-DATE-AUTHORITY.md`
- Authority repair evidence：`docs/evidence/REPAIR-NEW-TOP10-R13-TRUSTED-COMPLETED-TRADE-DATE-AUTHORITY/verification.md`
- Run identity：`r13-r1-20260901-f7f9d46`
- Capture date：`2026-09-01`
- Capture mode：`FORWARD_CAPTURE`
- Verdict：`NO_GO_EXISTING_SEAM_RUNTIME_FAILURE`
- Capture attempt count：`1`
- COMPLETE bundle：`NOT_CREATED`
- Bundle verification：`INVALID / manifest_unreadable`
- Outcome-free：`YES`
- Scope guard：未修改 source、config、model、正式 data/ranking、主 checkout；未 network fetch；未讀 outcome/sealed data；未 replay/benchmark/training；未 push/merge/deploy/production/external write。

## Source decision

CodeGraph gate：

- `codegraph_status(projectPath="/private/tmp/top10new-r13-trusted-date-authority-20260902")`
- Result：`CodeGraph not initialized`

依 repo 規則降級為限域唯讀檢查，只檢查：

- `scripts/research_regime_shadow_ranking.py`
- `scripts/build_market_regime_history.py`
- `app/research/ranking_provenance_receipt.py`
- R13/R13-R1 task cards and evidence listed above

## Preflight gates

| Gate | Evidence | Result |
| --- | --- | --- |
| Fixed source | `git rev-parse HEAD` returned `f7f9d46fb29f0e52b3a276738370f4192a7c2d68` | PASS |
| Source clean | `git diff --name-only` empty; `git status --porcelain --untracked-files=all` had only this task card before run artifacts | PASS |
| Main checkout read-only | before/after `git -C /Users/mattkuo/TOP10new diff --name-only` empty | PASS |
| Run identity uniqueness | no existing file under `artifacts/backtest/*r13-r1-20260901-f7f9d46*` before copy | PASS |
| Copy, not link | copied inputs have same byte size/hash as main checkout, different inode, file type `Regular File` | PASS |
| Input hash stability | copied hashes match main checkout hashes before capture; main checkout hashes unchanged after capture failure | PASS |
| Features freshness | copied `features.parquet` max date `2026-09-01`, rows for date `1930`, unique stocks `1930` | PASS |
| Universe freshness | copied `universe.parquet` max date `2026-09-01`, rows for date `1019`, unique stocks `1019` | PASS |
| Calendar schedule source | copied `ranking_2026-09-01.csv` has `10` rows and `10` unique stock IDs; used only as `dates-from-dir` schedule source | PASS |
| Completed-date authority | validator accepted `automation_status_2026-09-01.json`; trusted date `2026-09-01`; returned hash `sha256:0211252a3aa28676a42f9ecdf7c03b675a56ad215d98b240c381d8e5540b6400` | PASS |
| Fresh regime history | canonical builder output schema `market-regime-history.v2`, max trade date `2026-09-01`, rows `282`, `as_of_date == trade_date` violations `0` | PASS |
| Session size | `du -sk artifacts/backtest/r13-r1-20260901-f7f9d46` after failure returned `187900` KiB | PASS |

PyArrow emitted sandbox `sysctlbyname` warnings during parquet reads. The reads completed and did not change the gate results.

## Input hashes

| Input | Main checkout sha256 | Copied sha256 |
| --- | --- | --- |
| `data/clean/features.parquet` | `aab60603280ae3d2a603b705ab02c5b19f518dcf178080482b2500b221f954ce` | `aab60603280ae3d2a603b705ab02c5b19f518dcf178080482b2500b221f954ce` |
| `data/clean/universe.parquet` | `f658800012a8f8072e62aad053fe984b9c2a5d70c370b00b6f74c795fc81c109` | `f658800012a8f8072e62aad053fe984b9c2a5d70c370b00b6f74c795fc81c109` |
| `artifacts/ranking_2026-09-01.csv` | `cd917dcc36f6c56d9989faaadc95f30120023bad89753780631d91feb9d94171` | `cd917dcc36f6c56d9989faaadc95f30120023bad89753780631d91feb9d94171` |
| `artifacts/automation_status_2026-09-01.json` | `0211252a3aa28676a42f9ecdf7c03b675a56ad215d98b240c381d8e5540b6400` | `0211252a3aa28676a42f9ecdf7c03b675a56ad215d98b240c381d8e5540b6400` |
| `models/latest_lgbm.pkl` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` |
| `config/signals.yaml` | `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a` | `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a` |
| `data/reference/stock_industry_map.csv` | `86ca58072c0db0581df741e212b0bccc641848638b52b4ae1e3b1a0b4e96cb20` | `86ca58072c0db0581df741e212b0bccc641848638b52b4ae1e3b1a0b4e96cb20` |

Generated isolated regime history：

- `artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/artifacts/market_regime_history_2026-09-01.json`
- sha256：`2e8e2953ca7e0c75686f0defdbdd0ffb575fb53687610e5a904278ef2a9de20f`
- markdown sidecar sha256：`30daf27bd49d68d11b315bbc41d2123f2f31bb94bdc152588b4ff72ad4fefbd9`
- latest：`2026-09-01 / RISK_OFF`

## Capture attempt

Command：

```bash
.venv/bin/python scripts/research_regime_shadow_ranking.py --dates-from-dir artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/artifacts/calendar --output-dir artifacts/backtest/r13-r1-20260901-f7f9d46/output --market-regime-history artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/artifacts/market_regime_history_2026-09-01.json --industry-map artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/data/reference/stock_industry_map.csv --data-dir artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/data/clean --model-dir artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/models --config artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/config/signals.yaml --forward-capture --capture-trade-date 2026-09-01 --capture-authority-artifact artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/artifacts/authority/automation_status_2026-09-01.json --run-identity r13-r1-20260901-f7f9d46
```

Result：

- Exit：`1`
- Capture verdict：`NO_GO_EXISTING_SEAM_RUNTIME_FAILURE`
- Failure point：`StockRanker.calculate_scores(daily)`
- Error：`ValueError: M4 推論資料缺少訓練契約欄位`
- Missing fields shown by runtime：`event_break_20d_high`, `event_lose_20d_low`, `event_ma5_cross_ma20_up`, `event_ma5_cross_ma20_down`, `event_close_above_bb_mid`, `event_close_below_bb_mid`, `event_macd_bullish_cross`, `event_macd_bearish_cross`, `event_rsi_rebound_from_40`, `event_rsi_break_below_50`

This is the single allowed true `FORWARD_CAPTURE` attempt for this card. No second capture attempt was run.

## Bundle and artifacts

| Artifact | Path | Status | Hash |
| --- | --- | --- | --- |
| COMPLETE bundle | `artifacts/backtest/r13-r1-20260901-f7f9d46/output/.ranking-provenance-v1/runs/r13-r1-20260901-f7f9d46/COMPLETE.manifest.json` | `NOT_CREATED` | `NONE` |
| Bundle verification | same path | `INVALID / manifest_unreadable` | `NONE` |
| Failed marker | `artifacts/backtest/r13-r1-20260901-f7f9d46/output/.ranking-provenance-staging/r13-r1-20260901-f7f9d46/FAILED.json` | `CREATED` | `e2b8c9c351b0450b7659120227b64ef518543feaa7fe735014fbd4936732155d` |
| Staging model snapshot | `artifacts/backtest/r13-r1-20260901-f7f9d46/output/.ranking-provenance-staging/r13-r1-20260901-f7f9d46/model_snapshots/model-ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d.pkl` | `CREATED` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` |
| Ranking output | `artifacts/backtest/r13-r1-20260901-f7f9d46/output/ranking_2026-09-01.csv` | `NOT_CREATED` | `NONE` |
| Receipt output | `artifacts/backtest/r13-r1-20260901-f7f9d46/output/.ranking-provenance-v1/.../receipts/ranking_2026-09-01.receipt.json` | `NOT_CREATED` | `NONE` |

Failed marker content：

```json
{"reason":"ranking_generation_failed","run_identity":"r13-r1-20260901-f7f9d46","status":"FAILED"}
```

## Verification commands

```bash
git rev-parse HEAD
git diff --name-only
git status --porcelain --untracked-files=all
shasum -a 256 /Users/mattkuo/TOP10new/data/clean/features.parquet /Users/mattkuo/TOP10new/data/clean/universe.parquet /Users/mattkuo/TOP10new/artifacts/ranking_2026-09-01.csv /Users/mattkuo/TOP10new/artifacts/automation_status_2026-09-01.json /Users/mattkuo/TOP10new/models/latest_lgbm.pkl /Users/mattkuo/TOP10new/config/signals.yaml /Users/mattkuo/TOP10new/data/reference/stock_industry_map.csv
shasum -a 256 artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/data/clean/features.parquet artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/data/clean/universe.parquet artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/artifacts/calendar/ranking_2026-09-01.csv artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/artifacts/authority/automation_status_2026-09-01.json artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/models/latest_lgbm.pkl artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/config/signals.yaml artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/data/reference/stock_industry_map.csv
stat -f '%N %i %z %HT' /Users/mattkuo/TOP10new/data/clean/features.parquet /Users/mattkuo/TOP10new/data/clean/universe.parquet /Users/mattkuo/TOP10new/artifacts/ranking_2026-09-01.csv /Users/mattkuo/TOP10new/artifacts/automation_status_2026-09-01.json artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/data/clean/features.parquet artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/data/clean/universe.parquet artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/artifacts/calendar/ranking_2026-09-01.csv artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/artifacts/authority/automation_status_2026-09-01.json
.venv/bin/python scripts/build_market_regime_history.py --features artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/data/clean/features.parquet --industry-map artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/data/reference/stock_industry_map.csv --end-date 2026-09-01 --output artifacts/backtest/r13-r1-20260901-f7f9d46/inputs/artifacts/market_regime_history_2026-09-01.json
.venv/bin/python -m app.research.ranking_provenance_receipt --project-root . --verify-complete-bundle artifacts/backtest/r13-r1-20260901-f7f9d46/output/.ranking-provenance-v1/runs/r13-r1-20260901-f7f9d46/COMPLETE.manifest.json
du -sk artifacts/backtest/r13-r1-20260901-f7f9d46
git diff --check
```

Verifier result：

```json
{"errors": ["manifest_unreadable"], "status": "INVALID"}
```

## Acceptance mapping

| Acceptance item | Status |
| --- | --- |
| fixed SHA | PASS |
| source clean before run | PASS |
| copied inputs, no symlink/hardlink | PASS |
| copied input hashes match main checkout and main hashes unchanged after | PASS |
| fresh features/universe date `2026-09-01` | PASS |
| fresh `market-regime-history.v2` to `2026-09-01` | PASS |
| `as_of_date == trade_date` | PASS |
| completed-date authority path/hash validated | PASS |
| one true `FORWARD_CAPTURE` attempt only | PASS |
| COMPLETE manifest | FAIL：not created due runtime failure |
| `verify_complete_bundle` | FAIL_CLOSED：`manifest_unreadable` |
| receipt binding | NOT_EMITTED：runtime failed before receipt creation |
| admission eligibility | NOT_EMITTED；no receipt, no admission |
| historical corpus | PASS：unchanged and remains `NON_ADMISSION` |
| output size <= 256 MiB | PASS |
| changed-files allowlist | PASS pending final status：task card + this evidence only |

## Remaining risk

- The completed-date authority repair works for this local status artifact, and freshness gates now pass.
- The actual forward capture remains blocked by a model/features contract mismatch: the daily 2026-09-01 inference frame does not contain the M4 `event_*` columns required by `models/latest_lgbm.pkl`.
- Because no ranking, receipt or COMPLETE manifest was emitted, this run does not prove R13 success and does not admit R14, Entry-Regime capacity, preregistration, historical corpus, B0 Phase 2, B1, C1 or production.
- The ignored session artifacts are intentionally left under `artifacts/backtest/r13-r1-20260901-f7f9d46/` for local audit; they are not part of the commit.

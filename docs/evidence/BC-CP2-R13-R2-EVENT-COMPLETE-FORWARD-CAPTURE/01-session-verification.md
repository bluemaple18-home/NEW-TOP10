# BC-CP2 R13-R2 event-complete forward-capture verification

## Receipt

- Task：`BC-CP2-R13-R2-EVENT-COMPLETE-FORWARD-CAPTURE`
- Fixed HEAD：`af9c32bdd63d86918fbd9d57c4f909beaa03f936`
- Worktree：`/private/tmp/top10new-r13-trusted-date-authority-20260902`
- Task card：`docs/tasks/2026-09-02_RUN-NEW-TOP10-BC-CP2-R13-R2-EVENT-COMPLETE-FORWARD-CAPTURE.md`
- R13-R1 task：`docs/tasks/2026-09-02_RUN-NEW-TOP10-BC-CP2-R13-R1-FORWARD-CAPTURE-RETRY.md`
- R13-R1 evidence：`docs/evidence/BC-CP2-R13-R1-FORWARD-CAPTURE-RETRY/01-session-verification.md`
- Authority repair evidence：`docs/evidence/REPAIR-NEW-TOP10-R13-TRUSTED-COMPLETED-TRADE-DATE-AUTHORITY/verification.md`
- Run identity：`r13-r2-20260901-af9c32b`
- Capture date：`2026-09-01`
- Capture mode：`FORWARD_CAPTURE`
- Verdict：`GO_FORWARD_CAPTURE_SESSION_VERIFIED`
- Capture attempt count：`1`
- COMPLETE bundle：`CREATED`
- Bundle verification：`OK`
- Outcome-free：`YES`
- Scope guard：未修改 source、config、model、正式 data/ranking、主 checkout；未 network fetch；未讀 outcome/sealed data；未 replay/benchmark/training；未 push/merge/deploy/production/external write。

## Source decision

CodeGraph gate：

- `codegraph_context(projectPath="/private/tmp/top10new-r13-trusted-date-authority-20260902")`
- Result：`CodeGraph not initialized`
- Fallback：用主 checkout CodeGraph 做只讀定位；實際執行與寫入限定在本 worktree。
- Relevant seams inspected：`scripts/research_regime_shadow_ranking.py`、`scripts/build_market_regime_history.py`、`app/agent_b_ranking.py`、`app/agent_b_modeling.py`、`app/modeling/feature_contract.py`、`app/research/ranking_provenance_receipt.py`。

## Preflight gates

| Gate | Evidence | Result |
| --- | --- | --- |
| Fixed HEAD | `git rev-parse HEAD` returned `af9c32bdd63d86918fbd9d57c4f909beaa03f936` | PASS |
| Main checkout read-only | Source hashes before and after capture are unchanged; main checkout had unrelated untracked docs and was not modified | PASS |
| Run identity uniqueness | `test -e artifacts/backtest/r13-r2-20260901-af9c32b` exited `1` before session creation | PASS |
| Copy, not link | copied inputs have matching byte size/hash, different inode, file type `Regular File` | PASS |
| Features freshness | copied `features.parquet` max date `2026-09-01`, rows `516169`, target rows `1930`, target unique stocks `1930` | PASS |
| Events freshness | copied `events.parquet` max date `2026-09-01`, rows `516169`, target rows `1930`, target unique stocks `1930` | PASS |
| Universe freshness | copied `universe.parquet` max date `2026-09-01`, rows `274016`, target rows `1019`, target unique stocks `1019` | PASS |
| Calendar schedule source | copied `ranking_2026-09-01.csv` has `10` rows and `10` unique stock IDs; used only as `dates-from-dir` schedule source | PASS |
| Completed-date authority | validator accepted staged `automation_status_2026-09-01.json`; trusted date `2026-09-01`; hash `sha256:0211252a3aa28676a42f9ecdf7c03b675a56ad215d98b240c381d8e5540b6400` | PASS |
| Fresh regime history | canonical builder output schema `market-regime-history.v2`, rows `282`, max trade date `2026-09-01`, `as_of_date == trade_date` violations `0`, latest label `RISK_OFF` | PASS |
| M4 required features | `StockRanker.load_daily_data("2026-09-01")` on staged `features + events` produced daily rows `1019`; model required features `86`; missing count `0`; event missing count `0`; event column count `13` | PASS |
| Session size | `du -sk artifacts/backtest/r13-r2-20260901-af9c32b` after capture returned `188636` KiB | PASS |

## Input hashes

| Input | Main checkout sha256 | Copied sha256 |
| --- | --- | --- |
| `data/clean/features.parquet` | `aab60603280ae3d2a603b705ab02c5b19f518dcf178080482b2500b221f954ce` | `aab60603280ae3d2a603b705ab02c5b19f518dcf178080482b2500b221f954ce` |
| `data/clean/events.parquet` | `7a6f85beff13bc82ed1ce9d29fe81ab916f841118b69b981042d663fec800e34` | `7a6f85beff13bc82ed1ce9d29fe81ab916f841118b69b981042d663fec800e34` |
| `data/clean/universe.parquet` | `f658800012a8f8072e62aad053fe984b9c2a5d70c370b00b6f74c795fc81c109` | `f658800012a8f8072e62aad053fe984b9c2a5d70c370b00b6f74c795fc81c109` |
| `artifacts/ranking_2026-09-01.csv` | `cd917dcc36f6c56d9989faaadc95f30120023bad89753780631d91feb9d94171` | `cd917dcc36f6c56d9989faaadc95f30120023bad89753780631d91feb9d94171` |
| `artifacts/automation_status_2026-09-01.json` | `0211252a3aa28676a42f9ecdf7c03b675a56ad215d98b240c381d8e5540b6400` | `0211252a3aa28676a42f9ecdf7c03b675a56ad215d98b240c381d8e5540b6400` |
| `models/latest_lgbm.pkl` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` |
| `config/signals.yaml` | `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a` | `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a` |
| `data/reference/stock_industry_map.csv` | `86ca58072c0db0581df741e212b0bccc641848638b52b4ae1e3b1a0b4e96cb20` | `86ca58072c0db0581df741e212b0bccc641848638b52b4ae1e3b1a0b4e96cb20` |

Generated isolated regime history：

- Path：`artifacts/backtest/r13-r2-20260901-af9c32b/inputs/artifacts/market_regime_history_2026-09-01.json`
- sha256：`d1992844aae6c0cd5ae6c58fd8bf0882935f87de2114f69f11874ce42f4cee01`
- markdown sidecar：`artifacts/backtest/r13-r2-20260901-af9c32b/inputs/artifacts/market_regime_history_2026-09-01.md`
- latest：`2026-09-01 / RISK_OFF`

## Capture attempt

Command：

```bash
.venv/bin/python scripts/research_regime_shadow_ranking.py --dates-from-dir artifacts/backtest/r13-r2-20260901-af9c32b/inputs/artifacts/calendar --output-dir artifacts/backtest/r13-r2-20260901-af9c32b/output --market-regime-history artifacts/backtest/r13-r2-20260901-af9c32b/inputs/artifacts/market_regime_history_2026-09-01.json --industry-map artifacts/backtest/r13-r2-20260901-af9c32b/inputs/data/reference/stock_industry_map.csv --data-dir artifacts/backtest/r13-r2-20260901-af9c32b/inputs/data/clean --model-dir artifacts/backtest/r13-r2-20260901-af9c32b/inputs/models --config artifacts/backtest/r13-r2-20260901-af9c32b/inputs/config/signals.yaml --forward-capture --capture-trade-date 2026-09-01 --capture-authority-artifact artifacts/backtest/r13-r2-20260901-af9c32b/inputs/artifacts/authority/automation_status_2026-09-01.json --run-identity r13-r2-20260901-af9c32b
```

Result：

- Exit：`0`
- Capture verdict：`GO_FORWARD_CAPTURE_SESSION_VERIFIED`
- Runtime output：`REGIME_SHADOW_RANKING RISK_OFF 2026-09-01 .../ranking_2026-09-01.csv`
- Summary output：`{"status": "OK", "ranking_count": 1}`

This is the single allowed true `FORWARD_CAPTURE` attempt for this card. No second capture attempt was run.

## Bundle and artifacts

| Artifact | Path | Status | Hash |
| --- | --- | --- | --- |
| Ranking output | `artifacts/backtest/r13-r2-20260901-af9c32b/output/ranking_2026-09-01.csv` | `CREATED` | `d17cf9202b83f626023a8ee18aff423b1508540e6c54f294c7253021350046b2` |
| Summary output | `artifacts/backtest/r13-r2-20260901-af9c32b/output/regime_shadow_ranking.json` | `CREATED` | `ea8e61bd2bd89c6574b829ecfe143981102844ae30c8ea95313e105857104769` |
| COMPLETE manifest | `artifacts/backtest/r13-r2-20260901-af9c32b/output/.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b/COMPLETE.manifest.json` | `CREATED` | `144777c9ea1aa8dcd944917820640a77866e3e4280549854549a98e3b90189c9` |
| Receipt | `artifacts/backtest/r13-r2-20260901-af9c32b/output/.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b/receipts/ranking_2026-09-01.receipt.json` | `CREATED` | `dff85cb7028f3a664a5d96a0884f4f7e6d334c29ef2f8c23bd85e42cdcbc76ee` |
| Model snapshot | `artifacts/backtest/r13-r2-20260901-af9c32b/output/.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b/model_snapshots/model-ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d.pkl` | `CREATED` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` |

Verifier result：

```json
{"errors": [], "status": "OK"}
```

Manifest facts：

- `schema_version=ranking-provenance-batch-manifest.v1`
- `status=COMPLETE`
- `capture_mode=FORWARD_CAPTURE`
- `run_identity=r13-r2-20260901-af9c32b`
- `planned_rankings=["ranking_2026-09-01.csv"]`
- `entries[0].ranking_date=2026-09-01`
- `input_hashes_before == input_hashes_after` for features, universe, model, config, market regime history, industry map, calendar schedule and completed-date authority.

Receipt facts：

- `capture_mode=FORWARD_CAPTURE`
- `admission_eligible=pending_registration`
- `ranking_date=2026-09-01`
- `run_identity=r13-r2-20260901-af9c32b`
- `feature_calendar.sha256=sha256:aab60603280ae3d2a603b705ab02c5b19f518dcf178080482b2500b221f954ce`
- `model.sha256=sha256:ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`
- `config.sha256=sha256:b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a`
- `universe.sha256=sha256:f658800012a8f8072e62aad053fe984b9c2a5d70c370b00b6f74c795fc81c109`
- `strict_inputs.completed_trade_date_authority.sha256=sha256:0211252a3aa28676a42f9ecdf7c03b675a56ad215d98b240c381d8e5540b6400`
- `strict_inputs.market_regime_history.sha256=sha256:d1992844aae6c0cd5ae6c58fd8bf0882935f87de2114f69f11874ce42f4cee01`
- `strict_inputs.industry_map.sha256=sha256:86ca58072c0db0581df741e212b0bccc641848638b52b4ae1e3b1a0b4e96cb20`
- `strict_inputs.calendar_schedule_source.sha256=sha256:cd917dcc36f6c56d9989faaadc95f30120023bad89753780631d91feb9d94171`

Ranking output facts：

- rows：`10`
- unique stocks：`10`
- rank range：`1..10`
- score column：`shadow_score`

## Verification commands

```bash
git rev-parse HEAD
git -C /Users/mattkuo/TOP10new status --short
shasum -a 256 /Users/mattkuo/TOP10new/data/clean/features.parquet /Users/mattkuo/TOP10new/data/clean/events.parquet /Users/mattkuo/TOP10new/data/clean/universe.parquet /Users/mattkuo/TOP10new/artifacts/ranking_2026-09-01.csv /Users/mattkuo/TOP10new/artifacts/automation_status_2026-09-01.json /Users/mattkuo/TOP10new/models/latest_lgbm.pkl /Users/mattkuo/TOP10new/config/signals.yaml /Users/mattkuo/TOP10new/data/reference/stock_industry_map.csv
stat -f '%N %i %z %HT' /Users/mattkuo/TOP10new/data/clean/features.parquet /Users/mattkuo/TOP10new/data/clean/events.parquet /Users/mattkuo/TOP10new/data/clean/universe.parquet /Users/mattkuo/TOP10new/artifacts/ranking_2026-09-01.csv /Users/mattkuo/TOP10new/artifacts/automation_status_2026-09-01.json artifacts/backtest/r13-r2-20260901-af9c32b/inputs/data/clean/features.parquet artifacts/backtest/r13-r2-20260901-af9c32b/inputs/data/clean/events.parquet artifacts/backtest/r13-r2-20260901-af9c32b/inputs/data/clean/universe.parquet artifacts/backtest/r13-r2-20260901-af9c32b/inputs/artifacts/calendar/ranking_2026-09-01.csv artifacts/backtest/r13-r2-20260901-af9c32b/inputs/artifacts/authority/automation_status_2026-09-01.json
.venv/bin/python scripts/build_market_regime_history.py --features artifacts/backtest/r13-r2-20260901-af9c32b/inputs/data/clean/features.parquet --industry-map artifacts/backtest/r13-r2-20260901-af9c32b/inputs/data/reference/stock_industry_map.csv --end-date 2026-09-01 --output artifacts/backtest/r13-r2-20260901-af9c32b/inputs/artifacts/market_regime_history_2026-09-01.json
.venv/bin/python -c "<StockRanker staged load_daily_data and model feature missing count>"
.venv/bin/python scripts/research_regime_shadow_ranking.py --dates-from-dir artifacts/backtest/r13-r2-20260901-af9c32b/inputs/artifacts/calendar --output-dir artifacts/backtest/r13-r2-20260901-af9c32b/output --market-regime-history artifacts/backtest/r13-r2-20260901-af9c32b/inputs/artifacts/market_regime_history_2026-09-01.json --industry-map artifacts/backtest/r13-r2-20260901-af9c32b/inputs/data/reference/stock_industry_map.csv --data-dir artifacts/backtest/r13-r2-20260901-af9c32b/inputs/data/clean --model-dir artifacts/backtest/r13-r2-20260901-af9c32b/inputs/models --config artifacts/backtest/r13-r2-20260901-af9c32b/inputs/config/signals.yaml --forward-capture --capture-trade-date 2026-09-01 --capture-authority-artifact artifacts/backtest/r13-r2-20260901-af9c32b/inputs/artifacts/authority/automation_status_2026-09-01.json --run-identity r13-r2-20260901-af9c32b
.venv/bin/python -m app.research.ranking_provenance_receipt --project-root . --verify-complete-bundle artifacts/backtest/r13-r2-20260901-af9c32b/output/.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b/COMPLETE.manifest.json
du -sk artifacts/backtest/r13-r2-20260901-af9c32b
git diff --check
```

## Acceptance mapping

| Acceptance item | Status |
| --- | --- |
| Fixed HEAD | PASS |
| Main checkout read-only | PASS |
| Copy, not symlink/hardlink | PASS |
| features/events/universe max date all `2026-09-01` | PASS |
| copy hashes match source hashes | PASS |
| source hashes unchanged after capture | PASS |
| fresh regime history rebuilt to `2026-09-01` | PASS |
| schema/as-of gates | PASS |
| M4 required features missing count `0` before capture | PASS |
| single run identity | PASS：`r13-r2-20260901-af9c32b` |
| one true `FORWARD_CAPTURE` attempt only | PASS |
| capture exit | PASS：`0` |
| COMPLETE manifest | PASS：created, status `COMPLETE` |
| `verify_complete_bundle` | PASS：`OK` |
| receipt/manifest binding | PASS：ranking/model/config/universe/features/regime history/industry map/calendar schedule/completed-date authority/producer/run identity recorded |
| events evidence | PASS：fresh staged hash/date recorded and M4 event columns present |
| admission eligibility | PASS：receipt `pending_registration` |
| historical corpus | PASS：unchanged; this isolated forward capture does not admit historical corpus |
| session output <= 256 MiB | PASS：`188636` KiB |
| changed-files allowlist | PASS pending final commit：task card + this evidence only |

## Remaining risk

- This proves one isolated event-complete R13-R2 forward capture session at fixed HEAD.
- It does not admit R14, Entry-Regime capacity, preregistration, historical corpus, B0 Phase 2, B1, C1 or production.
- Session artifacts are intentionally left under ignored `artifacts/backtest/r13-r2-20260901-af9c32b/` for local audit and are not part of the commit.

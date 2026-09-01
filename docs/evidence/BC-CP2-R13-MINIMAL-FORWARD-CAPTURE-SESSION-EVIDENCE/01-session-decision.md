# BC-CP2 R13 最小 Forward-Capture Session Evidence

## Receipt

- 任務：`BC-CP2-R13-MINIMAL-FORWARD-CAPTURE-SESSION-EVIDENCE`
- 固定 parent：`0354183baf227d40f6aeb314a2571ca2d6b614ea`
- 任務卡：`docs/tasks/2026-09-01_RUN-NEW-TOP10-BC-CP2-R13-MINIMAL-FORWARD-CAPTURE-SESSION-EVIDENCE.md`
- 任務卡 sha256：`938450b6cae5b8911a3bfeec95257e5c099fc046c5adcce268d5fcd171471677`
- R12 evidence：`docs/evidence/BC-CP2-R12-RANKING-PROVENANCE-AUTHORITY-DECISION/01-forward-capture-or-defer.md`
- R12 evidence sha256：`b960a16847537a38abd49aa26fdd10c33e6ff8320be87e66afd508f51087c3ea`
- Verdict：`BLOCKED_FRESH_INPUT_OR_TRUSTED_DATE_AUTHORITY`
- Capture：`NOT_RUN`
- Bundle：`NOT_RUN`
- Bundle verification：`NOT_RUN`
- Outcome-free：`YES`
- 交付限制：只新增本檔；未修改 code、tests、config、workflow、data、ranking、manifest、receipt、registry、runner、queue、scheduler、backtest 或 production。
- 執行限制：未 network fetch、未產生 ranking、未執行 capture、replay、benchmark、training、outcome 或 sealed access；未准入 R14、Entry-Regime capacity、preregistration 或 production；未 merge、push、改 Issue、deploy 或 external write。

## Source Decision

CodeGraph 在本 worktree 回報未初始化，因此 source decision 降級為限域唯讀檢查：

- R13 task card 與 R12 evidence。
- Existing CLI seam：`scripts/build_historical_ranking_replay_set.py`、`scripts/research_regime_shadow_ranking.py`、`app/research/ranking_provenance_receipt.py`。
- Canonical configured checkout：任務卡允許唯讀；本 evidence 以 `<canonical-configured-checkout>` 表示其本機根目錄。
- Temp session root：任務卡指定 isolated temp；本 evidence 以 `<tmp>/top10-r13-forward-capture-session` 表示。

## Gate Results

| Gate | Requirement | Evidence | Result |
| --- | --- | --- | --- |
| G0 fixed parent | `HEAD == 0354183baf227d40f6aeb314a2571ca2d6b614ea` | `git rev-parse HEAD` returned `0354183baf227d40f6aeb314a2571ca2d6b614ea`; worktree preflight clean | PASS |
| G1 session clock | Session clock must be Asia/Taipei and date must be `2026-09-01` | `date '+%Y-%m-%d %H:%M:%S %Z %z'` returned `2026-09-01 22:23:47 CST +0800` | PASS |
| G2 producer command seam | Existing CLI must expose single-date `FORWARD_CAPTURE` gate and verifier seam | `rg -n -- "...FORWARD_CAPTURE..."` found `--forward-capture`、`--capture-trade-date`、`--run-identity` in both producers, `ensure_capture_mode` and `verify_complete_bundle` in receipt seam | PASS |
| G3 canonical checkout identity | Canonical configured checkout must be readable and pinned | `git -C <canonical-configured-checkout> rev-parse HEAD` returned `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`; checkout has untracked task-card files, treated as read-only projection noise | PASS_WITH_CAVEAT |
| G4 configured input hashes | Local inputs must match R11/R12 fixed current hashes | Hashes matched: history `4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70`; features `93e8432987b6037db243b2864f7bc8d09f12acd50249d9238d2acddacd2561d2`; universe `ba9c69dc5270bf53968e39a51c93e6e80421d7545c83b29df5a95a693aede85a`; model `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`; config `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a`; shadow config `6b1ab4d074c4d9ddd8ab8e62dd26ab79c078bb05f7323aeb75d616cc07b7116d` | PASS |
| G5 local input freshness | Features, universe, regime history and session date must jointly prove one fresh completed trade date | `features_date_max=2026-08-31`; `universe_date_max=2026-08-31`; `history_date_max=2026-05-29`; session date is `2026-09-01` | FAIL |
| G6 trusted completed trade date authority | Trusted completed trade date must be provable without network or historical substitution | No local source proves `2026-09-01` as completed market trade date with fresh inputs; latest local feature/universe date is `2026-08-31`, and regime history is older | FAIL |
| G7 temp root preflight | Isolated temp root must be available before capture | `test -e <tmp>/top10-r13-forward-capture-session` exit `1`; `du -sk <tmp>/top10-r13-forward-capture-session` exit `1`, `No such file or directory` | PASS：not pre-existing |
| G8 capture command | Only allowed after G1-G7 required freshness/date gates PASS | G5/G6 failed | NOT_RUN |
| G9 bundle create | Only allowed after capture PASS | Capture `NOT_RUN` | NOT_RUN |
| G10 bundle verify | Only allowed after bundle create PASS | Bundle `NOT_RUN` | NOT_RUN |
| G11 temp size | Temporary output must stay <= `256 MiB` | Temp session root was not created; effective session output size `0 KiB` / `NOT_CREATED` | PASS |
| G12 outcome-free guard | No outcome, replay, benchmark, training or sealed access | No such command was run | PASS |

## Decision

`BLOCKED_FRESH_INPUT_OR_TRUSTED_DATE_AUTHORITY`

Rationale：

1. Session clock is `2026-09-01 22:23:47 CST +0800`, so the clock gate itself passes.
2. Existing CLI/static seam is present and forward-only gates exist, but R13 success requires fresh local inputs and a trusted completed trade date before any capture.
3. Canonical configured input hashes match the R11/R12 fixed current hashes, but freshness does not: features and universe end at `2026-08-31`, while regime history ends at `2026-05-29`.
4. Because local inputs cannot jointly prove `2026-09-01` as the same fresh completed trade date, using `2026-08-31`, historical corpus, old manifest, fog root or `REPLAY_GENERATED` would violate the R13 fail-closed contract.
5. Therefore capture, bundle creation and bundle verification remain `NOT_RUN`; no temp session bundle exists.

## Commands / Exit / Hash / Temp Size

| Command | Exit | Evidence |
| --- | ---: | --- |
| `git rev-parse HEAD` | 0 | `0354183baf227d40f6aeb314a2571ca2d6b614ea` |
| `git status --short` | 0 | clean in R13 worktree before evidence write |
| `date '+%Y-%m-%d %H:%M:%S %Z %z'` | 0 | `2026-09-01 22:23:47 CST +0800` |
| `git -C <canonical-configured-checkout> rev-parse HEAD` | 0 | `35bb9927eb0eac9a624dcaf0dcffcbf88857c070` |
| `git -C <canonical-configured-checkout> status --short` | 0 | untracked task-card files only; used as read-only caveat |
| `shasum -a 256 <canonical-configured-checkout>/artifacts/market_regime_history_2026-05-29.json <canonical-configured-checkout>/data/clean/features.parquet <canonical-configured-checkout>/data/clean/universe.parquet <canonical-configured-checkout>/models/latest_lgbm.pkl <canonical-configured-checkout>/config/signals.yaml <canonical-configured-checkout>/config/research_shadow_runs.yaml` | 0 | hashes listed in G4 |
| `<project-python> -c "<read parquet/json max dates>"` | 0 | warnings from pyarrow `sysctlbyname` only; rows completed; features max `2026-08-31`, universe max `2026-08-31`, history max `2026-05-29` |
| `find <canonical-configured-checkout>/artifacts/backtest/historical_rankings_current_model -maxdepth 1 -type f -name 'ranking_*.csv' \| wc -l` | 0 | `25` |
| `find <canonical-configured-checkout>/artifacts/backtest/historical_rankings_current_model -maxdepth 4 -type f \( -name 'ranking_*.receipt.json' -o -name 'COMPLETE.manifest.json' -o -name '*provenance*.json' -o -name '*receipt*' -o -name '*manifest*' \) \| wc -l` | 0 | `0` |
| `test -e <tmp>/top10-r13-forward-capture-session` | 1 | temp session root not pre-existing |
| `du -sk <tmp>/top10-r13-forward-capture-session` | 1 | temp session root not created; effective size `0 KiB` |
| initial `rg -n "...--forward-capture..." ...` | 2 | failed because pattern beginning with `--` was parsed as option; no decision taken from this failed command |
| corrected `rg -n -- "...--forward-capture..." ...` | 0 | producer/receipt seam evidence in G2 |

## Output Artifacts

| Artifact | Status | Hash / Size |
| --- | --- | --- |
| Capture ranking | `NOT_RUN` | none |
| Receipt | `NOT_RUN` | none |
| COMPLETE manifest | `NOT_RUN` | none |
| Bundle verification result | `NOT_RUN` | none |
| Temp session root | `NOT_CREATED` | effective size `0 KiB`; task limit `256 MiB` |

## Reproducible Commands

```bash
git rev-parse HEAD
git status --short
date '+%Y-%m-%d %H:%M:%S %Z %z'
sed -n '1,260p' docs/tasks/2026-09-01_RUN-NEW-TOP10-BC-CP2-R13-MINIMAL-FORWARD-CAPTURE-SESSION-EVIDENCE.md
shasum -a 256 docs/tasks/2026-09-01_RUN-NEW-TOP10-BC-CP2-R13-MINIMAL-FORWARD-CAPTURE-SESSION-EVIDENCE.md docs/evidence/BC-CP2-R12-RANKING-PROVENANCE-AUTHORITY-DECISION/01-forward-capture-or-defer.md
rg -n -- "--forward-capture|--capture-trade-date|--run-identity|FORWARD_CAPTURE|REPLAY_GENERATED|ensure_capture_mode|verify_complete_bundle" scripts/build_historical_ranking_replay_set.py scripts/research_regime_shadow_ranking.py app/research/ranking_provenance_receipt.py
git -C <canonical-configured-checkout> rev-parse HEAD
git -C <canonical-configured-checkout> status --short
shasum -a 256 <canonical-configured-checkout>/artifacts/market_regime_history_2026-05-29.json <canonical-configured-checkout>/data/clean/features.parquet <canonical-configured-checkout>/data/clean/universe.parquet <canonical-configured-checkout>/models/latest_lgbm.pkl <canonical-configured-checkout>/config/signals.yaml <canonical-configured-checkout>/config/research_shadow_runs.yaml
wc -c <canonical-configured-checkout>/artifacts/market_regime_history_2026-05-29.json <canonical-configured-checkout>/data/clean/features.parquet <canonical-configured-checkout>/data/clean/universe.parquet <canonical-configured-checkout>/models/latest_lgbm.pkl <canonical-configured-checkout>/config/signals.yaml
<project-python> -c "<read features/universe parquet max dates and regime history max date>"
find <canonical-configured-checkout>/artifacts/backtest/historical_rankings_current_model -maxdepth 1 -type f -name 'ranking_*.csv' | wc -l
find <canonical-configured-checkout>/artifacts/backtest/historical_rankings_current_model -maxdepth 4 -type f \( -name 'ranking_*.receipt.json' -o -name 'COMPLETE.manifest.json' -o -name '*provenance*.json' -o -name '*receipt*' -o -name '*manifest*' \) | wc -l
test -e <tmp>/top10-r13-forward-capture-session
du -sk <tmp>/top10-r13-forward-capture-session
```

CodeGraph source-decision command：

```text
codegraph_status(projectPath=".") -> CodeGraph not initialized
```

## Absorption Boundary

Why not less：

- 必須同時驗 session clock、fresh input hashes/date maxima、trusted completed date authority 與 CLI seam；只看 R12 static seam 會漏掉 R13 的 runtime前置 freshness gate。
- 必須記錄 failed command 與 corrected command，避免把搜尋錯誤沉默吞掉。
- 必須把 capture/bundle/verify 全部列為 `NOT_RUN`，才能證明 fail-closed。

Why not more：

- G5/G6 已 fail；不得用歷史日期、舊 ranking、fog root、old manifest 或 `REPLAY_GENERATED` 硬跑 forward capture。
- 不應建立 temp bundle、receipt、manifest 或 ranking，因為 trusted completed date 與 fresh local inputs 未共同成立。
- R13 不是 data refresh、market calendar authority、ranking provenance implementation、R14 admission 或 production work。

Do not absorb：

- 不吸收 network fetch、data refresh、capture execution、ranking generation、receipt/manifest write、bundle verification 或 registration。
- 不吸收 outcome、return、PnL、win rate、Sharpe、alpha、target、promotion score、sealed outcome、replay、benchmark 或 training。
- 不吸收 historical corpus admission、fog root promotion、old manifest promotion、`REPLAY_GENERATED` exception、Entry-Regime capacity/split feasibility、R14、Phase 2、B1、C1 或 production。

## Temporary Cleanup

- Temporary root：`<tmp>/top10-r13-forward-capture-session`
- Pre-existing：`NO`
- Created：`NO`
- Cleanup required：`NO`
- Effective temp size：`0 KiB`

## Acceptance Mapping

| Acceptance item | Status |
| --- | --- |
| 只新增指定 evidence | PASS |
| 三選一 verdict | PASS：`BLOCKED_FRESH_INPUT_OR_TRUSTED_DATE_AUTHORITY` |
| 逐 gate PASS／FAIL／NOT_RUN | PASS |
| 命令／exit／hash／temp size | PASS |
| Capture/bundle/verify after failed freshness gate | PASS：all `NOT_RUN` |
| `git diff --check` | PASS：evidence write 後 pre-commit diff check exit `0`；post-commit diff check 由 final verification 固定 |
| Clean worktree | PASS：preflight clean；post-commit clean 由 final verification 固定 |
| 獨立 fixed-SHA Review 無 P0/P1 | NOT_RUN_BY_WORKER；留待 Mainline／Reviewer 驗收 |

## Unique Frontier

唯一 frontier：`TRUSTED_COMPLETED_TRADE_DATE_AND_FRESH_INPUT_AUTHORITY`

停止點：在 local features、universe、regime history 與 trusted completed trade date 能共同證明同一 fresh completed date 前，不得重跑 R13 capture，不得進入 R14、Entry-Regime capacity、preregistration 或 production。

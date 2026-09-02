# BC-CP2 R11 Entry-Regime Cohort Current-Baseline Feasibility

## Receipt

- 任務：`BC-CP2-R11-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY`
- 固定 repair parent：`24ab9703419c85b5e561c78fcbf5c0c4bb7472b3`
- 任務卡：`docs/tasks/2026-09-01_RESEARCH-NEW-TOP10-BC-CP2-R11-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY.md`
- 任務卡 sha256：`ef5992462779e461f7f894b3bb52cfbdcb8f8f8f46d95b12648aad382722d05e`
- Repair task card：`docs/tasks/2026-09-01_REPAIR-NEW-TOP10-BC-CP2-R11-R1-CONFIGURED-ROOT-EVIDENCE.md`
- Repair task card sha256：`7eedec6ae37f13a5a9c741f2db3642e715f111b3a9d13aa1d26d75180b306ccf`
- Contract：`docs/tasks/2026-09-01_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY-V2.md`
- Contract sha256：`94734b38961ed5a2cae8bad83705de6b94cb2d256e3ce9daee38a1442ea79ab5`
- Verdict：`BLOCKED_RANKING_PROVENANCE_AUTHORITY`
- Outcome-free：`YES`
- Capacity/split inventory：`NOT_RUN`
- 交付限制：只修改指定 evidence 檔；未修改其他 docs/evidence、code、tests、config、data、history、features、ranking、taxonomy、split、episode、horizon、workflow、runner、queue、scheduler、backtest 或 production。
- 執行限制：未產生 ranking、未執行 replay／benchmark／training、未讀取或衍生 return、PnL、win rate、Sharpe、alpha、target、promotion score 或 sealed outcome；未准入 preregistration、R12、Phase 2、B1、C1 或 production；未 merge、push、改 Issue、deploy 或 external write。

## Source Decision

CodeGraph 在 repair worktree 回報未初始化，因此 source decision 降級為限域唯讀證據對帳。R11 candidate 的 isolated Git projection 只代表 committed source/docs state；ignored artifacts 必須以 canonical configured checkout 作 configured artifact authority，不能用 isolated projection 的 missing files 判定 configured corpus absent：

- V2 contract：`docs/tasks/2026-09-01_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY-V2.md`
- R11 task card：`docs/tasks/2026-09-01_RESEARCH-NEW-TOP10-BC-CP2-R11-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY.md`
- R11 repair card：`docs/tasks/2026-09-01_REPAIR-NEW-TOP10-BC-CP2-R11-R1-CONFIGURED-ROOT-EVIDENCE.md`
- Runtime config：`config/research_shadow_runs.yaml`
- Configured model/config refs：`models/latest_lgbm.pkl`、`config/signals.yaml`
- Configured ranking root path：`artifacts/backtest/historical_rankings_current_model`
- Canonical configured checkout inventory：`artifacts/market_regime_history_2026-05-29.json`、`data/clean/features.parquet`、`data/clean/universe.parquet`、`artifacts/backtest/historical_rankings_current_model`
- Isolated repair projection inventory：`artifacts/backtest/historical_rankings_current_model` absent；此事只證明 ignored artifact 未投影，不是 configured root 缺失。
- Repository path inventory for ranking provenance receipt code/tests only。

本卡不宣稱 runtime replay evidence，也不使用 old manifest、fog root、historical rebuild、`REPLAY_GENERATED` 或 filename coverage 補 provenance。

## Fixed Authority Refs

| Authority | SHA / Hash | Status |
| --- | --- | --- |
| R11 repair fixed parent | `24ab9703419c85b5e561c78fcbf5c0c4bb7472b3` | PASS |
| R11 original candidate | commit `61ca8314f4b065edaaed7712f26483ff3f68c056` | PASS |
| R10 V2 contract | commit `e4c6690c6720406cb287ef19bcc000d7352a1f77`; sha256 `94734b38961ed5a2cae8bad83705de6b94cb2d256e3ce9daee38a1442ea79ab5` | PASS |
| R9 current-baseline reconciliation | commit `ba2c5310ae4a8e89ec81e8ec347433123dbcbb49`; evidence sha256 `37b2e0a92fbca1464c5293ca7f76408a0dae3108f39deecd38a9a110f585e2a6` | PASS |
| R8 exact-holding successor decision | commit `27327b670142e22c4c4cdd5bda7cae03ac2eb1e4`; task sha256 `69fca1c1cfc311f7111f7cba3cb3c455587696d9711c7783172ccf41e20e84bb` | PASS |
| R7 identity/episode authority | commit `e1a30830d0ab2ee24af0f81d703cbf350be4819e`; evidence sha256 `d2ecacfe8e762fa939704649f6461bb4be4db39ddb935a01cdd5969083219574` | PASS |
| R6 configured ranking source authority | commit `b7ba1fc6065d6221353f7362db92ac7638bb8017`; evidence sha256 `d4492b7711ee8a532a5a1b1b9e232dd285b030c22d7931cc2b13f0f52788bf98` | PASS |
| Canonical backlog | `docs/RESEARCH_SPINE_BACKLOG.md`; sha256 `5065a341c3a050c78a6d94a341c8f47664dec36c201a2c2943489b8c8d5d5dc8` | PASS |

## Gate Results

| Gate | Requirement | Evidence | Result |
| --- | --- | --- | --- |
| G0 fixed parent | `HEAD == 24ab9703419c85b5e561c78fcbf5c0c4bb7472b3` before evidence repair write | `git rev-parse HEAD` returned `24ab9703419c85b5e561c78fcbf5c0c4bb7472b3`; repair worktree preflight clean | PASS |
| G1.1 model bytes | Current configured model bytes must match V2 authority | `models/latest_lgbm.pkl` sha256 `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` | PASS |
| G1.2 config bytes | Current configured signal config bytes must match V2 authority | `config/signals.yaml` sha256 `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a` | PASS |
| G1.3 top-N | Current config must bind top-N | `config/research_shadow_runs.yaml` has `top_n: 10`; file sha256 `6b1ab4d074c4d9ddd8ab8e62dd26ab79c078bb05f7323aeb75d616cc07b7116d` | PASS |
| G1.4 market regime history bytes | Current configured history bytes must be present and match V2 authority | Canonical configured checkout has `artifacts/market_regime_history_2026-05-29.json`; sha256 `4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70`; bytes `216519` | PASS |
| G1.5 features bytes | Current configured features bytes must be present and match V2 authority | Canonical configured checkout has `data/clean/features.parquet`; sha256 `93e8432987b6037db243b2864f7bc8d09f12acd50249d9238d2acddacd2561d2`; bytes `137774296` | PASS |
| G1.6 universe bytes | Current configured universe bytes must be present and match V2 authority | Canonical configured checkout has `data/clean/universe.parquet`; sha256 `ba9c69dc5270bf53968e39a51c93e6e80421d7545c83b29df5a95a693aede85a`; bytes `81005591` | PASS |
| G1.7 configured ranking root | Configured ranking corpus must exist at current configured root | Canonical configured checkout has `artifacts/backtest/historical_rankings_current_model`; inventory is `25` `ranking_*.csv` files and `28` total files: `analysis_report.md`, `analysis_report.yaml`, `ranked_stocks_detailed.csv`, plus dated ranking CSVs from `2026-04-08` through `2026-05-13`; receipt/provenance/manifest name inventory under this root returned no files | PASS |
| G1.8 per-ranking receipt | Each current ranking must have per-ranking receipt authority | Configured ranking root exists, but no `receipt`/`provenance`/`manifest` files exist under that root; bounded repository inventory found provenance implementation/tests (`app/research/ranking_provenance_receipt.py`, `app/research/ranking_provenance_admission.py`, `tests/test_ranking_provenance_receipt.py`, `tests/test_ranking_provenance_admission.py`) but no per-ranking receipt bundle for the 25 current ranking files | FAIL |
| G1.9 contemporaneous provenance | Ranking provenance must bind model/config/universe/top-N at capture time | No contemporaneous provenance or manifest exists under the configured ranking root to bind the 25 ranking files to model `ce643...`, signal config `b34c...`, universe `ba9c...`, history `4501...`, and `top_n: 10`; R6 also fixed no per-ranking receipt authority | FAIL |
| G2 capacity/split inventory | Only allowed after all G1 gates PASS | G1.8/G1.9 failed; capacity/split inventory intentionally not run | NOT_RUN |
| G3 outcome-free guard | No outcome, replay, sealed or benchmark access | No outcome-bearing command was run | PASS |

## Decision

`BLOCKED_RANKING_PROVENANCE_AUTHORITY`

Rationale：

1. V2 requires ranking corpus provenance to bind model、config、universe、top-N、per-ranking receipt 與 contemporaneous provenance；current fixed parent does not satisfy that precondition.
2. `config/research_shadow_runs.yaml` points to `artifacts/backtest/historical_rankings_current_model`; that root is absent only in the isolated repair projection, but exists in canonical configured checkout with `25` current ranking files and `28` total files.
3. Current history、features、universe、model、signal config bytes match V2, and top-N is explicitly configured as `10`; therefore G1.4-G1.7 are PASS against canonical configured authority.
4. The remaining blocker is narrower：the configured ranking root has no per-ranking receipt、provenance 或 manifest artifact that contemporaneously binds those ranking files to model/config/universe/history/top-N, so G1.8/G1.9 still fail before any capacity/split audit is allowed.
5. This is not `BLOCKED_CURRENT_AUTHORITY_CONFLICT` because the checked refs do not contradict R6/R7/R8/R9/V2; the blocker is missing ranking provenance authority, exactly covered by V2 fail-closed behavior.

## Reproducible Read-Only Commands

```bash
git rev-parse HEAD
git status --short
sed -n '1,260p' docs/tasks/2026-09-01_RESEARCH-NEW-TOP10-BC-CP2-R11-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY.md
sed -n '1,220p' docs/tasks/2026-09-01_REPAIR-NEW-TOP10-BC-CP2-R11-R1-CONFIGURED-ROOT-EVIDENCE.md
sed -n '1,180p' docs/tasks/2026-09-01_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY-V2.md
shasum -a 256 docs/tasks/2026-09-01_REPAIR-NEW-TOP10-BC-CP2-R11-R1-CONFIGURED-ROOT-EVIDENCE.md docs/tasks/2026-09-01_RESEARCH-NEW-TOP10-BC-CP2-R11-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY.md docs/tasks/2026-09-01_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY-V2.md docs/RESEARCH_SPINE_BACKLOG.md

# Run this from the isolated repair projection; absence here is projection scope evidence only.
find artifacts/backtest/historical_rankings_current_model -maxdepth 2 -type f

# Run the following from the canonical configured checkout root, not the isolated repair projection.
cd <repo-root>
sed -n '1,220p' config/research_shadow_runs.yaml
shasum -a 256 artifacts/market_regime_history_2026-05-29.json data/clean/features.parquet data/clean/universe.parquet models/latest_lgbm.pkl config/signals.yaml config/research_shadow_runs.yaml
wc -c artifacts/market_regime_history_2026-05-29.json data/clean/features.parquet data/clean/universe.parquet
test -e artifacts/backtest/historical_rankings_current_model
find artifacts/backtest/historical_rankings_current_model -maxdepth 2 -type f -name 'ranking_*.csv' | wc -l
find artifacts/backtest/historical_rankings_current_model -maxdepth 2 -type f | wc -l
find artifacts/backtest/historical_rankings_current_model -maxdepth 2 -type f | sort
find artifacts/backtest/historical_rankings_current_model -maxdepth 2 -type f | rg 'receipt|provenance|manifest'
find artifacts/backtest/historical_rankings_current_model -maxdepth 2 -type f -name 'manifest*'
rg --files | rg 'ranking.*provenance|provenance.*ranking|ranking-provenance|historical_rankings_current_model|research_shadow_run_manifest|manifest|receipt'
```

CodeGraph source-decision command：

```text
codegraph_status(projectPath=".") -> CodeGraph not initialized
```

## Absorption Boundary

Why not less：

- 必須逐項驗 history、features、universe、model、config、top-N、configured ranking root、per-ranking receipt、contemporaneous provenance 與 current configured bytes；只引用 R6 的 conclusion 會漏掉 R11 repair parent 的現場 corpus 狀態。
- 必須明確區分「isolated projection 缺 ignored artifacts」與「canonical configured checkout 的 artifact authority」，否則會把 projection miss 誤寫成 configured root 缺失。
- 必須在第一 gate 即停止，才能證明沒有偷跑 capacity/split 或 outcome。

Why not more：

- G1.8/G1.9 fail；V2 規定不得進入 capacity/split inventory。
- 不應用 fog root、old manifest、historical rebuild 或 `REPLAY_GENERATED` 補洞，否則會違反 R6、R9 與 V2 ranking provenance boundary。
- R11 不是 ranking provenance implementation、artifact restore、receipt registration、R12 admission 或 production work。

Do not absorb：

- 不吸收 outcome、return、PnL、win rate、Sharpe、alpha、target、promotion score、sealed outcome 或 replay/benchmark。
- 不吸收 capacity counts、global split construction、overlap component census 或 preregistration claim。
- 不吸收 ranking generation、ranking backfill、fog root promotion、old manifest admission 或 per-ranking receipt implementation。
- 不吸收 taxonomy、split、episode、horizon、runner、queue、scheduler、workflow 或 production 變更。

## Temporary Cleanup

- Temporary files：`NONE`
- Temporary directories：`NONE`
- External writes：`NONE`

## Acceptance Mapping

| Acceptance item | Status |
| --- | --- |
| 只修改指定 evidence | PASS |
| 四選一 verdict | PASS：`BLOCKED_RANKING_PROVENANCE_AUTHORITY` |
| 逐 gate PASS／FAIL／NOT_RUN | PASS |
| 可重現唯讀命令 | PASS |
| Outcome-free | PASS |
| Capacity/split provenance gate 後停止 | PASS：`NOT_RUN` |
| `git diff --check` | PASS：evidence write 後 pre-commit diff check exit `0`；post-commit diff check 由 final verification 固定 |
| Clean worktree | PASS：preflight clean；post-commit clean 由 final verification 固定 |
| 獨立 fixed-SHA Review 無 P0/P1 | NOT_RUN_BY_WORKER；留待 Mainline／Reviewer 驗收 |

## Unique Frontier

唯一 frontier：`OWNER_ADMISSION_REVIEW_FOR_R12_RANKING_PROVENANCE_AUTHORITY_REPAIR`

下一步若 Owner／Mainline 要繼續，只能先處理 current configured ranking corpus 與 per-ranking contemporaneous provenance authority；在此之前不得進入 Entry-Regime Cohort capacity/split feasibility、replay、outcome 或 preregistration。

# BC-CP2 R12 Ranking Provenance Authority 薄裁決

## Receipt

- 任務：`BC-CP2-R12-RANKING-PROVENANCE-AUTHORITY-DECISION`
- 固定 parent：`57539e95acc6555a74cf01a0c4935c1a58f12ce9`
- 任務卡：`docs/tasks/2026-09-01_RESEARCH-NEW-TOP10-BC-CP2-R12-RANKING-PROVENANCE-AUTHORITY-DECISION.md`
- 任務卡 sha256：`349a58ff82776b5029020020eb45c765aa860b9289c2f9b21e5db46613f1e4e2`
- R11 repaired evidence：`docs/evidence/BC-CP2-R11-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY/01-feasibility-decision.md`
- R11 repaired evidence sha256：`43746ec10c2bd58cbcd5e25e50141bbf0a090f07359f45ef66dac5a1210bba3a`
- Verdict：`GO_FOR_MINIMAL_FORWARD_CAPTURE_CARD`
- Historical corpus authority：`PERMANENT_NON_ADMISSION`
- Runtime session evidence：`MISSING`
- 交付限制：只新增本檔；未修改 code、tests、config、workflow、ranking、manifest、receipt、registry、data、runner、queue、scheduler、backtest 或 production。
- 執行限制：未產生或回填 ranking provenance，未建立 ledger／database／canonical writer／第二套 runtime，未執行 capture、replay、benchmark、outcome 或 sealed access；未准入 R13、Entry-Regime capacity、Phase 2、B1、C1 或 production；未 merge、push、改 Issue、deploy 或 external write。

## Source Decision

CodeGraph 在本 worktree 回報未初始化，因此 source decision 降級為限域唯讀盤點：

- Task／authority docs：R12 task card、R11 repaired evidence、R10 V2 contract、canonical backlog。
- Static seam：`app/research/ranking_provenance_receipt.py`、`app/research/ranking_provenance_admission.py`。
- Producer 接點：`scripts/build_historical_ranking_replay_set.py`、`scripts/research_regime_shadow_ranking.py`。
- Test evidence：`tests/test_ranking_provenance_receipt.py`、`tests/test_ranking_provenance_admission.py`。
- Runtime/session inventory：repo 內 `ranking_*.receipt.json`、`COMPLETE.manifest.json`、`*provenance*.json` 搜尋。

本卡不把程式存在、測試檔存在、舊 availability hash、old manifest、fog root、historical rebuild 或 `REPLAY_GENERATED` 當成 runtime capture authority。

## Fixed Refs

| Ref | sha256 / fact |
| --- | --- |
| R10 V2 contract | `94734b38961ed5a2cae8bad83705de6b94cb2d256e3ce9daee38a1442ea79ab5` |
| R11 repaired evidence | `43746ec10c2bd58cbcd5e25e50141bbf0a090f07359f45ef66dac5a1210bba3a` |
| Canonical backlog | `5065a341c3a050c78a6d94a341c8f47664dec36c201a2c2943489b8c8d5d5dc8` |
| Receipt seam | `app/research/ranking_provenance_receipt.py`; sha256 `34c702978e66b70db21e5a1e0338a2f56a62074e24f7759eb2da0515cd55db36` |
| Admission seam | `app/research/ranking_provenance_admission.py`; sha256 `323d3e133b5e554fe8ffb2ed890d41575a4499a8475bb64c420aa8158181c7f0` |
| Receipt tests | `tests/test_ranking_provenance_receipt.py`; sha256 `fa8f6192ce75a75a35b5bd8764c0993d206889b726a212faa36ba42765d90371` |
| Admission tests | `tests/test_ranking_provenance_admission.py`; sha256 `717c2e56bdadab12bd88b8fa771471738123a5ccb1ce8edad3db81cfa8d62971` |
| Baseline producer | `scripts/build_historical_ranking_replay_set.py`; sha256 `5474d30ab31b7aa7585a11441ce0611134fab9776c599474141c1b0c5138e061` |
| Shadow producer | `scripts/research_regime_shadow_ranking.py`; sha256 `d9fd14b6071b6d1f62da888ae40f3356cae3786e9cadf67195d0b8e529b5067f` |
| Prior admission audit | `docs/evidence/CARD-NEW-TOP10-RANKING-PROVENANCE-ADMISSION-AUDIT-V1/admission.json`; status `NO_GO_RANKING_PROVENANCE_INCOMPLETE`; `record_count=50`; `missing_lineage_field_count=300`; `receipt_authority_configured=false` |

Task card caveat：R12 task card 內文列 `fixed parent／R11=498b76c9282974a38cc43ecc9302c2ac12dcfa28`；delegation 與 actual preflight fixed parent 是 `57539e95acc6555a74cf01a0c4935c1a58f12ce9`，且 `57539e9` 是新增 R12 task card 的 commit，`498b76c` 是其前一個 R11 repaired evidence commit。此為 dependency label 分層，不解除本卡的 single-file evidence boundary。

## Static Capability Evidence

| Area | Evidence | Decision |
| --- | --- | --- |
| Receipt schema | `ranking-provenance-receipt.v1` includes ranking artifact、producer、model、config、universe、feature calendar、top-N policy、strict inputs、receipt identity | EXISTING_SEAM |
| Capture mode boundary | `ensure_capture_mode` only allows `FORWARD_CAPTURE` when ranking date is single and equals trusted capture trade date; `REPLAY_GENERATED` returns admission false | EXISTING_SEAM |
| Historical non-admission | `build_receipt` rejects `REPLAY_GENERATED` with admission eligibility; forward only returns `pending_registration` | PERMANENT_NON_ADMISSION_FOR_HISTORICAL |
| Input binding | `snapshot_inputs` and `assert_same_inputs` bind strict input hashes before/after run | EXISTING_SEAM |
| Producer source binding | `producer_source_lineage` checks HEAD bytes for producer dependencies and rejects drift | EXISTING_SEAM |
| Artifact immutability | `BundleRun` uses run-unique staging, create-only receipt/manifest, and no overwrite final run directory | EXISTING_SEAM |
| Semantic ranking check | `stable_ranked_top_n` and `verify_ranking_semantics` require score DESC / stock_id ASC, unique stock_id, complete top-N and continuous ranks | EXISTING_SEAM |
| Producer integration | Baseline and shadow research producers import the receipt seam and expose `--forward-capture`, `--capture-trade-date`, `--run-identity` | EXISTING_SEAM |
| Admission audit | Current admission seam has `RECEIPT_AUTHORITY_CONFIGURED = False`; historical availability remains reject-only | HISTORICAL_NON_ADMISSION |

Static decision：existing first-party seam is sufficient to justify one minimal forward-capture session-evidence card. It is not sufficient to claim capture authority already exists.

## Test Evidence

本卡只讀 test evidence；未執行 tests，因本任務禁止 runtime/capture 與只允許新增 evidence。

| Test area | Evidence | Decision |
| --- | --- | --- |
| Forward date gate | `test_forward_mode_requires_explicit_single_matching_capture_date` covers single trusted capture date and rejects multi-date/wrong-date forward capture | STATIC_TEST_COVERAGE_PRESENT |
| Replay non-admission | `test_receipt_rejects_false_admission_absolute_path_outcome_and_noncanonical_identity` rejects `REPLAY_GENERATED` false admission | STATIC_TEST_COVERAGE_PRESENT |
| Canonical create-only bundle | `test_complete_bundle_is_canonical_create_only_and_verifiable` checks canonical bundle and create-only behavior | STATIC_TEST_COVERAGE_PRESENT |
| Ranking semantics | `test_stable_top_n_uses_score_desc_stock_id_asc_and_rejects_short_or_duplicate` and `test_semantic_verifier_rejects_short_top_n_and_unstable_score_order` cover row count、dedupe、排序 | STATIC_TEST_COVERAGE_PRESENT |
| Drift and tamper rejection | Receipt tests cover source drift、input/manifest/receipt swap、rollback；admission tests cover committed source drift、alias、false admission | STATIC_TEST_COVERAGE_PRESENT |
| Historical admission status | `test_actual_evidence_is_deterministic_no_go_matrix` asserts `NO_GO_RANKING_PROVENANCE_INCOMPLETE`, `record_count=50`, `missing_lineage_field_count=300`, all records reject | STATIC_TEST_COVERAGE_PRESENT |

Test decision：tests describe useful boundaries for a minimal forward capture attempt, but they are not runtime session evidence and do not prove create→capture→verify on this fixed parent.

## Runtime Session Evidence

| Evidence requirement | Observation | Result |
| --- | --- | --- |
| Existing `ranking_*.receipt.json` | repo search returned no files | MISSING |
| Existing `COMPLETE.manifest.json` | repo search returned no files | MISSING |
| Existing committed provenance JSON usable for current capture authority | no current forward-capture session artifact found | MISSING |
| Prior admission audit | `NO_GO_RANKING_PROVENANCE_INCOMPLETE`, 50 records, 300 missing lineage fields, `receipt_authority_configured=false` | REJECT_HISTORICAL |
| create→capture→verify session evidence | no session receipt proving successful one-date forward capture and bundle verification | MISSING |

Runtime decision：no existing runtime session evidence proves the seam works end-to-end. Therefore R12 cannot declare ranking provenance capture authority already usable.

## Historical Corpus Boundary

Historical corpus is permanently `NON_ADMISSION` for this decision chain:

- Existing historical ranking availability and old hashes are not contemporaneous provenance.
- `REPLAY_GENERATED` remains `admission_eligible=false` even when receipt fields are complete.
- Historical rebuild, fog root, old manifest and filename coverage cannot repair R11/R12 provenance authority.
- Any future historical artifact may be diagnostic or replay support only; it cannot become admission authority without a new Owner-level policy decision.

## Decision

`GO_FOR_MINIMAL_FORWARD_CAPTURE_CARD`

Rationale：

1. `NO_GO_NEW_SUBSYSTEM_REQUIRED` is too strong: the first-party receipt/admission seam, producer hooks, input binding, model snapshot, create-only bundle and static tests already exist. The minimum next step is not a new ledger/database/canonical writer/runtime.
2. `DEFER_UNTIL_NATURAL_AUTHORITY_ACCUMULATES` is too passive: without an admitted forward capture session-evidence card, natural passage of time will not by itself produce create→capture→verify evidence under the required contract.
3. The GO is narrow: it only admits a future minimal card to run one forward capture session and verify the produced bundle. It does not admit R13, production, Entry-Regime capacity, replay, outcome, historical corpus, backfill or preregistration.
4. Missing runtime session evidence remains explicit: no current artifact proves create→capture→verify, so the seam is candidate-capable, not authority-active.

## Reproducible Read-Only Commands

```bash
git rev-parse HEAD
git status --short
git log --oneline -8
sed -n '1,260p' docs/tasks/2026-09-01_RESEARCH-NEW-TOP10-BC-CP2-R12-RANKING-PROVENANCE-AUTHORITY-DECISION.md
sed -n '1,220p' docs/evidence/BC-CP2-R11-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY/01-feasibility-decision.md
sed -n '1,260p' app/research/ranking_provenance_receipt.py
sed -n '260,620p' app/research/ranking_provenance_receipt.py
sed -n '1,260p' app/research/ranking_provenance_admission.py
sed -n '260,620p' app/research/ranking_provenance_admission.py
sed -n '1,260p' tests/test_ranking_provenance_receipt.py
sed -n '1,260p' tests/test_ranking_provenance_admission.py
sed -n '1,220p' scripts/build_historical_ranking_replay_set.py
sed -n '220,520p' scripts/build_historical_ranking_replay_set.py
sed -n '340,540p' scripts/research_regime_shadow_ranking.py
rg -n "def test_|FORWARD_CAPTURE|REPLAY_GENERATED|admission_eligible|verify_complete_bundle|build_receipt|BundleRun|producer_source_lineage|snapshot_inputs|assert_same_inputs|create_content_addressed_model_snapshot|stable_ranked_top_n" tests/test_ranking_provenance_receipt.py tests/test_ranking_provenance_admission.py app/research/ranking_provenance_receipt.py app/research/ranking_provenance_admission.py scripts/build_historical_ranking_replay_set.py scripts/research_regime_shadow_ranking.py
find . -maxdepth 8 -type f \( -name 'ranking_*.receipt.json' -o -name 'COMPLETE.manifest.json' -o -name '*provenance*.json' \)
rg -n "NO_GO_RANKING_PROVENANCE_INCOMPLETE|missing_lineage_field_count|record_count|receipt_authority_configured|CONTEMPORANEOUS_RANKING_PROVENANCE_MISSING|ADMITTED_RANKING_PROVENANCE_COMPLETE|RECEIPT_AUTHORITY_CONFIGURED" docs/evidence/CARD-NEW-TOP10-RANKING-PROVENANCE-ADMISSION-AUDIT-V1/admission.json app/research/ranking_provenance_admission.py tests/test_ranking_provenance_admission.py
shasum -a 256 app/research/ranking_provenance_receipt.py app/research/ranking_provenance_admission.py tests/test_ranking_provenance_receipt.py tests/test_ranking_provenance_admission.py scripts/build_historical_ranking_replay_set.py scripts/research_regime_shadow_ranking.py
```

CodeGraph source-decision command：

```text
codegraph_status(projectPath=".") -> CodeGraph not initialized
```

## Absorption Boundary

Why not less：

- 必須同時盤點 receipt builder、admission audit、兩個 producer 接點、test coverage 與 runtime artifact absence；只看 R11 blocker 會漏掉 existing seam 是否足以支援最小 forward capture。
- 必須區分 static capability、test evidence、runtime session evidence；否則容易把程式存在誤當成 runtime authority。
- 必須固定 historical corpus 永久 `NON_ADMISSION`，避免 R13 或後續卡把 old manifest/fog root/rebuild 當補洞捷徑。

Why not more：

- R12 是薄裁決，不是 implementation、capture run、registration、artifact restore、new subsystem 或 production work。
- 未有 create→capture→verify session evidence前，不得宣稱 seam 已可用或 admission authority 已成立。
- 不需要設計第二套 ledger、database、canonical writer 或 runtime；既有 first-party seam 足以承載下一張最小 session-evidence 卡。

Do not absorb：

- 不吸收 capture execution、ranking generation/backfill、manifest/receipt write、registration、production scheduler 或 external write。
- 不吸收 outcome、return、PnL、win rate、Sharpe、alpha、target、promotion score、sealed outcome、replay 或 benchmark。
- 不吸收 Entry-Regime capacity/split feasibility、R13 admission、Phase 2、B1、C1 或 production canary。
- 不吸收 historical corpus admission、fog root promotion、old manifest promotion 或 `REPLAY_GENERATED` exception。

## Acceptance Mapping

| Acceptance item | Status |
| --- | --- |
| 只新增指定 evidence | PASS |
| 三選一 verdict | PASS：`GO_FOR_MINIMAL_FORWARD_CAPTURE_CARD` |
| Static/test/runtime evidence 分層 | PASS |
| Historical corpus 永久 `NON_ADMISSION` | PASS |
| 不宣稱 runtime capture 已可用 | PASS |
| 不建立新 subsystem | PASS |
| `git diff --check` | PASS：evidence write 後 pre-commit diff check exit `0`；post-commit diff check 由 final verification 固定 |
| Clean worktree | PASS：preflight clean；post-commit clean 由 final verification 固定 |
| 獨立 fixed-SHA Review 無 P0/P1 | NOT_RUN_BY_WORKER；留待 Mainline／Reviewer 驗收 |

## Unique Frontier

唯一 frontier：`R13-MINIMAL-FORWARD-CAPTURE-SESSION-EVIDENCE`

停止條件：若 Owner／Mainline 不明示准入 R13，本鏈停在本 R12 裁決；historical corpus 維持永久 `NON_ADMISSION`，不得進入 Entry-Regime capacity/split feasibility、replay、outcome、preregistration 或 production。

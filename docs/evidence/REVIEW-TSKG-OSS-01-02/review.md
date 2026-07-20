---
card_id: REVIEW-TSKG-OSS-01-02
status: REVIEW_GO
reviewed_on: 2026-07-20
re_reviewed_on: 2026-07-20
reviewer_thread_id: 019f7e60-0da2-71d1-b9cb-76f794312ee6
operation_level: independent_read_only_review
---

# REVIEW-TSKG-OSS-01-02 review

## Verdict

`GO`

Re-review fixed repair candidate `a29e007baf431e98eab005082baddda258b2be7a` resolves the original P2 finding from review commit `5919ca987367aac50287f156ef3101610f335310`. The combined inputs `TSKG-OSS-01` at `f6a4f8fd263364d8dfe94f47f02e0e22cb6a8507` and repaired `TSKG-OSS-02` at `a29e007baf431e98eab005082baddda258b2be7a` can be used as ADR input, with the remaining risks below carried forward.

## Reviewed commits

| Item | Commit | Parent check |
|---|---|---|
| Review card HEAD | `b95584f228410a9e83896c6b3de7d2d988dd56c8` | n/a |
| Candidate OSS-01 | `f6a4f8fd263364d8dfe94f47f02e0e22cb6a8507` | parent = `1a2b0eab8a3ed625d85fdeef6ce4ddb4726a7208` |
| Original Candidate OSS-02 | `d935c4fcb9e67faf124984dd07c93d72722a470e` | parent = `1a2b0eab8a3ed625d85fdeef6ce4ddb4726a7208` |
| Original NO_GO review | `5919ca987367aac50287f156ef3101610f335310` | n/a |
| Repair card parent | `b5e5019a64c85486f66edcb6c4b3fca690528379` | n/a |
| Repaired Candidate OSS-02 | `a29e007baf431e98eab005082baddda258b2be7a` | parent = `b5e5019a64c85486f66edcb6c4b3fca690528379` |

## Findings

- [P2][RESOLVED] `TWSEMCPServer` latest release metadata is stale/incorrect - `d935c4fcb9e67faf124984dd07c93d72722a470e:docs/research/TSKG-OSS-02_external_open_source_reference_scout.md:34`
  - Evidence: candidate line 34 and lines 150-152 state GitHub latest release `v1.3.0` on `2026-05-22`. The canonical repo page at `https://github.com/twjackysu/TWSEMCPServer` shows `Releases 13` and latest `v1.8.0` on `Jul 19, 2026`; the same page still supports the MIT license, 176 commits, and 3 open issues. The direct T86 relevance remains supported by `CLAUDE.md`, which mentions `/rwd/zh/fund/T86`.
  - Risk: the external reference scout claims exact maintenance evidence as of `2026-07-20`, but one of the most important direct candidates has an incorrect latest release/date. This can mislead the ADR input about current activity and violates the review card's release/activity-date cross-check requirement.
  - Repair acceptance: update the OSS-02 candidate research and verification evidence to the current canonical release/date for `TWSEMCPServer`, include the source line/URL used, keep the warning that README/CLAUDE is not official endpoint authorization, rerun exact allowlist/path scan/`git diff --check`, and resubmit for review.
  - Re-review result: repaired candidate line 34 and lines 151-152 now state canonical repo sidebar latest release `v1.8.0 / 2026-07-19`, retain the `README/CLAUDE` non-authorization boundary, and record GitHub cross-page inconsistency. This satisfies the P2 repair acceptance.

No new P0-P2 findings were found in the repair.

## Spec Axis

`GO`

- OSS-01 satisfies the requested repo call-chain check at review depth: FinMind fetcher/integrator/FetchStage/indicator consumer and direct TWSE T86 market-context caller/verifier/artifact consumers are present in repo evidence.
- OSS-01 status and reuse decisions are conservative: FinMind is `REFERENCE_ONLY`/`NEEDS_VALIDATION`, direct T86 fetch is not treated as approved production ingestion, and `SecurityFlowObservation` raw-only/TWD/source-policy boundaries are not collapsed.
- Repaired OSS-02 satisfies the required canonical/source boundary checks: FinMind code/data-use split, twstock request-limit note, twstocks-crawler low-confidence metadata, tsec/tsrtc license gaps, TWSEMCPServer directness, and corrected TWSEMCPServer release/date evidence are represented conservatively.
- Repair did not turn TWSEMCPServer README/CLAUDE claims into endpoint authorization or source approval.
- Repair verification was narrowed to the release-metadata repair, but the original scout source tracker remains in the repaired research report. This does not create a P0-P2 evidence regression because the source ledger supporting the seven candidates was not removed from the deliverable.

## Standards Axis

`GO`

- Candidate commits are docs-only and respect the no-runtime/no-external-execution boundary.
- Candidate and repair diffs pass whitespace checks.
- Shared evidence should continue using repo-relative paths or `<repo-root>`.
- Repair changed only the repair-card allowlist paths and did not modify code, config, runtime, API, UI, TSKG contract, SourcePolicy, or OSS-01.
- The repaired verification file is a scoped repair verification rather than a full replacement of the scout ledger; this is acceptable because the repaired research file still carries the full source tracker and unchanged candidate-count/license-risk conclusions.

## Source Ledger

| ID | Source | Review use | Status |
|---|---|---|---|
| R01 | Repo files under `app/**`, `scripts/**`, `docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md` | OSS-01 call-chain and governance blocker cross-check | retrieved local |
| R02 | `https://pypi.org/project/finmind/` | FinMind PyPI `2.0.5`, upload date, Apache metadata, request limit note | retrieved |
| R03 | `https://finmind.github.io/en/PrivacyPolicy/` | FinMind service/data-use boundary; software license separated from service terms | retrieved |
| R04 | `https://github.com/mlouielu/twstock` | twstock MIT license, TWSE request-limit README note, latest GitHub release | retrieved |
| R05 | `https://pypi.org/project/twstock/` | twstock PyPI `1.5.1` release date and MIT metadata | retrieved |
| R06 | `https://pypi.org/project/twstocks-crawler/` | twstocks-crawler `0.0.7`, MIT metadata, sparse description | retrieved |
| R07 | `https://github.com/twjackysu/TWSEMCPServer` | TWSEMCPServer MIT license, commits/issues, latest release mismatch evidence | retrieved |
| R08 | `https://github.com/twjackysu/TWSEMCPServer/blob/main/CLAUDE.md` | T86 directness evidence; not treated as official endpoint authorization | retrieved |
| R09 | `https://github.com/twjackysu/TWSEMCPServer/releases` | Re-review cross-page release presentation check | retrieved |

No clone, archive download, dependency install, external code execution, login/token use, financial data endpoint call, rate test, or remote write was performed.

## Commands And Exit Codes

| Command | Exit | Purpose |
|---|---:|---|
| `git status --short --branch` | 0 | Confirm HEAD state and clean output context |
| `git rev-parse --show-toplevel --git-dir --is-inside-work-tree HEAD` | 0 | Confirm independent worktree and HEAD |
| `test -e <repo-gitdir>/worktrees/TOP10new6/index.lock` | 1 | Confirm no index lock exists |
| `sed -n '1,260p' docs/tasks/2026-07-20_REVIEW-TSKG-OSS-01-02_reuse_research.md` | 0 | Read review contract |
| `git cat-file -t f6a4f8fd263364d8dfe94f47f02e0e22cb6a8507` | 0 | Confirm OSS-01 candidate object |
| `git cat-file -t d935c4fcb9e67faf124984dd07c93d72722a470e` | 0 | Confirm OSS-02 candidate object |
| `git rev-parse f6a4f8fd...^ d935c4f...^ 1a2b0eab...` | 0 | Confirm common parent |
| `git show --name-only --format=fuller <candidate>` | 0 | Inspect candidate file scope |
| `git diff --name-status 1a2b0eab... <candidate>` | 0 | Confirm candidate changed files |
| `git show <candidate>:<path> \| nl -ba \| sed -n ...` | 0 | Read fixed candidate blobs with line numbers |
| `rg -n "FinMind\|..." app scripts tests docs/References.md docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md` | 0 | Cross-check OSS-01 repo call-chain |
| `sed -n ... app/finmind_fetcher.py app/finmind_integrator.py app/pipeline/fetch_stage.py app/market_context_fetcher.py scripts/verify_market_context_fetcher.py` | 0 | Inspect local code evidence |
| `git diff --check 1a2b0eab... f6a4f8fd...` | 0 | OSS-01 candidate whitespace gate |
| `git diff --check 1a2b0eab... d935c4f...` | 0 | OSS-02 candidate whitespace gate |
| `rg -n '/(Users|private)/\|file:/[/]' docs/tasks/2026-07-20_REVIEW-TSKG-OSS-01-02_reuse_research.md` | 1 | No host-specific path match in review card |
| `git status --short` | 0 | Confirm only review evidence is untracked before final gates |
| `rg -n '/(Users|private)/\|file:/[/]' docs/evidence/REVIEW-TSKG-OSS-01-02/review.md docs/tasks/2026-07-20_REVIEW-TSKG-OSS-01-02_reuse_research.md` | 1 | No host-specific path match in review evidence/card |
| `git diff --check -- docs/evidence/REVIEW-TSKG-OSS-01-02/review.md` | 0 | Review evidence whitespace gate |
| `git cat-file -t a29e007baf431e98eab005082baddda258b2be7a` | 0 | Confirm repair candidate object |
| `git rev-parse a29e007...^ b5e5019... 5919ca9...` | 0 | Confirm repair parent and original NO_GO review commit |
| `git show --name-only --format=fuller a29e007...` | 0 | Inspect repair candidate scope |
| `git diff --name-status b5e5019... a29e007...` | 0 | Confirm exact repair changed files |
| `git diff --check b5e5019... a29e007...` | 0 | Repair candidate whitespace gate |
| `git grep -n "v1.3.0\|2026-05-22" a29e007... -- <repair allowlist>` | 0 | Old latest-release text remains only in repair task problem statement |
| `git grep -n -E '/(Users\|private)/\|file:/[/]' a29e007... -- <repair allowlist>` | 1 | No host-specific path match in repaired candidate files |

## Remaining Risks

- External GitHub/PyPI pages are live sources and can change after this review; the finding is based on read-only retrieval on `2026-07-20`.
- Reviewer did not execute candidate code or any external market-data endpoint by design.
- Reviewer did not verify every old GitHub release page for `tsec`/`tsrtc`; their candidate conclusions remain conservative because license/maintenance gaps are already called out.
- GitHub's TWSEMCPServer repo page and releases page continue to show inconsistent release metadata through unauthenticated HTML views. During this re-review, the repo page showed `v1.8.0 / Jul 19, 2026`, while the releases page HTML showed older release metadata. This is recorded as a remaining upstream presentation risk, not a blocker, because the repaired report identifies the canonical repo page basis and preserves the inconsistency warning.

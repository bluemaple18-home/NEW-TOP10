---
card_id: TSKG-OSS-01
status: DELIVERED_CANDIDATE
operation_level: repo_first_read_only
access_date: 2026-07-20
---

# TSKG-OSS-01 verification

## 1. Preflight receipt

正式 receipt：

```text
thread_id: 019f7e58-df0f-7eb1-808d-369fa5c02206
source_card_commit: 1a2b0ea
worktree_path: <local-only-worktree verified in preflight>
```

Local-only preflight commands and observed result:

```bash
pwd
git rev-parse --show-toplevel
git rev-parse --git-dir
git status --short
git rev-parse HEAD
git merge-base --is-ancestor 1a2b0ea HEAD && printf 'card commit ancestor yes\n'
test ! -e "$(git rev-parse --git-dir)/index.lock" && printf 'index lock clear\n'
```

Observed:

```text
cwd: <local-only-worktree>
show-toplevel: <local-only-worktree>
git-dir: <local-only-gitdir>
git status --short: clean before document edits
HEAD: 1a2b0eab8a3ed625d85fdeef6ce4ddb4726a7208
card commit ancestor yes
index lock clear
```

Sandbox note: direct `test -w "$(git rev-parse --git-dir)"` returned not writable inside restricted sandbox because git metadata lives under the source repo's worktree metadata. Candidate commit was therefore expected to require platform-approved git write permissions.

## 2. Repo search evidence

Commands used:

```bash
rg -n -i "FinMind|finmind|T86|三大法人|外資|投信|自營商|institutional|legal person|Dealer|Investment_Trust|Foreign_Investor" app scripts tests docs config README*
rg --files app scripts tests docs | rg -i "finmind|market_context|fetch_stage|fundamental|institution|t86|twse"
rg -n "market_context|build_market_context|parse_twse_institutional|institutional\\]|foreign_net|trust_net|dealer_net|foreign_buy|trust_buy|dealer_buy|inst_buy" app scripts tests docs
rg -n -i "FinMind|finmind|DataLoader" requirements.txt app docs scripts tests
find artifacts -maxdepth 2 -type f \( -name '*market_context*' -o -name '*chip*' -o -name '*institutional*' -o -name '*finmind*' \) | sort | head -n 80
```

Key findings:

- `requirements.txt` contains `finmind>=1.2.0`.
- `app/finmind_fetcher.py` imports `FinMind.data.DataLoader` and exposes institutional investors plus margin purchase/short sale methods.
- `app/finmind_integrator.py` maps `Foreign_Investor` and `Investment_Trust`, sums `Dealer*`, and emits `foreign_buy/trust_buy/dealer_buy`.
- `app/pipeline/fetch_stage.py` calls `FinMindIntegrator().integrate_chip_data(df)` and records skipped status on exception.
- `app/indicators/core.py` includes `foreign_buy/trust_buy/dealer_buy` pivots when present; `app/indicators/mixins/volume.py` derives institutional indicators from those columns.
- `app/market_context_fetcher.py` has `parse_twse_institutional` and direct T86 fetch URL.
- `scripts/verify_market_context_fetcher.py` monkeypatches fetches and checks `institutional_parsed`.
- `scripts/run_automation.py` invokes `python -m app.market_context_fetcher --date ...` when daily config enables market context.
- `scripts/build_decision_quality.py` consumes market context `institutional`.
- `find artifacts ...` returned no tracked/local market_context, chip, institutional, or finmind artifact under the current worktree.

## 3. Git evidence

Commands used:

```bash
git log --oneline --decorate -- app/finmind_fetcher.py app/finmind_integrator.py app/pipeline/fetch_stage.py app/market_context_fetcher.py docs/References.md docs/tasks/2026-05-29_MARKET-CONTEXT-02-TW_fetcher.md docs/tasks/2026-05-28_MARKET-CONTEXT-02_tw_context_handoff.md
git log --format='%H%x09%ad%x09%s' --date=short -- app/finmind_fetcher.py app/finmind_integrator.py app/pipeline/fetch_stage.py app/market_context_fetcher.py app/indicators/mixins/volume.py scripts/verify_market_context_fetcher.py docs/References.md
git blame -L 1,110 -- app/finmind_integrator.py
git blame -L 1,45 -- app/pipeline/fetch_stage.py
git blame -L 211,408 -- app/market_context_fetcher.py
```

Observed summary:

```text
61c6d541d3e206de4567979516f4841412066d23  2026-05-29  Add decision quality artifact pipeline
814261b976e27ee2ea44c3eb37d1d1e7a58b12e0  2026-05-27  Add daily Clawd publish flow
f6572457ef02e492a609595d7fdadd1e6fa72ff6  2026-05-25  初始化 NEW-TOP10 主線
```

Blame summary:

- `app/finmind_integrator.py` lines 1-99 are from initial commit `f657245`.
- `app/pipeline/fetch_stage.py` FinMind import/call/skip block is from initial commit `f657245`; nearby dedupe line 30 changed in `814261b`.
- `app/market_context_fetcher.py` T86 parser and fetch block lines 211-408 are from `61c6d541`.

## 4. Classification evidence

| Item | Classification | Evidence basis |
|---|---|---|
| FinMind fetcher/integrator | `FALLBACK` | Has FetchStage caller, but exceptions skip and no dedicated verifier/artifact was found |
| FinMind margin method | `DORMANT` | Exists, but no caller found by repo search |
| Institutional indicator consumer | `ACTIVE` consumer, source `UNKNOWN` | Called by `calculate_all_indicators`, but source columns depend on upstream data |
| TWSE T86 parser/fetcher | `ACTIVE` code path, source approval `UNKNOWN/BLOCKED` | Called by automation and tested synthetically; `TSKG-MFO-SRC-01` keeps source blocked |
| Market context verifier | `ACTIVE` verifier | Synthetic test checks T86 institutional parsing and single-source failure |
| Docs/reference links | `DORMANT` or `REFERENCE_ONLY` | Useful navigation, not approval |

## 5. Verification not run

Not run by design:

- `python -m app.market_context_fetcher --date ...`
- `app/finmind_fetcher.py` `__main__`
- full ETL, daily automation, ranking, model training
- any command that calls FinMind, TWSE, TPEx, TAIFEX or other external financial services

Reason: task contract explicitly forbids external financial data service calls and code/runtime modifications.

## 6. Final gates

Commands run after document edits and before candidate commit:

```bash
git status --short
rg -n '/(Users|private)/|file:/[/]' docs/tasks/2026-07-20_TSKG-OSS-01_existing_asset_reuse_audit.md docs/research/TSKG-OSS-01_existing_asset_reuse_audit.md docs/evidence/TSKG-OSS-01/verification.md
git diff --check -- docs/tasks/2026-07-20_TSKG-OSS-01_existing_asset_reuse_audit.md docs/research/TSKG-OSS-01_existing_asset_reuse_audit.md docs/evidence/TSKG-OSS-01/verification.md
```

Observed gate result:

```text
git status --short: only allowlist paths changed/untracked
host-specific path scan: no matches
git diff --check: pass
```

Expected allowlist:

```text
docs/evidence/TSKG-OSS-01/verification.md
docs/research/TSKG-OSS-01_existing_asset_reuse_audit.md
docs/tasks/2026-07-20_TSKG-OSS-01_existing_asset_reuse_audit.md
```

# TSKG-SLC-01 Verification Evidence

## Scope

- Source card commit: `f1ece54bd8d072da70265a4c8ea5ab6f8b4d1210`
- Worktree mode: platform-managed independent worktree
- Scope: synthetic fixture → deterministic resolver → injectable company service → standalone FastAPI router
- Explicit exclusions: production API composition, external network/data source, LLM, database, cache, graph store, real relationship/trading data

## Preflight

- `HEAD` was exactly the source card commit before edits.
- `git merge-base --is-ancestor f1ece54bd8d072da70265a4c8ea5ab6f8b4d1210 HEAD` returned success.
- Worktree and index were clean before edits.
- No `index.lock` existed.

## TDD RED

Public behavior tests were created before `app/tskg/**` or the fixture existed.

Command semantics (offline; using the existing main-workspace `<repo-root>/.venv`
Python 3.11 environment without dependency sync):

```text
UV_NO_SYNC=1 UV_OFFLINE=1 uv run --with-requirements requirements.txt python -m unittest tests.test_tskg_slc01 -v
```

Meaningful RED result:

```text
ImportError: Failed to import test module: test_tskg_slc01
ModuleNotFoundError: No module named 'app.tskg'
Ran 1 test in 0.000s
FAILED (errors=1)
```

This is the expected public-boundary failure: the tests could import FastAPI and start unittest discovery, but the new package did not exist.

The local-only environment binding used to expose that existing venv was removed
before GREEN implementation verification; this worktree does not create, replace,
or retain a `.venv` or symlink.

### Non-RED environment diagnostics

An earlier invocation selected Python 3.14 because this new worktree had no local `.venv`. It stopped before test discovery while existing `lxml==4.9.4` failed to compile against Python 3.14. That result is not counted as TDD RED. The meaningful RED above used the already-provisioned Python 3.11 environment and disabled network/sync.

The requested original command remains:

```text
uv run --with-requirements requirements.txt python -m unittest tests.test_tskg_slc01 -v
```

Its status is `BLOCKED_BY_PYTHON_3_14_LXML`: without a worktree-local project
environment, `uv` selected Python 3.14 and existing `lxml==4.9.4` is incompatible.
It is not reported as passing. No dependency or requirements change was made.

The suggested `UV_PROJECT_ENVIRONMENT=<repo-root>/.venv uv run --no-sync ...`
form also did not select the environment because this repository has no
`pyproject.toml`; `uv` reported that `--no-sync` had no effect outside a project.
Verification therefore invoked the already-approved Python 3.11 interpreter
directly, with no resolver, sync, install, or network access.

## GREEN Verification

Portable environment semantic: `<repo-root>/.venv/bin/python` from the main
workspace. Local-only resolved interpreter evidence:
`/Users/matt/TOP10new/.venv/bin/python` (`Python 3.11.14`).

```text
<repo-root>/.venv/bin/python -m unittest tests.test_tskg_slc01 -v
```

Result: `Ran 13 tests in 0.662s` / `OK`.

Covered public behaviors:

- NFKC/whitespace/casefold alias normalization.
- NVIDIA/NVDA/Nvidia, Tesla/TESLA, and Meta/Facebook canonical resolution.
- Cross-jurisdiction alias collision returns structured `AMBIGUOUS`.
- Security code remains a string, including leading-zero `0123`.
- `3017` follows explicit `issuer_id`; same-code cross-market ambiguity is fail-closed.
- 200/400/404/409 API envelopes and market-specific lookup.
- All relation sections are empty paged collections.
- Reordered fixture checksum stability, prohibited-field scan, and existing API isolation.

```text
<repo-root>/.venv/bin/python -m py_compile app/tskg/*.py tests/test_tskg_slc01.py
```

Result: PASS (exit 0, no output).

## Fixture and Determinism

- Fixture version: `identity-v1`
- Schema version: `tskg-identity-fixture-v1`
- Normalizer version: `nfkc-casefold-v1`
- Canonical entities: 13 (9 Organization, 4 Security)
- Alias records: 10
- Normalized alias collision groups: 1
- Relationship claims: 0

Deterministic checksum method:

1. Load the fixture normally and with reversed `entities`/`aliases` input order.
2. Resolve `3017` and build the company envelope from each repository.
3. Remove the injected top-level `request_id`.
4. Serialize with UTF-8 JSON, `sort_keys=True`, `ensure_ascii=False`, and compact separators.
5. Compare SHA-256.

Canonical byte length: 1391. SHA-256:
`2da13d5090b32b3c22900770b74fef3be61c651d820defdd7db1bee0e8f5eb28`.

## API Contract and Isolation

- Happy path top-level keys are exactly `request_id`, `data`, `freshness`,
  `provenance_summary`, and `warnings`.
- `products`, `themes`, `customers`, `suppliers`, `competitors`, `upstream`,
  `downstream`, and `etfs` each equal `{items: [], next_cursor: null}`.
- Fixture provenance explicitly marks the response synthetic and reports zero
  relationship claims.
- Recursive response-key scan found no score, weight, prediction, buy/sell,
  target, or stop fields.
- Importing `app.api.main` succeeded; its OpenAPI paths do not contain
  `/v1/company/{stock_id}`. The standalone router is not composed into runtime.

## Changed-file Allowlist

Expected candidate paths (all are on the card allowlist):

```text
app/tskg/__init__.py
app/tskg/identity.py
app/tskg/repository.py
app/tskg/router.py
app/tskg/service.py
data/fixtures/tskg/identity_v1.json
docs/evidence/TSKG-SLC-01/verification.md
docs/tasks/2026-07-18_TSKG-SLC-01_offline_identity_company_query.md
tests/__init__.py
tests/test_tskg_slc01.py
```

- `app/api/main.py`: unchanged.
- `requirements.txt`: unchanged.
- Changed-file allowlist: PASS; staged path set exactly matched the 10 paths above.
- `git diff --cached --check`: PASS (exit 0, no output).
- Initial candidate `4f58e4f5252da0f244fe28a0bf1806818b4440bf` post-commit
  verification: PASS; `git status --short` was empty, detached HEAD was the only
  branch-status line, `git diff --check` passed, and no `index.lock` existed.
  The evidence-only amend preserves source-card parent
  `f1ece54bd8d072da70265a4c8ea5ab6f8b4d1210`; final SHA and final clean status
  are reported by the delivery thread after the amend.

## Remaining Risk and Unrun Scope

- The original `--with-requirements` command is
  `BLOCKED_BY_PYTHON_3_14_LXML`; direct Python 3.11 verification passed.
- No browser, network, LLM, database, Redis, Neo4j, Postgres, crawler, scheduler,
  or production runtime verification was run because each is outside this card.
- This card does not establish real-data correctness, relationship claims,
  production API integration, database behavior, ingestion behavior, or SLO acceptance.

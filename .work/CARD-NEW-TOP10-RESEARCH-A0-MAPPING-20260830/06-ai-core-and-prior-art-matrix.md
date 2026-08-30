# 06 — AI Core and Prior Art Matrix

日期：2026-08-30
Lane：A0 Lane C — AI Core and Official Prior Art Mapping
Execution base：NEW-TOP10 `origin/main@4c6d41a44314beb3592ccdf7a9b43d8fe614ad88`
AI Core authority：`aicore/docs/ai-core-backlog.md@c896cbff126a57384f5f436b80ceaa2e14a22999`
OMI authority：`prior_art_only`，指定 commit `lulu930128/open-market-intelligence@2d54c5983b8597babd804110f022a5f299e45a9d`

## Scope

本檔只做 A0 Lane C 的 reuse/admission matrix。它不修改 AI Core、NEW-TOP10 code/config/schema/runtime/DB/scheduler/production，不啟動 A1-A6，也不把任何 prior art backend、tracking DB、hidden Git ref、optimizer、RDF subsystem 或 event store 升格為 NEW-TOP10 authority。

裁決值只使用：

`ALREADY_EXISTS` / `USE_AS_IS` / `CONFIGURE` / `WRAP` / `ADAPT` / `COPY_CODE` / `CUSTOM_REQUIRED` / `REJECT`

## Evidence Inventory

| evidence_ref | authority | as_of | evidence_hash | status | note |
|---|---|---:|---|---|---|
| `AI-CORE:docs/ai-core-backlog.md@c896cbf` | pinned AI Core remote commit | 2026-08-29 | `git_blob_sha1:503244e14c6dcfd15b6e18331149a5320294d5c3` | CONFIRMED | Current unique frontier is `NONE`; no new runtime authority without real product evidence. |
| `AI-CORE:docs/research/PERSONAL-MODE-RUNTIME-SAFETY-PRIOR-ART-20260825.md@c896cbf` | pinned AI Core remote commit | 2026-08-25 | `git_blob_sha1:20a72976b14c26c1ba9f1a569686cb885b310391` | CONFIRMED | Runtime owns session/thread/worktree/tool loop by default; AI Core owns Mission/policy/memory/routing/convergence. |
| `AI-CORE:rules/24-prior-art-implementation-admission.md@c896cbf` | pinned AI Core remote commit | 2026-08-25 | `git_blob_sha1:681962d23f267fda050988a3f28486fd616d8e54` | CONFIRMED | `run/wrap/adapt` before port/custom; no second authority/lifecycle/registry by default. |
| `NEW:docs/RESEARCH_SPINE_BACKLOG.md@4c6d41a` | NEW-TOP10 pinned execution base | 2026-08-30 | `git_blob_sha1:9e84f150e37c3b717df5a85a0e5be57b38b4439b` | CONFIRMED | A0 only; Research Ledger must be rebuildable projection, not runtime authority. |
| `NEW:docs/operations/CURRENT_OPERATIONAL_FRONTIER.md@4c6d41a` | NEW-TOP10 pinned execution base | 2026-08-30 | `git_blob_sha1:0e2a12569f94065e1026062e47498b5cdb582be0` | CONFIRMED | Research lane cannot touch scheduler/publish/production/runtime/config/schema/data mutation. |
| `NEW:app/research/contracts.py@4c6d41a` | NEW-TOP10 pinned execution base | 2026-08-30 | `git_blob_sha1:7deddc03d80e12d8a57e29fc9e991121061c4aa6` | CONFIRMED | Existing canonical JSON, content hash, TrialSpec, intent, receipt validators. |
| `NEW:app/research/run_receipts.py@4c6d41a` | NEW-TOP10 pinned execution base | 2026-08-30 | `git_blob_sha1:4156a42507c12090b7d368b83b435bd2cee0fc26` | CONFIRMED | Existing native runner adapter writes trial specs, intents, attempts and terminal receipts. |
| `NEW:app/research/receipt_store.py@4c6d41a` | NEW-TOP10 pinned execution base | 2026-08-30 | `git_blob_sha1:e553ced87fb8d1c237f474b4b670f0fd214a5739` | CONFIRMED | Existing immutable JSON writer and content-addressed corpus. |
| `NEW:app/research/observation_ingest.py@4c6d41a` | NEW-TOP10 pinned execution base | 2026-08-30 | `git_blob_sha1:86d88898425dcc42e173a4e3774143c2c44f6adb` | CONFIRMED | Existing DuckDB ledger is projection from immutable corpus. |
| `NEW:app/research/legacy_migration.py@4c6d41a` | NEW-TOP10 pinned execution base | 2026-08-30 | `git_blob_sha1:147e812dea4874e6acc9425d15cb083c3ed275f9` | CONFIRMED | Existing fail-closed migration from legacy research artifacts. |
| `NEW:app/research/ranking_provenance_receipt.py@4c6d41a` | NEW-TOP10 pinned execution base | 2026-08-30 | `git_blob_sha1:f6257d74493b0660f164220e16d8cf1c7fe5e366` | CONFIRMED | Existing forward-only ranking provenance receipt; receipt does not grant admission. |
| `NEW:config/research_parameter_catalog.json@4c6d41a` | NEW-TOP10 pinned execution base | 2026-08-30 | `git_blob_sha1:29aa94a1e4da5e6ee1a4f7b7bd209dc0f0552aad` | CONFIRMED | Domain parameter catalog uses `SOLE_AUTHORING_AUTHORITY` and fixed executable/coverage dimensions. |
| OpenLineage Run Cycle `1.52.0` | official docs | retrieved 2026-08-30 | `web_ref:openlineage.io/docs/spec/run-cycle/` | CONFIRMED | Defines `START/RUNNING/COMPLETE/ABORT/FAIL/OTHER`; terminal events end run emission. |
| OpenLineage license | official GitHub repo main | retrieved 2026-08-30 | `web_ref:raw.githubusercontent.com/OpenLineage/OpenLineage/main/LICENSE` | UNKNOWN | Apache-2.0 text retrieved from unpinned `main`; JIT pin before code reuse. |
| MLflow architecture overview | official docs latest | retrieved 2026-08-30 | `web_ref:mlflow.org/docs/latest/self-hosting/architecture/overview/` | UNKNOWN | Latest docs are unpinned; concepts still usable as prior art. |
| MLflow license | official GitHub repo master | retrieved 2026-08-30 | `web_ref:raw.githubusercontent.com/mlflow/mlflow/master/LICENSE.txt` | UNKNOWN | Apache-2.0 text retrieved from unpinned `master`; JIT pin before code reuse. |
| DVC Experiments docs | official docs source on GitHub main | retrieved 2026-08-30 | `web_ref:github.com/treeverse/dvc.org/.../experiment-management/index.md` | UNKNOWN | Docs show experiments as hidden Git refs under `.git/refs/exps`; unpinned `main`. |
| DVC license | official GitHub repo main | retrieved 2026-08-30 | `web_ref:raw.githubusercontent.com/treeverse/dvc/main/LICENSE` | UNKNOWN | Apache-2.0 text retrieved from unpinned `main`; JIT pin before code reuse. |
| Optuna TrialState docs `4.9.0` | official docs | retrieved 2026-08-30 | `web_ref:optuna.readthedocs.io/.../TrialState.html` | CONFIRMED | Defines `WAITING/RUNNING/COMPLETE/PRUNED/FAIL`; unfinished states are WAITING/RUNNING. |
| Optuna license | official GitHub repo master | retrieved 2026-08-30 | `web_ref:raw.githubusercontent.com/optuna/optuna/master/LICENSE` | UNKNOWN | MIT text retrieved from unpinned `master`; JIT pin before code reuse. |
| W3C PROV-O Recommendation | W3C Recommendation | 2013-04-30; retrieved 2026-08-30 | `web_ref:www.w3.org/TR/prov-o/` | CONFIRMED | Stable W3C provenance vocabulary; usable as vocabulary, not RDF subsystem admission. |
| Martin Fowler Event Sourcing | pattern reference | 2005-12-12; retrieved 2026-08-30 | `web_ref:martinfowler.com/eaaDev/EventSourcing.html` | CONFIRMED | Draft pattern reference: event log can rebuild application state. |
| OMI specified commit | prior_art_only donor | requested commit `2d54c5983b8597babd804110f022a5f299e45a9d` | `UNKNOWN_PINNED_BYTES_NOT_RETRIEVED` | UNKNOWN | Network sandbox prevented `git ls-remote`; browser search exposed current AGENTS/product snippets only, not pinned bytes. |

## Decision Matrix

| Source | Decision | Reuse candidate | License / provenance | why_not_less | why_not_more | do_not_absorb |
|---|---|---|---|---|---|---|
| Current AI Core | USE_AS_IS | Authority/admission constraints: prior-art-first, runtime-owned default, no second authority/lifecycle/registry, runtime IDs remain facts. | Pinned AI Core commit `c896cbf`; three confirmed blob refs above. | Less would ignore the governing rebaseline and risk admitting a duplicate local authority. | More would modify AI Core or re-open Runtime Bake-off, which Lane C cannot do. | No AI Core code/config changes; no second AI Core runtime authority, lifecycle, ledger, registry, FSM or database in NEW-TOP10. |
| Existing NEW-TOP10 | ALREADY_EXISTS | Domain-specific Research Spine primitives: canonical TrialSpec/Intent/Attempt/Receipt, immutable JSON corpus, CAS, DuckDB projection, legacy migration, ranking provenance receipt, fixed parameter catalog. | Pinned NEW-TOP10 base `4c6d41a`; local blob refs above. | Less would miss existing domain seams and incorrectly classify the Research Ledger as greenfield. | More would prematurely start A1-A6 implementation or mutate schema/runtime. | Do not replace current corpus/receipt/projection contracts; do not promote DuckDB to canonical truth. |
| OpenLineage | ADAPT | Run lifecycle vocabulary, terminal state discipline, lineage facets, batch/service distinction. | Official docs version `1.52.0`; repo license appears Apache-2.0 from unpinned `main`, so code reuse remains JIT-pinned only. | Less would lose a mature vocabulary for start/terminal events and accumulative lineage. | More would install an OpenLineage backend or make OpenLineage the research authority, which conflicts with the Research Spine invariant. | No backend authority, no external lineage service, no direct schema takeover. |
| MLflow | ADAPT | Metadata/artifact separation, experiment/run concepts, local tracking as reference model. | Official latest docs unpinned; license appears Apache-2.0 from unpinned `master`; NEW-TOP10 already has `mlflow>=2.8` in training dependency group. | Less would ignore existing dependency and useful separation between metadata store and artifact store. | More would make MLflow tracking DB the canonical ledger or require server setup for A0/A1. | No MLflow tracking DB as source of truth; no mandatory MLflow server; no model promotion authority. |
| DVC Experiments | ADAPT | Reproducibility, version provenance, comparison concepts, baseline-to-experiment relation. | Official docs source unpinned `main`; DVC license appears Apache-2.0 from unpinned `main`. | Less would miss strong data-science reproducibility prior art. | More would replace Research Spine identity with hidden Git refs under `.git/refs/exps`. | No hidden Git refs as research identity; no DVC queue as execution control plane. |
| Optuna | ADAPT | Study/Trial/state ontology for attempts and terminal classifications. | Official docs `4.9.0`; license appears MIT from unpinned `master`; NEW-TOP10 already has `optuna>=3.5` in training dependency group. | Less would discard a compact trial-state vocabulary relevant to attempts. | More would import optimizer/search authority into Card A, violating scope locks. | No optimizer admission, no adaptive search, no priority/queue/ranking policy changes. |
| W3C PROV-O | ADAPT | Entity/Activity/Agent and derivation/attribution vocabulary for evidence references. | W3C Recommendation 2013-04-30; stable standards authority. | Less would force local naming for common provenance relations. | More would create RDF/OWL storage/query subsystem without measured need. | No RDF triple store, no ontology engine, no PROV as canonical database. |
| Event Sourcing | ADAPT | Immutable facts plus rebuildable projections; external query responses must be captured at boundary for deterministic rebuilds. | Martin Fowler pattern page dated 2005-12-12; draft pattern reference. | Less would weaken the immutable-evidence/rebuildable-DuckDB invariant. | More would require whole-system event sourcing beyond Card A scope. | No universal event store, no global event bus, no every-subsystem event-sourcing mandate. |
| OMI | ADAPT | Concept-only: market-data provider boundary, canonical observation, resolver/control plane, freshness/source-health semantics, external consumer thinness. | Requested pinned commit not retrieved; current public snippets only support unpinned concept awareness. | Less would ignore relevant Taiwan-market domain prior art and source-health semantics. | More would copy a different product architecture or import OMI backend authority into NEW-TOP10. | No OMI code copy; no DB/provider/control-plane import; no consumer-side provider fallback logic. |

## Structured Claims

### C-AI-CORE-001

| field | value |
|---|---|
| claim_id | `C-AI-CORE-001` |
| subject | Current AI Core authority locks |
| claim | AI Core pinned current authority does not authorize new runtime authority/lifecycle/registry work; it requires waiting for owner or real product evidence and preserves runtime-owned session/worktree/tool-loop boundaries. |
| authority | `AI-CORE:docs/ai-core-backlog.md@c896cbf`; `AI-CORE:PERSONAL-MODE-RUNTIME-SAFETY-PRIOR-ART-20260825.md@c896cbf` |
| scope | A0 Lane C mapping only |
| as_of | 2026-08-30 |
| evidence_ref | `AI-CORE:docs/ai-core-backlog.md@c896cbf`, `AI-CORE:docs/research/PERSONAL-MODE-RUNTIME-SAFETY-PRIOR-ART-20260825.md@c896cbf` |
| evidence_hash | `git_blob_sha1:503244e14c6dcfd15b6e18331149a5320294d5c3`; `git_blob_sha1:20a72976b14c26c1ba9f1a569686cb885b310391` |
| status | CONFIRMED |
| owner | Integrator / Mainline |
| next_action | Use AI Core locks as admission gate for A1; do not create a NEW-TOP10-local AI Core runtime clone. |

### C-AI-CORE-002

| field | value |
|---|---|
| claim_id | `C-AI-CORE-002` |
| subject | Prior-art admission order |
| claim | Any implementation touching execution, authorization, receipt or state mutation must complete prior-art admission and prefer run/wrap/adapt before port/custom. |
| authority | `AI-CORE:rules/24-prior-art-implementation-admission.md@c896cbf` |
| scope | A1-A6 admission gate, not Lane C implementation |
| as_of | 2026-08-30 |
| evidence_ref | `AI-CORE:rules/24-prior-art-implementation-admission.md@c896cbf` |
| evidence_hash | `git_blob_sha1:681962d23f267fda050988a3f28486fd616d8e54` |
| status | CONFIRMED |
| owner | Integrator / Mainline |
| next_action | Require A1 card to explicitly fill reuse candidate, do-not-absorb and why-custom fields before implementation. |

### C-NEW-001

| field | value |
|---|---|
| claim_id | `C-NEW-001` |
| subject | Existing NEW-TOP10 domain specialization |
| claim | NEW-TOP10 already has domain-specific TrialSpec/Intent/Attempt/Receipt contracts, immutable corpus writer, CAS publication, DuckDB projection, legacy migration and ranking provenance receipts. |
| authority | NEW-TOP10 `origin/main@4c6d41a` |
| scope | Existing code evidence only; no runtime mutation |
| as_of | 2026-08-30 |
| evidence_ref | `app/research/contracts.py`, `app/research/run_receipts.py`, `app/research/receipt_store.py`, `app/research/observation_ingest.py`, `app/research/legacy_migration.py`, `app/research/ranking_provenance_receipt.py` |
| evidence_hash | `git_blob_sha1:7deddc03d80e12d8a57e29fc9e991121061c4aa6`; `4156a42507c12090b7d368b83b435bd2cee0fc26`; `e553ced87fb8d1c237f474b4b670f0fd214a5739`; `86d88898425dcc42e173a4e3774143c2c44f6adb`; `147e812dea4874e6acc9425d15cb083c3ed275f9`; `f6257d74493b0660f164220e16d8cf1c7fe5e366` |
| status | CONFIRMED |
| owner | NEW-TOP10 Research Spine |
| next_action | Treat A1-A6 as tightening existing domain spine, not greenfield prior-art import. |

### C-NEW-002

| field | value |
|---|---|
| claim_id | `C-NEW-002` |
| subject | DuckDB role |
| claim | Existing `research_ledger.duckdb` is a rebuildable projection from immutable corpus, not canonical truth. |
| authority | NEW-TOP10 `origin/main@4c6d41a`; Research Spine Backlog |
| scope | Research Ledger admission semantics |
| as_of | 2026-08-30 |
| evidence_ref | `docs/RESEARCH_SPINE_BACKLOG.md`, `app/research/observation_ingest.py` |
| evidence_hash | `git_blob_sha1:9e84f150e37c3b717df5a85a0e5be57b38b4439b`; `git_blob_sha1:86d88898425dcc42e173a4e3774143c2c44f6adb` |
| status | CONFIRMED |
| owner | NEW-TOP10 Research Spine |
| next_action | A1/A4 must preserve delete-and-rebuild semantics; DB cannot become writer authority. |

### C-PRIOR-OPENLINEAGE-001

| field | value |
|---|---|
| claim_id | `C-PRIOR-OPENLINEAGE-001` |
| subject | OpenLineage run lifecycle |
| claim | OpenLineage run-cycle concepts are suitable to ADAPT for START/RUNNING/terminal vocabulary, but not as backend authority. |
| authority | Official OpenLineage docs version `1.52.0`; NEW-TOP10 backlog non-goal |
| scope | Vocabulary and lifecycle comparison only |
| as_of | 2026-08-30 |
| evidence_ref | `https://openlineage.io/docs/spec/run-cycle/`; `docs/RESEARCH_SPINE_BACKLOG.md` |
| evidence_hash | `web_ref:openlineage-run-cycle-1.52.0`; `git_blob_sha1:9e84f150e37c3b717df5a85a0e5be57b38b4439b` |
| status | CONFIRMED |
| owner | Integrator / A1-A4 |
| next_action | Borrow terminal vocabulary and lineage facet idea; do not install backend or replace Research Spine identity. |

### C-PRIOR-MLFLOW-001

| field | value |
|---|---|
| claim_id | `C-PRIOR-MLFLOW-001` |
| subject | MLflow metadata/artifact separation |
| claim | MLflow architecture supports metadata/artifact separation and optional local tracking, but its tracking backend must not become canonical Research Ledger truth. |
| authority | Official MLflow latest architecture docs; NEW-TOP10 pyproject |
| scope | Concept comparison; no dependency/config change |
| as_of | 2026-08-30 |
| evidence_ref | `https://mlflow.org/docs/latest/self-hosting/architecture/overview/`; `pyproject.toml` |
| evidence_hash | `web_ref:mlflow-latest-architecture-retrieved-20260830`; `git_blob_sha1:df71fa8a5058143b0e49d77ce7608e7ac3206a57` |
| status | UNKNOWN |
| owner | Integrator / A1-A4 |
| next_action | Use as concept; JIT pin docs/source before any direct code or required runtime dependency. |

### C-PRIOR-DVC-001

| field | value |
|---|---|
| claim_id | `C-PRIOR-DVC-001` |
| subject | DVC Experiments identity boundary |
| claim | DVC experiment-management concepts are useful for reproducibility and comparison, but hidden Git experiment refs must not replace Research Spine identity. |
| authority | Official DVC docs source on GitHub main; NEW-TOP10 backlog |
| scope | Concept comparison only |
| as_of | 2026-08-30 |
| evidence_ref | `https://github.com/treeverse/dvc.org/blob/main/content/docs/user-guide/experiment-management/index.md`; `docs/RESEARCH_SPINE_BACKLOG.md` |
| evidence_hash | `web_ref:dvc-org-main-experiment-management-retrieved-20260830`; `git_blob_sha1:9e84f150e37c3b717df5a85a0e5be57b38b4439b` |
| status | UNKNOWN |
| owner | Integrator / A1-A4 |
| next_action | Adapt reproducibility vocabulary only; if code reuse is proposed, pin exact DVC/DVC-docs commit first. |

### C-PRIOR-OPTUNA-001

| field | value |
|---|---|
| claim_id | `C-PRIOR-OPTUNA-001` |
| subject | Optuna state ontology |
| claim | Optuna TrialState is suitable to ADAPT as state vocabulary for trials/attempts; optimizer/search authority is out of Card A scope. |
| authority | Official Optuna docs `4.9.0`; NEW-TOP10 pyproject/backlog |
| scope | Ontology comparison only |
| as_of | 2026-08-30 |
| evidence_ref | `https://optuna.readthedocs.io/en/stable/reference/generated/optuna.trial.TrialState.html`; `pyproject.toml`; `docs/RESEARCH_SPINE_BACKLOG.md` |
| evidence_hash | `web_ref:optuna-trialstate-4.9.0`; `git_blob_sha1:df71fa8a5058143b0e49d77ce7608e7ac3206a57`; `git_blob_sha1:9e84f150e37c3b717df5a85a0e5be57b38b4439b` |
| status | CONFIRMED |
| owner | Integrator / A1-A4 |
| next_action | Reuse naming pattern only if it reduces ambiguity; no optimizer import. |

### C-PRIOR-PROV-001

| field | value |
|---|---|
| claim_id | `C-PRIOR-PROV-001` |
| subject | PROV-O vocabulary |
| claim | W3C PROV-O is suitable to ADAPT for Entity/Activity/Agent and derivation/attribution vocabulary, but not as a reason to introduce RDF infrastructure. |
| authority | W3C Recommendation 2013-04-30 |
| scope | Vocabulary comparison only |
| as_of | 2026-08-30 |
| evidence_ref | `https://www.w3.org/TR/prov-o/` |
| evidence_hash | `web_ref:w3c-prov-o-rec-20130430` |
| status | CONFIRMED |
| owner | Integrator / A1-A4 |
| next_action | Prefer lightweight field naming alignment; reject RDF subsystem without measured need. |

### C-PRIOR-EVENT-001

| field | value |
|---|---|
| claim_id | `C-PRIOR-EVENT-001` |
| subject | Event sourcing boundary |
| claim | Event Sourcing supports immutable fact log plus rebuildable projection thinking, but Card A should not expand to whole-system event sourcing. |
| authority | Martin Fowler pattern reference dated 2005-12-12; NEW-TOP10 backlog |
| scope | Pattern comparison only |
| as_of | 2026-08-30 |
| evidence_ref | `https://martinfowler.com/eaaDev/EventSourcing.html`; `docs/RESEARCH_SPINE_BACKLOG.md` |
| evidence_hash | `web_ref:fowler-event-sourcing-20051212`; `git_blob_sha1:9e84f150e37c3b717df5a85a0e5be57b38b4439b` |
| status | CONFIRMED |
| owner | Integrator / A1-A4 |
| next_action | Preserve immutable evidence and projection rebuild; do not create global event bus/store. |

### C-PRIOR-OMI-001

| field | value |
|---|---|
| claim_id | `C-PRIOR-OMI-001` |
| subject | OMI concept-only boundary |
| claim | OMI should remain concept-only prior art for market-data evidence, canonical observation, resolver/control plane and freshness/source-health semantics; pinned commit bytes were not retrieved in this lane. |
| authority | Card-specified OMI commit as prior_art_only; unpinned public search snippets |
| scope | Concept awareness only; no code copy |
| as_of | 2026-08-30 |
| evidence_ref | `lulu930128/open-market-intelligence@2d54c5983b8597babd804110f022a5f299e45a9d`; browser search result for current AGENTS snippets |
| evidence_hash | `UNKNOWN_PINNED_BYTES_NOT_RETRIEVED` |
| status | UNKNOWN |
| owner | Integrator / Lane E if any future OMI teardown is admitted |
| next_action | If Integrator needs OMI-specific claims, fetch/pin the exact commit bytes outside this sandbox or mark OMI details UNKNOWN. |

## Runtime Authority / Lifecycle / Ledger / Registry Risk

| risk | status | decision | evidence |
|---|---|---|---|
| Second AI Core runtime authority | CONFIRMED risk | REJECT | AI Core pinned authority says runtime/session/worktree/tool loop are runtime-owned by default; NEW-TOP10 research lane cannot create runtime mutation. |
| New lifecycle/FSM for missions or research cards | CONFIRMED risk | REJECT | AI Core admission rule forbids duplicate lifecycle/FSM without measured unmet need; Card A is Research Spine evidence, not AI Core runtime. |
| New authority ledger/registry/database | CONFIRMED risk | REJECT | AI Core current backlog blocks new authority ledgers/registries without real product evidence; NEW-TOP10 backlog says DuckDB must be rebuildable projection. |
| Promoting runtime-specific IDs to research authority | CONFIRMED risk | REJECT | AI Core prior-art receipt says runtime-specific IDs remain adapter/runtime facts; NEW-TOP10 must bind domain evidence through immutable spec/receipt, not thread IDs. |
| Importing donor backend/control plane | CONFIRMED risk | REJECT | OpenLineage/MLflow/DVC/OMI backends overlap with authority/projection surfaces; A0 only admits bounded vocabulary/pattern reuse. |

## Domain Specialization Finding

NEW-TOP10 is not trying to build a generic workflow runtime. The existing codebase is already specialized around Taiwan-market quantitative research:

- `config/research_parameter_catalog.json` defines fixed research dimensions and executable/coverage boundaries.
- `app/research/run_receipts.py` binds topic, scenario, dataset hash, ranking source hash, execution profile, development/sealed lineage and terminal receipt.
- `app/research/receipt_store.py` stores immutable JSON and CAS artifacts.
- `app/research/observation_ingest.py` rebuilds DuckDB projection from corpus and records ingestion conflicts/rejections.
- `app/research/legacy_migration.py` treats legacy artifacts as fail-closed migration evidence.
- `app/research/ranking_provenance_receipt.py` locks ranking artifact provenance without granting promotion/admission.

Therefore A1-A6, if admitted, should tighten these domain seams. It should not import a general-purpose lineage/tracking/experiment/event runtime.

## Generic Primitive Candidates For AI Core Upstream

These are upstream candidates only. Lane C does not write `10-upstream-ai-core-proposals.md`.

| candidate | reason | minimum sufficient shape | do_not_absorb |
|---|---|---|---|
| Structured claim/evidence contract helper | A0 lanes repeat the same fields and status taxonomy. | Markdown/JSON schema guidance for `claim_id`, `authority`, `evidence_ref`, `evidence_hash`, status and owner. | No central evidence DB, no runtime writer. |
| Prior-art decision vocabulary helper | Multiple products need `USE_AS_IS/CONFIGURE/WRAP/ADAPT/...` with `why_not_less/why_not_more/do_not_absorb`. | Reusable checklist/template in AI Core docs or skill. | No automatic admission engine or donor registry. |
| Runtime-fact vs domain-authority glossary | Repeated risk that thread IDs, tool status, projections or backend records become authority. | Small glossary plus review questions. | No universal lifecycle FSM. |
| Rebuildable projection invariant template | NEW-TOP10 and AI Core both need "immutable evidence -> rebuildable projection" language. | Contract snippet for projection ownership, rebuild input set, collision behavior and deletion recovery. | No cross-project projection service. |
| Pinned-source retrieval receipt convention | Browser docs and GitHub `main/latest` sources are often unpinned. | Standard fields for exact commit/tag/version, retrieval date, and `UNKNOWN` fallback. | No persistent global source cache unless separately admitted. |

## UNKNOWN / CONFLICT Register

| id | status | subject | impact | next_action |
|---|---|---|---|---|
| `U-OMI-001` | UNKNOWN | OMI pinned commit bytes not retrieved. | OMI-specific detailed claims cannot be CONFIRMED; only concept-only boundary is safe. | Integrator may fetch/pin commit bytes if OMI detail matters. |
| `U-LICENSE-001` | UNKNOWN | OpenLineage/MLflow/DVC/Optuna licenses were observed from unpinned `main/master`. | No direct code copy should be admitted from these repos yet. | JIT pin repo commit/tag and license before `COPY_CODE` or dependency admission. |
| `U-DOCS-001` | UNKNOWN | MLflow/DVC official docs were retrieved from `latest/main`, not immutable doc versions. | Concept-level ADAPT is okay; exact field/schema claims require pinning. | A1/A4 should pin versions if using exact semantics. |
| `CROSS-CONFLICT-001` | CONFLICT not found | Parent Research Spine and AI Core rebaseline appear compatible if Research Ledger stays domain evidence index/rebuildable projection. | No architecture-decision stop required from Lane C. | Integrator should verify against other A0 lanes before A1 admission. |

## Approved Stop Status

| stop condition | lane status |
|---|---|
| governing-authority conflict | NOT_TRIGGERED |
| identity-grain ambiguity | NOT_TRIGGERED |
| terminal-boundary ambiguity | NOT_TRIGGERED |
| required runtime mutation | NOT_TRIGGERED |

Lane C stops with `COMPLETE_FOR_INTEGRATOR_REVIEW`: all required sources were mapped, donor boundaries were recorded, UNKNOWNs were explicit, and no A1-A6 implementation or runtime mutation was started.

## Admission Summary

Card A can proceed only if Integrator accepts the cross-lane evidence that Research Ledger is:

1. a quantitative-research evidence index and rebuildable projection;
2. backed by immutable spec/intent/receipt/artifact evidence;
3. not a second AI Core authority/lifecycle/ledger/registry;
4. not replaceable by direct `USE_AS_IS` OpenLineage/MLflow/DVC/Optuna/PROV/Event Sourcing/OMI without violating domain specialization or authority boundaries.

Lane C verdict:

```text
ADMIT_NARROW_DOMAIN_SPINE_REFINEMENT_IF_A0_BUNDLE_ACCEPTED
REJECT_GENERIC_RUNTIME_OR_BACKEND_IMPORT
UNKNOWN_OMI_PINNED_DETAIL
```

# 10 — Upstream AI Core Proposals

日期：2026-08-30
Execution base：`origin/main@4c6d41a44314beb3592ccdf7a9b43d8fe614ad88`
AI Core pinned authority：`aicore/docs/ai-core-backlog.md@c896cbff126a57384f5f436b80ceaa2e14a22999`
狀態：`PROPOSALS_ONLY / NO_AI_CORE_WRITE / NO_ADMISSION`

這些是由 A0 repeated evidence friction 得出的 upstream evaluation proposals，不表示 AI Core 已有缺口、已接受 scope 或應建立 shared runtime。任何 proposal 都必須回到 AI Core canonical authority 做 equivalence check 與 measured-gap admission。

## Structured proposals

### A0-UPSTREAM-001

| field | value |
|---|---|
| claim_id | `A0-UPSTREAM-001` |
| subject | structured claim/evidence contract helper |
| claim | A0三條 lanes與Integrator重複使用同一組 `claim_id/subject/claim/authority/scope/as_of/evidence_ref/evidence_hash/status/owner/next_action` 欄位；可評估將這個11-field contract收斂為AI Core docs/template helper。 |
| authority | A0 bundle contract；Lane C upstream candidate |
| scope | AI Core docs/template evaluation proposal only |
| as_of | 2026-08-30 |
| evidence_ref | 01–06 structured claims；06 Generic Primitive Candidates |
| evidence_hash | `01=fce6fda213887f5d891f169e96cd8fb8c3a5fe65`; `02=bd695af1ad4af72cdcfd300b431228c2175fed6c`; `03=02db82892a91e6f3f95528717434104b6f365f63`; `04=7c60fc73ec1e8608d28461e47d5fe7b38033346b`; `05=32bde5d5f3553dffbd8aeef6624899f6d12a425c`; `06=f49c5279cf55010eba996579628dddb6050d64ca` |
| status | `UNKNOWN` |
| owner | AI Core canonical backlog owner |
| next_action | 先查AI Core是否已有等價template；只有存在跨專案authoring measured gap才採docs-only最小helper，禁止evidence DB/runtime writer。 |

### A0-UPSTREAM-002

| field | value |
|---|---|
| claim_id | `A0-UPSTREAM-002` |
| subject | prior-art admission vocabulary helper |
| claim | `USE_AS_IS/CONFIGURE/WRAP/ADAPT/COPY_CODE/CUSTOM_REQUIRED/REJECT` 搭配 `why_not_less/why_not_more/do_not_absorb` 能清楚限制 donor promotion；可評估是否已有可重用 AI Core checklist。 |
| authority | Lane C decision matrix；AI Core pinned prior-art rule |
| scope | AI Core checklist evaluation proposal only |
| as_of | 2026-08-30 |
| evidence_ref | 06 Decision Matrix；`AI-CORE:rules/24-prior-art-implementation-admission.md@c896cbf` as recorded in 06 |
| evidence_hash | `06=f49c5279cf55010eba996579628dddb6050d64ca`; `ai_core_blob=681962d23f267fda050988a3f28486fd616d8e54` |
| status | `UNKNOWN` |
| owner | AI Core canonical backlog owner |
| next_action | 先做equivalence check；若已有rule只新增thin mapping，不建立donor registry或automatic admission engine。 |

### A0-UPSTREAM-003

| field | value |
|---|---|
| claim_id | `A0-UPSTREAM-003` |
| subject | runtime fact vs domain authority glossary |
| claim | A0反覆需要區分 runtime IDs、projection receipts、compatibility artifacts、canonical domain evidence與policy authority；可評估AI Core是否需要一份小型glossary/review questions。 |
| authority | Lane A authority/identity maps；Lane C authority-risk review |
| scope | AI Core terminology evaluation proposal only |
| as_of | 2026-08-30 |
| evidence_ref | 01 `A0-AUTH-007`～`009`；02 `A0-ID-002`～`010`；06 Runtime Authority / Lifecycle / Ledger / Registry Risk |
| evidence_hash | `01=fce6fda213887f5d891f169e96cd8fb8c3a5fe65`; `02=bd695af1ad4af72cdcfd300b431228c2175fed6c`; `06=f49c5279cf55010eba996579628dddb6050d64ca` |
| status | `UNKNOWN` |
| owner | AI Core canonical backlog owner |
| next_action | 查現有authority docs是否等價；若不足只補review vocabulary，禁止universal lifecycle/FSM或NEW-TOP10-local AI Core clone。 |

### A0-UPSTREAM-004

| field | value |
|---|---|
| claim_id | `A0-UPSTREAM-004` |
| subject | rebuildable projection invariant template |
| claim | NEW-TOP10以 immutable evidence → rebuildable DuckDB/compatibility projection避免第二套authority；可評估將 projection owner、rebuild inputs、collision/fail-closed與deletion recovery整理成AI Core contract snippet。 |
| authority | Lane A boundary map；Lane C current-capability mapping |
| scope | AI Core contract-template evaluation proposal only |
| as_of | 2026-08-30 |
| evidence_ref | 01 `A0-AUTH-007`；03 `A0-BND-004`～`007`；06 `C-NEW-002` and Generic Primitive Candidates |
| evidence_hash | `01=fce6fda213887f5d891f169e96cd8fb8c3a5fe65`; `03=02db82892a91e6f3f95528717434104b6f365f63`; `06=f49c5279cf55010eba996579628dddb6050d64ca` |
| status | `UNKNOWN` |
| owner | AI Core canonical backlog owner |
| next_action | 先驗證跨專案需求；若採用只做docs/template，不建立shared projection service、DB或event store。 |

### A0-UPSTREAM-005

| field | value |
|---|---|
| claim_id | `A0-UPSTREAM-005` |
| subject | pinned-source retrieval receipt convention |
| claim | Lane C對`latest/main/master` docs與licenses必須保留UNKNOWN，且OMI因lane-local retrieval能力不同產生可用evidence差異；可評估AI Core提供 exact commit/tag/version、retrieval date、blob/content hash與UNKNOWN fallback的receipt convention。 |
| authority | Lane C evidence inventory/UNKNOWN register；Lane B pinned OMI evidence |
| scope | AI Core source-evidence convention proposal only |
| as_of | 2026-08-30 |
| evidence_ref | 06 Evidence Inventory / UNKNOWN Register；05 OMI evidence index |
| evidence_hash | `06=f49c5279cf55010eba996579628dddb6050d64ca`; `05=32bde5d5f3553dffbd8aeef6624899f6d12a425c` |
| status | `UNKNOWN` |
| owner | AI Core canonical backlog owner |
| next_action | 查現有source pinning規則；若有gap只補receipt fields與JIT pin gate，不建立global source cache或網路runtime。 |

## Proposal disposition

所有 proposal 都是 `UNKNOWN`（尚未對 AI Core canonical backlog 做完整 equivalence/admission review），因此本輪不形成 upstream implementation card。推薦順序是先查等價能力，再只吸收有 measured gap 的最小 docs/template slice；不得建立 authority ledger、registry、FSM、database、runtime writer或always-on service。

OMI `lulu930128/open-market-intelligence@2d54c5983b8597babd804110f022a5f299e45a9d` 在本檔仍為 `prior_art_only`，不構成 AI Core 或 NEW-TOP10 authority。

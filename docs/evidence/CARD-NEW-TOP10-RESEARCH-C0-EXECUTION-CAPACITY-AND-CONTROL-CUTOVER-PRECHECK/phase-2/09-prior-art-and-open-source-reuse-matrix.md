# C0 Phase 2 — Prior Art and Open Source Reuse Matrix

## Scope receipt

- Work item: `CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK`
- Phase: `phase-2`
- Candidate parent: `c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba`
- Canonical source SHA: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- Observed at: `2026-09-01T05:47:34Z`
- Boundary: prior-art comparison only。未新增 dependency、未改 pyproject/uv.lock、未安裝套件、未引入 broker/runtime。

## Direct answer

最小 sufficient prior art 是「借概念，不吸收 runtime」。Celery/RQ/Dramatiq/Prefect/APScheduler 都有可參考的 retry、ack/lease、cache isolation、persistent schedule 或 dead-letter pattern，但直接導入會引入 broker、scheduler、worker lifecycle、deployment/ops 或 license review 面。C0 Phase 2 的最小路徑仍是 repo-native claim/lease/receipt extension plus shadow parity。

## Reuse matrix

| Candidate | Version / license observed | Relevant pattern | Decision | Rationale |
|---|---|---|---|---|
| Current repo-native Research Spine | local `pyproject.toml` has no Celery/RQ/Dramatiq/Prefect/APScheduler dependency | immutable receipts, CAS, batch owner, A6 bridge inventory | ADOPT | Already aligned with Card A identity/receipt boundaries; smallest scope. |
| Celery | PyPI latest 5.6.3; BSD-3-Clause source license | retries, late ack for idempotent tasks, broker-backed distributed workers | REJECT_FOR_C1 | Too much runtime/broker surface for C0; useful concept: idempotency before redelivery. |
| RQ | PyPI latest 2.11.0; BSD-2-Clause | Redis/Valkey job queue, job ids, retry limits, TTL/results | REJECT_FOR_C1 | Redis worker dependency and pickle-default security note require ops/security review; useful concept: explicit job id and result TTL. |
| APScheduler | PyPI latest 3.11.3; MIT | persistent job stores, misfire/coalesce, max instances | REJECT_FOR_C1 | Scheduler replacement is out of scope; useful concept: persistent schedule conflict policy and max instances. |
| Prefect | PyPI latest stable `3.8.4`, released/uploaded Aug 25, 2026; Apache-2.0 PyPI/license metadata | task runs, retries, caching, cache isolation, state tracking | REJECT_FOR_C1 | Full orchestration platform is too broad; useful concept: input/source-derived cache key and lock manager for serializable cache. |
| Dramatiq | PyPI latest 2.2.0; LGPL | actor retries, dead-letter queue, broker abstraction, rate limiting | REJECT_FOR_C1 | Broker plus LGPL review is heavier than minimum sufficient; useful concept: poison/dead-letter after retry exhaustion. |

## Minimum sufficient slice

- why_not_less: ignoring prior art would risk designing claim/retry without known failure vocabulary: idempotency, late ack/redelivery, persistent job identity, retry TTL/dead-letter, cache isolation, coalescing.
- why_not_more: importing any full framework would create a second scheduler/worker/runtime/broker boundary, contradicting C0 evidence-only and current L3 personal autonomous constraints.
- do_not_absorb: external broker, distributed workers, full orchestration UI, production scheduler replacement, dependency changes, worker autoscaling, hosted/cloud control plane.

## Claim ledger

### Claim C0P2-OSS-001

```yaml
claim_id: C0P2-OSS-001
claim: The current project dependency manifest does not include Celery, RQ, Dramatiq, Prefect, or APScheduler, so adopting any of them would be a new dependency/runtime decision.
classification: LOCAL_DEPENDENCY_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: pyproject.toml
source_range_or_section: lines 1-48
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: assuming a broker/workflow library is already in scope.
implication: C0 Phase 2 should not add external runtime dependencies.
open_question: future C1 may revisit only with owner-approved measured gap.
owner: Dependency owner / Mainline
```

### Claim C0P2-OSS-002

```yaml
claim_id: C0P2-OSS-002
claim: Celery provides mature distributed task semantics including retries and late acknowledgment guidance for idempotent tasks, but it is a broker-backed task queue framework and direct adoption exceeds minimum C0 scope.
classification: PRIOR_ART_REJECT_RUNTIME_ADOPT_CONCEPT
source_repo: Celery project / PyPI
source_sha_or_version: celery 5.6.3 observed on PyPI; Celery docs stable; GitHub main LICENSE observed 2026-09-01
source_path_or_official_url: https://pypi.org/project/celery/; https://docs.celeryq.dev/en/stable/userguide/tasks.html; https://github.com/celery/celery/blob/main/LICENSE
source_range_or_section: PyPI project metadata; Tasks guide Task.acks_late section; LICENSE top section
observed_at: 2026-09-01T05:47:34Z
confidence: MEDIUM_HIGH
conflict_with: introducing broker-backed workers as C0 evidence-only work.
implication: Borrow idempotency/redelivery caution; do not absorb Celery runtime for C1 candidate.
open_question: none for C0; future dependency review would be separate.
owner: Future C1 design owner
```

### Claim C0P2-OSS-003

```yaml
claim_id: C0P2-OSS-003
claim: RQ provides Redis/Valkey-backed job queues with job ids, retries, TTL/result retention, and worker process isolation, but PyPI and docs highlight Redis/Valkey requirement and pickle-default security considerations.
classification: PRIOR_ART_REJECT_RUNTIME_ADOPT_CONCEPT
source_repo: RQ project / PyPI
source_sha_or_version: rq 2.11.0 observed on PyPI; RQ docs observed 2026-09-01
source_path_or_official_url: https://pypi.org/project/rq/; https://python-rq.org/docs/; https://python-rq.org/docs/results/
source_range_or_section: PyPI project metadata/security/release history; docs CLI Enqueueing; Results TTL section
observed_at: 2026-09-01T05:47:34Z
confidence: MEDIUM_HIGH
conflict_with: adding Redis queue without explicit ops/security admission.
implication: Borrow explicit job identity/TTL/dead-letter vocabulary; reject dependency now.
open_question: no Redis/Valkey ops envelope exists for NEW-TOP10 C1.
owner: Future C1 design owner / security reviewer
```

### Claim C0P2-OSS-004

```yaml
claim_id: C0P2-OSS-004
claim: APScheduler prior art covers persistent job stores, coalescing/misfire behavior, and max instances, but replacing or expanding scheduling is out of C0/C1 admission scope.
classification: PRIOR_ART_REJECT_SCHEDULER_ADOPT_CONCEPT
source_repo: APScheduler project / PyPI
source_sha_or_version: APScheduler 3.11.3 observed on PyPI; docs 3.x/master observed 2026-09-01
source_path_or_official_url: https://pypi.org/project/APScheduler/; https://apscheduler.readthedocs.io/en/3.x/userguide.html; https://apscheduler.readthedocs.io/en/master/userguide.html
source_range_or_section: PyPI metadata/release history; 3.x User Guide job stores/max_instances/misfire sections; master User Guide persistent data stores/coalescing sections
observed_at: 2026-09-01T05:47:34Z
confidence: MEDIUM_HIGH
conflict_with: scheduler mutation or replacement during evidence-only C0.
implication: Borrow coalesce/max-instance language for claim policy; reject scheduler dependency now.
open_question: launchd/fog worker ownership remains current scheduler boundary.
owner: Scheduler owner / future C1 owner
```

### Claim C0P2-OSS-005

```yaml
claim_id: C0P2-OSS-005
claim: Prefect provides workflow task retries, cached task results keyed by inputs/source/run context, and cache isolation with lock manager options, but it is a broad workflow orchestration framework and not minimum sufficient for C1.
classification: PRIOR_ART_REJECT_ORCHESTRATOR_ADOPT_CONCEPT
source_repo: Prefect project / PyPI / docs
source_sha_or_version: Prefect 3.8.4 latest stable observed on PyPI, released/uploaded Aug 25, 2026; Apache-2.0 metadata observed 2026-09-01
source_path_or_official_url: https://pypi.org/project/prefect/; https://docs.prefect.io/v3/concepts/tasks; https://docs.prefect.io/v3/concepts/caching; https://github.com/PrefectHQ/prefect/blob/main/pyproject.toml
source_range_or_section: PyPI project metadata, Key dates, Download files, Release history, License classifier, and source provenance for `prefect-3.8.4`; Tasks concept; Caching cache policies/isolation sections; pyproject license metadata
observed_at: 2026-09-01T05:47:34Z
confidence: MEDIUM
conflict_with: absorbing a full orchestration platform as a small claim/lease fix.
implication: Borrow cache-key/isolation concepts; keep implementation repo-native unless a future measured gap proves otherwise.
open_question: exact latest stable Prefect version should be rechecked again if dependency adoption is ever proposed after 2026-09-01.
owner: Future architecture owner
```

### Claim C0P2-OSS-006

```yaml
claim_id: C0P2-OSS-006
claim: Dramatiq provides actor retries with backoff, dead-letter behavior, broker abstraction, and rate-limiting patterns, but direct adoption requires broker plus LGPL review and is not minimum sufficient.
classification: PRIOR_ART_REJECT_RUNTIME_ADOPT_CONCEPT
source_repo: Dramatiq project / PyPI / docs
source_sha_or_version: dramatiq 2.2.0 observed on PyPI; docs 2.2.0 observed 2026-09-01
source_path_or_official_url: https://pypi.org/project/dramatiq/; https://dramatiq.io/guide.html; https://dramatiq.io/reference.html; https://dramatiq.io/license.html
source_range_or_section: PyPI metadata/release/license; User Guide Error Handling/Message Retries/Dead Letters/Brokers; API Retries; License page
observed_at: 2026-09-01T05:47:34Z
confidence: MEDIUM_HIGH
conflict_with: adding LGPL/broker runtime without explicit dependency/security scope.
implication: Borrow retry exhaustion/dead-letter concepts; reject runtime adoption for C1 candidate.
open_question: none for C0; future license review required before any dependency proposal.
owner: Future C1 design owner / license reviewer
```

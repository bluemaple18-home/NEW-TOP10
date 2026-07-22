# REVIEW-TSKG-MFO-TPEX-01

## Review identity and decision

- reviewed candidate (`HEAD^`): `5a436b1062a8ef6a7ba4908cd6a79f8446dce2c9`
- reviewed candidate's parent: `5a436b1062a8ef6a7ba4908cd6a79f8446dce2c9^`
- review HEAD: `f10b74cc94398412bc7f9793967df51afc2b588c`
- worktree: clean at review start and before review commit
- review type: independent source-governance review; no implementation change
- source decision: `KEEP_BLOCKED`
- review decision: `REVIEW_GO`

`REVIEW_GO` means this review accepts the candidate's fail-closed source-governance conclusion. It does not mean TPEx source approval or adapter authorization. TPEx ingestion, redistribution, and downstream TPEx venue promotion remain blocked.

## Findings

- [P2] Candidate verification lineage fields are stale or from another worktree - `docs/evidence/TSKG-MFO-TPEX-01/verification.md:4-5`
  The candidate evidence records `candidate base` `ecac54440d0eae95ee7aefb830f06da3107e2aac` and `requested base ancestor` `558a04f82a9ff164ae6a95a126f8a354bd33ebab`, while the reviewed candidate is the parent of review HEAD `f10b74c...` and the task explicitly fixes the reviewed candidate to `5a436b...`. The new review evidence binds the decision and verification to the actual reviewed SHA; the stale fields should be corrected in a future evidence repair, but they do not overturn the independently reproduced `KEEP_BLOCKED` decision.

No P0/P1 source-governance finding was found. No adapter, source policy mutation, Yuanta secure payload, credential, token, or production-path change was introduced by the candidate.

## Official primary-source receipts (read-only, 2026-07-22 Asia/Taipei)

| Receipt | What was verified | Boundary |
|---|---|---|
| https://www.tpex.org.tw/openapi/ | TPEx OpenAPI 1.0.0 landing/catalog lists `GET /tpex_3insti_daily_trading`, schema `tpex_3insti_daily_trading`, and the identity 「上櫃股票三大法人買賣明細資訊」. | Catalog identity proves source identity only; it does not prove permission, rate, retention, or redistribution. |
| https://www.tpex.org.tw/openapi/swagger.json | Official machine-readable specification locator is linked by the catalog. | Not opened or downloaded; no request/response, auth, rate, or media contract was inferred. |
| https://www.tpex.org.tw/zh-tw/mainboard/trading/major-institutional/summary/day.html | Official summary page exposes date query and CSV export, and identifies the TPEx institutional report. | Interactive/CSV controls are not automation permission. |
| https://www.tpex.org.tw/zh-tw/mainboard/trading/major-institutional/detail/day.html | Official detail page exposes category/date query and CSV export; it states the data is based on original same-day trades. | Does not state batch automation, rate, retention, revision/deletion, or downstream redistribution terms. |
| https://www.tpex.org.tw/zh-tw/gtsm_disclaimer.html | Website terms prohibit downloading software/data through automation, scripts, spiders, crawlers, or extraction programs unless TPEx agrees to the method or gives consent; reuse/distribution also requires written permission except explicitly authorized government-open-data material. | Supports `automation permission=NOT_FOUND` and blocked redistribution; no consent artifact exists. |
| https://www.tpex.org.tw/storage/regular_system/%E6%94%B6%E5%B8%82%E5%BE%8C%E4%BA%A4%E6%98%93%E8%B3%87%E6%96%99%E4%BD%BF%E7%94%A8%E6%94%B6%E8%B2%BB%E8%BE%A6%E6%B3%95%28V1.31%E7%89%88%29.pdf?t=202312221705 | Official fee document lists S35 `STKBIG3DDTLN.TXT` as the daily/weekly/monthly institutional detail file; it requires application/order consent, has a monthly fee, and restricts reproduction, transmission, and distribution without authorization. | Paid S35 is not an open-data fallback; no purchase, registration, terms acceptance, or credential use occurred. |
| https://data.gov.tw/license | OGL applies to open data explicitly released by a provider, grants reuse for that released data, and requires attribution with release name/version. | General OGL cannot be expanded to an unmatching TPEx API/report or paid S35 product. |

## Governance field conclusions

| Field | Review result |
|---|---|
| dataset identity / owner | `FOUND`: TPEx operation/schema identity; publisher is Taipei Exchange. |
| machine-readable source | `FOUND`: official catalog and OAS locator; no endpoint call or OAS download. |
| automation permission | `NOT_FOUND`: catalog/report existence is not consent; website terms require TPEx-agreed method or consent. |
| rate / concurrency / retry / UA | `NOT_FOUND`; no load or rate test performed. |
| retention / redaction / deletion | `NOT_FOUND`; no free API operational retention/deletion contract found. |
| revision / correction | `NOT_FOUND`; report notes original same-day trade statistics but no target-specific revision/backfill contract. |
| redistribution / derivative | `BLOCKED`: website terms and paid S35 terms do not authorize the proposed downstream use. |
| owner / review / expiry | `NOT_FOUND` for a specific API-use approval and policy artifact. |

Therefore `KEEP_BLOCKED` is evidence-backed and must not be rewritten as source GO.

## Reproducible verification

Commands were run with the prescribed existing project `.venv/bin/python`; no `uv` cache, dependency installation, networked test, endpoint, or dataset was used.

| Check | Result |
|---|---|
| `python -m pytest tests/test_tskg_twse_t86.py tests/test_tskg_mfo01.py` | `17 passed` |
| `python -m py_compile app/tskg/source_policy.py app/tskg/twse_t86.py app/tskg/flow_observation.py` | passed |
| `git diff --check` | passed |
| reviewed candidate first-parent file set | 4 files, all within original implementation-card allowlist |
| candidate runtime/source-policy/adapter mutation | none |
| Yuanta secure payload / credential / token / secret scan of candidate paths | none found |
| host-specific path scan of candidate evidence | only the pre-existing candidate command contains its prescribed local interpreter path; no new shared command was added |

## Scope and prohibited actions

This review did not call a TPEx data endpoint, download a dataset or OAS file, register, purchase S35, accept terms, use credentials, create an adapter, access Yuanta encrypted material, or modify runtime/config/source policy. Only this review evidence and review status are added by the review work.

## Final status

`REVIEW_GO` with final source decision `KEEP_BLOCKED`.

Required unlock remains a TPEx/source-compliance owner artifact naming the exact operation/media, method/path, authentication, rate/concurrency, UA, update/correction, retention/deletion, redistribution/derivative scope, owner, policy version, review date, and expiry. Until then, no live TPEx connector or TPEx downstream promotion is authorized.

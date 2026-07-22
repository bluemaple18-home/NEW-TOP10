# TSKG-MFO-TPEX-01 verification

## Result

- candidate base: `ecac54440d0eae95ee7aefb830f06da3107e2aac`
- requested base ancestor: `558a04f82a9ff164ae6a95a126f8a354bd33ebab`
- access date: `2026-07-22` (Asia/Taipei)
- source gate: `KEEP_BLOCKED`
- adapter: not implemented; live fetch remains disabled by absence of approved source policy

## Evidence collected

1. TPEx official OpenAPI catalog lists `GET /tpex_3insti_daily_trading`, schema `tpex_3insti_daily_trading`, described as 上櫃股票三大法人買賣明細資訊.
2. TPEx official interactive pages expose date/category queries and CSV controls for institutional reports, but do not state batch automation permission.
3. TPEx website terms prohibit automated/script/crawler extraction unless performed by a TPEx-approved method or with TPEx consent; they also reserve reproduction/distribution rights except for explicitly authorized government-open-data releases.
4. TPEx official after-hours data fee schedule identifies S35 `STKBIG3DDTLN.TXT` as the security-level institutional detail file. It requires application/subscription and states that data must not be given or resold; the attached terms restrict reproduction, transmission and distribution without authorization.
5. Government OGL page defines open data as data explicitly released by a provider under the license and requires an identifiable release/version; no matching TPEx dataset was found in this read-only discovery.

## Negative evidence / scope

- No data endpoint was opened or called.
- No OAS JSON was downloaded; only the official catalog/index identity was inspected.
- No rate/load test, registration, purchase, acceptance of terms, credential use, or external write occurred.
- Missing automation permission, rate/concurrency, retention, correction/revision, deletion, redistribution and review/expiry evidence is treated as `NOT_FOUND`, not inferred from endpoint existence or robots behavior.

## Verification commands

The card has no TPEx implementation or adapter tests to run because the source gate is blocked. Existing contracts were checked with the prescribed local interpreter:

```text
/Users/mattkuo/TOP10new/.venv/bin/python -m pytest tests/test_tskg_twse_t86.py tests/test_tskg_mfo01.py
/Users/mattkuo/TOP10new/.venv/bin/python -m py_compile app/tskg/source_policy.py app/tskg/twse_t86.py app/tskg/flow_observation.py
git diff --check
```

Results:

- `pytest tests/test_tskg_twse_t86.py tests/test_tskg_mfo01.py`: **17 passed**.
- `py_compile app/tskg/source_policy.py app/tskg/twse_t86.py app/tskg/flow_observation.py`: **passed**.
- `git diff --check`: **passed**.
- allowlist scan: changed files are limited to the dossier, evidence and `.work/TSKG-MFO-TPEX-01/` paths allowed by the card; no secure/Yuanta payload, credential, token or secret was added.

The prescribed external Python interpreter was used; its machine-specific absolute path is intentionally omitted from this cross-machine evidence. No empty TPEx glob was used.

## Official locators

- https://www.tpex.org.tw/openapi/
- https://www.tpex.org.tw/openapi/swagger.json
- https://www.tpex.org.tw/zh-tw/mainboard/trading/major-institutional/summary/day.html
- https://www.tpex.org.tw/zh-tw/mainboard/trading/major-institutional/detail/day.html
- https://www.tpex.org.tw/zh-tw/gtsm_disclaimer.html
- https://www.tpex.org.tw/storage/regular_system/%E6%94%B6%E5%B8%82%E5%BE%8C%E4%BA%A4%E6%98%93%E8%B3%87%E6%96%99%E4%BD%BF%E7%94%A8%E6%94%B6%E8%B2%BB%E8%BE%A6%E6%B3%95%28V1.31%E7%89%88%29.pdf?t=202312221705
- https://data.gov.tw/license

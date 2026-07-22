# REPAIR-UI-MFR-01-02 verification snapshot

- RED: compact `20260717` and ISO-week `2026-W29-5` returned 200 before repair.
- GREEN: both return 422 `INVALID_AS_OF_DATE` after exact ASCII lexical gating.
- GREEN: canonical `2026-07-17` remains 200.
- Matrix: 51/51.
- Tests: 15 passed.
- Browser radar smoke: passed.

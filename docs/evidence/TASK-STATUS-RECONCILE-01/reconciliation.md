# TASK-STATUS-RECONCILE-01 Evidence Matrix

| Chain | Previous stale state | Reconciled state | Governing evidence |
|---|---|---|---|
| NEXT-WAVE-01 | `CARD_DRAFTED` | `DISPATCH_COMPLETED` | six delivered child chains and their acceptance evidence |
| SHADOW-RUN-01 | no status | `INTEGRATED` | `docs/evidence/SHADOW-RUN-01/acceptance.md` |
| REVIEW-SHADOW-RUN-01 | no status | `REVIEW_GO` | `docs/evidence/REVIEW-SHADOW-RUN-01/review.md` |
| FEATURE-PROMOTE-02 | `CARD_DRAFTED` | `INTEGRATED_NO_GO` | `docs/evidence/FEATURE-PROMOTE-02/acceptance.md` |
| REVIEW-FEATURE-PROMOTE-02 | `READY_FOR_INDEPENDENT_REVIEW` | `REVIEW_GO` | `docs/evidence/REVIEW-FEATURE-PROMOTE-02/final-re-review.md` |
| REPAIR-FEATURE-PROMOTE-02-01/02 | `READY_FOR_REPAIR` | `REPAIR_COMPLETED` | final reviewed candidate `1a08f385...` |
| TSKG-MFO-GRAPH-01 | `CARD_DRAFTED` | `INTEGRATED_SHADOW_ONLY` | `docs/evidence/TSKG-MFO-GRAPH-01/acceptance.md` |
| REVIEW-TSKG-MFO-GRAPH-01 | `READY_FOR_INDEPENDENT_REVIEW` | `REVIEW_GO` | `docs/evidence/REVIEW-TSKG-MFO-GRAPH-01/re-review.md` |
| REPAIR-TSKG-MFO-GRAPH-01-01 | `READY_FOR_REPAIR` | `REPAIR_COMPLETED` | reviewed repair candidate `6115a3c...` |
| TSKG-MFO-THEME-01 | `CARD_DRAFTED` | `INTEGRATED` | `docs/evidence/TSKG-MFO-THEME-01/acceptance.md` |
| REVIEW-TSKG-MFO-THEME-01 | `READY_FOR_REVIEW` | `REVIEW_GO` | `docs/evidence/REVIEW-TSKG-MFO-THEME-01/re-review.md` |
| REPAIR-TSKG-MFO-THEME-01-01 | `REPAIR_READY` | `REPAIR_COMPLETED` | reviewed repair candidate `71c02aa...` |
| TSKG-MFO-TPEX-01 | `READY_FOR_REVIEW_V2` | `INTEGRATED_CURRENT_DAY_ONLY` | `docs/evidence/TSKG-MFO-TPEX-01/verification_v2.md` and current closeout |
| REVIEW-TSKG-MFO-TPEX-01 | `READY_FOR_REVIEW` | `REVIEW_GO` | `docs/evidence/REVIEW-TSKG-MFO-TPEX-01/review.md` |
| UI-MFR-01 | `CARD_DRAFTED` | `INTEGRATED_READ_ONLY` | `docs/evidence/UI-MFR-01/acceptance.md` |
| REVIEW-UI-MFR-01 | `READY_FOR_INDEPENDENT_REVIEW` | `REVIEW_GO` | `docs/evidence/REVIEW-UI-MFR-01/final-re-review-02.md` |
| REPAIR-UI-MFR-01-01/02 | `READY_FOR_REPAIR` | `REPAIR_COMPLETED` | final reviewed candidate `88d6125...` |
| YUANTA-WIN-AUTOMATION-01 | no status | `INTEGRATED_EXPERIMENTAL_STATIC` | `docs/evidence/YUANTA-WIN-AUTOMATION-01/acceptance.md` |
| REVIEW-YUANTA-WIN-AUTOMATION-01 | no status | `REVIEW_GO` | `docs/evidence/REVIEW-YUANTA-WIN-AUTOMATION-01/re-review-01.md` |
| REPAIR-YUANTA-WIN-AUTOMATION-01-01 | no status | `REPAIR_COMPLETED` | reviewed repair candidate `6c2d0cea...` |

## Preserved non-terminal research states

- `CHIP-OVERLAY-SHADOW-01`：`WAITING_FOR_NEW_OOS_DATES`
- `EVENT-OVERLAY-SHADOW-01`：`WAITING_FOR_NEW_OOS_DATES`
- `RESEARCH-FUNDAMENTAL-READINESS-01`：`COMPLETED_BLOCKED_DATA`
- `VOLUME-CLIMAX-WARNING-SHADOW-01`：`COMPLETED_MONITORING`

這些狀態沒有被改寫成 promotion 或 production-ready。

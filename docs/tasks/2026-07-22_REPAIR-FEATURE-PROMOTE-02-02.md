---
card_id: REPAIR-FEATURE-PROMOTE-02-02
chain_id: TOP10-NEXT-WAVE-20260722
status: READY_FOR_REPAIR
type: bounded-repair
repair_generation: 2
repair_limit: 2
repair_1_candidate: 0079370cf4e6d46fe718579de4a78fb3c5c3ac73
re_review_no_go_sha: 76b066bfd02ff1e1cd88d55da1553562f29adece
original_reviewer_thread: 019f8979-2084-79e3-a10b-8a15c4cea18c
reasoning: medium
thickness: strict
---

# REPAIR-FEATURE-PROMOTE-02-02

Repair 2/2。只修原 Reviewer fresh probe 的一個新 P1；不得建立 Repair 3。

## Fixed repair

Builder 必須在判定 evidence present／GO 前驗證 freshness semantics：

- `as_of` 與日期區間為嚴格 ISO 日期／UTC contract；拒絕未來日期、反向區間與不可能日期。
- 依 evidence kind 的固定 maximum age／window contract 判定 stale；不可依本機 wall-clock 漂移，decision 必須有明確 `decision_as_of` 輸入並納入 artifact/hash。
- Builder 與 verifier 共用或等價重算同一 freshness contract；future/stale evidence 在 builder 即視為 missing/invalid，實際 decision 保持 NO_GO。
- synthetic complete GO positive control 固定 decision_as_of 與合法 freshness，只留測試暫存。

## Required RED → GREEN

- 原 Reviewer fresh probe 的 `as_of=2999-01-01` builder GO 先 RED，再 GREEN。
- future、stale、invalid date、reversed range、decision_as_of tamper、timezone boundary、exact max-age boundary 與 over-boundary tests。
- 原 Repair 1 adversarial probes 全部維持 GREEN。
- 真實 repo 仍 `NO_GO`、12 missing、Graph RISK、TPEx KEEP_BLOCKED。

## Allowlist

- `scripts/build_feature_promotion_decision.py`
- `scripts/verify_feature_promotion_decision.py`
- `tests/test_feature_promotion_decision.py`
- `docs/evidence/REPAIR-FEATURE-PROMOTE-02-02/**`
- `.work/REPAIR-FEATURE-PROMOTE-02-02/**`

不得修改既有 implementation/review/Repair 1 evidence、ranking/model/runtime/daily/deploy 或建立假 promotion evidence。

完成後跑原與 fresh probes、全部 promotion tests、builders/verifiers、py_compile、diff/allowlist/privacy/non-mutation，提交並 push fixed candidate。不得自行 Review/merge。

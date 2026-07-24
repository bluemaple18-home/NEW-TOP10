---
card_id: REPAIR-FEATURE-PROMOTE-02-01
chain_id: TOP10-NEXT-WAVE-20260722
status: REPAIR_COMPLETED
type: bounded-repair
repair_generation: 1
candidate_sha: e057ff9e5256091c7825251c7a9e7e43ed324ebe
review_evidence_sha: 86ec0e2
original_reviewer_thread: 019f8979-2084-79e3-a10b-8a15c4cea18c
reasoning: medium
thickness: strict
---

# REPAIR-FEATURE-PROMOTE-02-01

只修 `docs/evidence/REVIEW-FEATURE-PROMOTE-02/review.md` 的兩個 P1；目前 decision 必須維持 `NO_GO`，不得製造缺失 promotion evidence。

## Fixed repairs

1. 建立 closed、versioned evidence schema：每類 evidence 需驗證種類、decision/verdict、candidate/base/data SHA binding、universe/date/cost identity、metrics/thresholds、freshness/as-of、source file SHA；不能只看檔名存在。
2. Verifier 對 top-level/rows/items closed schema fail-closed：拒絕 duplicate/unknown/missing/type、absolute/traversal/out-of-repo/symlink、pattern drift、wrong SHA、wrong candidate/base/data identity、NO_GO review、stale manifest、tampered decision/hash；任何錯誤只回 typed FAILED，不拋未處理例外。

## RED → GREEN

- 原 Reviewer `adversarial_probes.py` 先完整重現 RED。
- 補合法完整 evidence set 的 synthetic GO positive control，但不得提交為真實 promotion evidence，也不得讓本卡實際 decision 變 GO。
- 對每個 required evidence kind 補 placeholder/semantic mismatch/identity/freshness negative controls。
- 當前 repo 缺 required evidence 時 builder/verifier 必須 deterministic `NO_GO`，Graph P2 與 TPEx KEEP_BLOCKED attribution 保留。

## Allowlist

- `scripts/build_feature_promotion_decision.py`
- `scripts/verify_feature_promotion_decision.py`
- `tests/test_feature_promotion_decision.py`
- `docs/evidence/REPAIR-FEATURE-PROMOTE-02-01/**`
- `.work/REPAIR-FEATURE-PROMOTE-02-01/**`

不得修改原 implementation/review evidence、RankingPolicy、weights、model/runtime、daily path、deploy 或 ignored artifacts 以偽造 GO。

## Verification

重跑原 tests、原 Reviewer probes、fresh schema/semantic probes、builder/verifier、py_compile、diff/allowlist/privacy/non-mutation。Python 只用 `<repo-root>/.venv/bin/python`。

提交並 push repair candidate；回覆完整 SHA、RED→GREEN、schema/binding/freshness 契約與實際 `NO_GO` artifact hash。不得自行 Review 或 merge。

---
card_id: REVIEW-FEATURE-PROMOTE-02
chain_id: TOP10-NEXT-WAVE-20260722
status: REVIEW_GO
final_review_sha: 6f92520047abbd73d1ba6875a9c75440316cec28
type: independent-promotion-review
reviewed_candidate: e057ff9e5256091c7825251c7a9e7e43ed324ebe
base_sha: b5a5e6394fa1bdb4f82124ffa5e1694844605f28
reasoning: medium
thickness: strict
---

# REVIEW-FEATURE-PROMOTE-02

角色：獨立 Reviewer，只審不修。固定 reviewed range：
`b5a5e6394fa1bdb4f82124ffa5e1694844605f28..e057ff9e5256091c7825251c7a9e7e43ed324ebe`。

只能新增 `docs/evidence/REVIEW-FEATURE-PROMOTE-02/**` 與
`.work/REVIEW-FEATURE-PROMOTE-02/**`；不得修改 candidate、ranking、model、runtime 或 deploy。

## Required review

- Reviewer 必須從 repo 實體證據重算當前 decision，不採信文案或 artifact。
- 驗證 sealed OOS、walk-forward、same universe/date/cost、leakage、stability、turnover、drawdown、concentration、late-data、data/candidate manifest 與 code Review 缺失時必為 NO_GO。
- 驗證 builder/verifier 不是只以檔名存在就允許 GO；內容 schema、SHA binding、candidate/data identity、metric semantics、review verdict 與 freshness 必須 fail-closed。以 reviewer-owned synthetic placeholder／tampered／wrong SHA／NO_GO review probes 驗證。
- 驗證 top-level closed schema、unknown/missing/type/duplicate ID、path traversal/symlink/out-of-repo、manifest drift、artifact tamper、decision flip 都 fail closed。
- 驗證 Graph P2、TWSE-only/TPEx KEEP_BLOCKED attribution 不可移除或偽裝 full coverage。
- 沿 diff/import 證明無 RankingPolicy、weight、production runtime、daily path 或 deploy mutation。

## Commands

執行卡片原 tests/verifiers/builders，另跑 reviewer-owned adversarial probes、py_compile、allowlist/privacy/non-mutation 與 `git diff --check`。Python 使用 `<repo-root>/.venv/bin/python`。

## Verdict

- `GO`：當前 NO_GO 重算正確，且 decision contract 對未來 GO 路徑仍 fail-closed，無 P0/P1。
- `NO_GO`：任何 placeholder/tamper/identity/semantic bypass 可產生 GO，或當前缺 evidence 被誤判。
- `BLOCKED`：僅客觀環境阻斷。

提交單一 review evidence commit，回報完整 SHA、findings 與 Overall verdict。不得自行 Repair 或 merge。

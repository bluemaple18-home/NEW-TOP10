---
id: REVIEW-REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPLACEMENT
status: CARD_DRAFTED
type: review_replacement
chain_id: REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01
ownership: independent_reviewer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
reviewer_identity_continuity: 019fa367-851b-7402-bec7-6b11b68249de
replacement_reason: 原 Reviewer task 連續三次 systemError
base_sha: 759dd7c76bf7ea3766fb67670c501be3a24ef2c4
candidate_sha: b1e3dc191527c24a5d3f5d80b975a81ad8a46543
evidence_path: docs/evidence/REVIEW-REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPLACEMENT/
---

# REVIEW-REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPLACEMENT

延續原 Reviewer 的同一 findings ledger；不得重置 Repair generation。只複審 Repair-2
對 F-02 的修復及整條 public-path trust boundary。

必查：

- forged dataset lineage → fail closed
- forged sealed dates/date hash/slice hash → 各自 fail closed
- 合法 81/720、242/720、available-data canary 行為不變
- targeted、verifier、full suite、production hashes、diff-check
- candidate 不得被 Reviewer 修改

固定 base/candidate 如 frontmatter。若 `GO`，提交 review-only evidence；若 `NO_GO`，
必須標記 `BLOCKED / REVIEW_REPAIR_LIMIT`。不得 merge、push、deploy、acceptance。

Worktree 必須獨立且 clean；replacement thread 建立後回寫正式 receipt。

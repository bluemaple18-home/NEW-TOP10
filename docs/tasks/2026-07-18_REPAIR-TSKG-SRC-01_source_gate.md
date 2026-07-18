---
card_id: REPAIR-TSKG-SRC-01
chain_id: TSKG-SRC
title: Repair Source Gate fail-open findings F-01 to F-03
status: DELIVERED_CANDIDATE
type: repair
owner: Codex 主線
assignee: independent repair thread
thickness: standard
risk: high
model: gpt-5.5
reasoning: high
model_reason: 三個 P1 finding 都在來源存取安全邊界，包含 public false approval、raw JSON ambiguity 與 Unicode traversal；範圍明確但回退成本高
source_kind: commit
base_candidate_sha: bcbf773f8dbee51e84488b1ea3c11fabbad7a28a
review_commit: 31715802f794f411986abdebb6f368ce31b35834
reviewer_thread: 019f75e7-4703-72f0-bdf5-67e8401acbd9
source_branch: codex/repair-tskg-src-01
mainline_dispatcher: TSKG root thread
evidence_path: docs/evidence/REPAIR-TSKG-SRC-01/repair.md
---

# REPAIR-TSKG-SRC-01：Repair F-01～F-03

## Fixed input

- Base candidate：`bcbf773f8dbee51e84488b1ea3c11fabbad7a28a`。
- Review：`31715802f794f411986abdebb6f368ce31b35834`，verdict `REVIEW_NO_GO`。
- 本卡只能修復下列三個既有 P1 findings；不得修改 reviewer evidence，不得擴增新的 ingestion/crawler 功能。

## Findings to repair

### F-01：generic mapping 可製造 PUBLIC + APPROVED

- `SourcePolicyRegistry.from_mapping` 可將 synthetic approved policy 改成 `PUBLIC/APPROVED`，preflight 仍呼叫 reader。
- 在 OQ-SRC-01 未解除期間，現有 contract 必須一律拒絕 `source_class=PUBLIC` 且 `decision_status=APPROVED`，不論來自 fixture、file 或 in-memory mapping。
- 未來 public approval 必須由另一張 source-owner approval 卡引入獨立 immutable decision artifact／constructor；本卡不得自行設計或批准。

### F-02：duplicate JSON members 被 last-wins 吞掉

- `from_file` 必須在 mapping 建構前，以遞迴 duplicate-member rejecting parser 讀 raw JSON。
- registry 頂層與任意 nested policy/object 的 duplicate key 都要 fail loud，包含互斥 `source_class`／`decision_status`。
- `from_mapping` 無法恢復 raw duplicate provenance；文件與測試須明確限制此邊界，不得宣稱 mapping path 可偵測 duplicate JSON。

### F-03：Unicode compatibility traversal

- request path 在 allowlist matching 前只允許單一保守 canonical representation。
- fullwidth dot/slash、NFKC 後改變的 compatibility characters、control characters、backslash、encoded separator/traversal、absolute URL、query/fragment、double slash 與 `.`／`..` segment 都必須 fail closed。
- 驗證、matching、receipt 與 reader callback 必須使用同一 canonical path；不可 gate 一個字串、reader 另一個字串。

## Allowed scope

- `app/tskg/source_policy.py`
- `tests/test_tskg_src01.py`
- `docs/evidence/REPAIR-TSKG-SRC-01/repair.md`
- `docs/evidence/TSKG-SRC-01/verification.md`（只更新修復後可重現結果）
- `docs/tasks/2026-07-18_REPAIR-TSKG-SRC-01_source_gate.md`
- 原 `docs/tasks/2026-07-18_TSKG-SRC-01_source_gate.md`（只更新 Result/test count，不改 scope）

## Forbidden scope

- 不修改 `docs/evidence/REVIEW-TSKG-SRC-01/review.md` 或 Review 卡。
- 不連外、不下載 terms/robots、不新增 dependency、不建立真實 source approval。
- 不修改 fixture 為 public approved；不建立 RawArtifact/claim/Evidence/relationship。
- 不修改 `app/api/main.py`、requirements/lockfile、production runtime 或 SLC-01 code/fixture。
- 不重構成 crawler framework，不處理 review 未列的新功能。

## TDD and acceptance

1. 先新增能在 base candidate 重現 F-01～F-03 的 public-behavior tests並保存 RED：
   - custom mapping `PUBLIC+APPROVED` → rejected，reader 0。
   - duplicate keys at registry/policy/nested object → rejected before registry construction。
   - fullwidth／NFKC／control／encoded traversal matrix → rejected，reader 0。
2. 最小修復後重跑：
   - `<repo-root>/.venv/bin/python -m unittest tests.test_tskg_src01 tests.test_tskg_slc01 -v`
   - `<repo-root>/.venv/bin/python -m py_compile app/tskg/source_policy.py tests/test_tskg_src01.py`
3. 重跑原 reviewer 51-case matrix 或等價 probes，必須 51/51；另證明 F-01/F-02 exploit 不再成立。
4. 驗證 exact changed-file allowlist、prohibited/network/dependency/production/host-path scan、`git diff --check`、post-commit clean。
5. Repair evidence 逐 finding 記錄 root cause、change、RED、GREEN、reader call count、remaining boundary。

## Delivery and re-review

- 交付 successor candidate commit，回報完整 SHA/parent、changed files、test counts、probe matrix、reader-call proof、evidence、blockers。
- 只能回 `DELIVERED_CANDIDATE`；不得自行標 findings resolved、review go、accepted 或 integrated。
- 完成後必須回原 reviewer thread `019f75e7-4703-72f0-bdf5-67e8401acbd9` re-review；不得更換 reviewer。
- OQ-SRC-01 未解除、沒有 public source approved、SLC-02 仍 blocked。

## Result

`DELIVERED_CANDIDATE`

- Fixed base candidate：`bcbf773f8dbee51e84488b1ea3c11fabbad7a28a`。
- Review：`31715802f794f411986abdebb6f368ce31b35834`。
- Successor parent：`717e1c6dffedf254661a12ab41b1092bfae948d9`。
- TDD：focused RED `3 tests / 9 failures`；focused GREEN `3/3`。
- Regression：`17` SRC + `22` SLC = `39/39`；compile PASS。
- Probes：`51/51`；F-01/F-02 exploits `3/3 BLOCKED`；10 denied requests
  reader `0` call。
- Evidence：`docs/evidence/REPAIR-TSKG-SRC-01/repair.md`。
- Blocker：OQ-SRC-01 未解除，沒有 public source approved，SLC-02 仍 blocked。

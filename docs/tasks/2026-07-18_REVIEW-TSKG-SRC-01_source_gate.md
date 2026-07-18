---
card_id: REVIEW-TSKG-SRC-01
chain_id: TSKG-SRC
title: Independent review of fail-closed Source Gate
status: REVIEW_GO
type: review
owner: Codex 主線
assignee: independent reviewer thread
thickness: standard
risk: high
model: gpt-5.5
reasoning: high
model_reason: 來源治理 gate 涉及 fail-open、安全路徑與未來外部存取邊界；需獨立檢查完整 diff、負向測試與規格雙軸
source_kind: commit
base_sha: 4f0470e133b763d5d5c5a232acddf3ab2bc94de8
candidate_sha: bcbf773f8dbee51e84488b1ea3c11fabbad7a28a
reviewed_sha: 2d81414185446e83a34df28c37f54989515d7f76
original_reviewed_sha: bcbf773f8dbee51e84488b1ea3c11fabbad7a28a
initial_review_commit: 31715802f794f411986abdebb6f368ce31b35834
repair_parent_sha: 717e1c6dffedf254661a12ab41b1092bfae948d9
re_review_round: 1
source_branch: codex/review-tskg-src-01
mainline_dispatcher: TSKG root thread
implementation_thread: 019f75d7-093b-7ef2-a556-2b20673c5b40
worktree_mode: platform-managed-independent-worktree
evidence_path: docs/evidence/REVIEW-TSKG-SRC-01/review.md
---

# REVIEW-TSKG-SRC-01：Independent Source Gate Review

## Review boundary

- 固定 base：`4f0470e133b763d5d5c5a232acddf3ab2bc94de8`。
- 固定 candidate：`bcbf773f8dbee51e84488b1ea3c11fabbad7a28a`。
- 完整閱讀 candidate diff、TSKG-SRC-01 卡、TSKG v1.1 source governance／AC-10／OQ-SRC-01，以及 SLC-01 public contracts。
- Review 只可新增／更新本卡與 `docs/evidence/REVIEW-TSKG-SRC-01/review.md`；不得修改 candidate code、fixture、tests 或既有 evidence。
- 不得連外、下載 terms/robots、安裝 dependency、把 public source 設為 approved、merge、push 或清理 worktree。

## Required reviewer perspectives

- Correctness：closed schema、decision completeness、state/expiry、reader ordering、checksum receipt。
- Security：path traversal／prefix confusion、method/media normalization、callback invocation、fail-open、host path／secret／source bytes。
- Regression：SLC-01、`app.tskg` exports、fixture isolation、dependency/runtime boundary。
- Test gap：負向案例是否真的命中 public interface，而非只測 helper。
- Maintainability：schema/version/error contract 是否穩定且未提前長成 crawler framework。

## Mandatory risk probes

1. `PUBLIC + APPROVED` 是否可能經 fixture mutation／custom registry 繞過「repo fixture 不得核准 public」契約。
2. `decision_status`、review／expiry timestamp、timezone、naive datetime、boundary equality 是否 fail closed。
3. missing／unknown／duplicate fields、duplicate `policy_id/source_id`、bool-as-int、NaN/Infinity、零／負／過大 rate/concurrency 是否拒絕。
4. `allowed_paths` 是否可被 `..`、encoded traversal、double slash、query/fragment、prefix confusion、Unicode／backslash 或 absolute URL 繞過。
5. method 與 media type 的 case、parameters／wildcards、空集合、重複值是否有唯一且保守的語意。
6. robots `ALLOW` 是否在 terms/legal basis 缺漏或 blocked 時仍錯誤放行。
7. `BLOCKED/EXPIRED/unknown/invalid request` 是否在所有路徑保證 reader 0 calls；reader exception 是否被誤寫成 approval receipt。
8. checksum 是否包含所有 policy-governance 欄位、排除輸入順序但不掩蓋 duplicate、使用 canonical JSON，且 receipt 綁定正確 policy/checksum/request。
9. committed fixture 是否只有 synthetic approved，public examples 無真實 source bytes、URL、claim／relationship 或貌似法律核准的 decision evidence。
10. `app/tskg/__init__.py` export 是否造成既有 import／API 回歸；`app/api/main.py`、dependencies、production runtime 是否確實未變。
11. evidence 是否可重現 RED、14 SRC tests、22 SLC regression、compile、allowlist、prohibited scan、diff/clean，且沒有本機絕對路徑。
12. OQ-SRC-01 與 SLC-02 blocker 是否在 code、fixture、card、evidence 中一致保留，沒有完成文案誤導。

## Verification

- `<repo-root>/.venv/bin/python -m unittest tests.test_tskg_src01 tests.test_tskg_slc01 -v`
- `<repo-root>/.venv/bin/python -m py_compile app/tskg/source_policy.py tests/test_tskg_src01.py`
- `git diff --check 4f0470e133b763d5d5c5a232acddf3ab2bc94de8 bcbf773f8dbee51e84488b1ea3c11fabbad7a28a`
- 驗證 candidate changed-file allowlist、no-network/no-dependency/no-production paths、host-specific path scan。
- 可新增 ephemeral in-memory probes，但不得修改 candidate；所有 probe 與結果寫入 review evidence。

## Finding schema

每個 finding 必須包含 severity、category、repo-relative `path:line`、觸發條件／evidence、risk、suggested fix、validation gap、confidence。先 findings，後 Spec axis／Standards axis verdict。

## Verdict

- 任一 P0/P1、production safety risk、明確 fail-open 或 public-source false approval：`REVIEW_NO_GO`。
- P2 若破壞本卡 acceptance／AC-10 或缺乏可重現證據：`REVIEW_NO_GO`；純非阻塞改善可 `REVIEW_GO_WITH_NOTES`。
- 無阻塞 finding：`REVIEW_GO`。
- Review 完成後建立 review artifact commit，只回報 verdict、reviewed SHA、review commit、findings、tests、evidence 與 remaining risks。

## Result

- Initial review：`REVIEW_NO_GO`；reviewed candidate
  `bcbf773f8dbee51e84488b1ea3c11fabbad7a28a`；review commit
  `31715802f794f411986abdebb6f368ce31b35834`；F-01/F-02/F-03 均為 P1。
- Re-review Round 1：`REVIEW_GO`；reviewed successor
  `2d81414185446e83a34df28c37f54989515d7f76`；parent
  `717e1c6dffedf254661a12ab41b1092bfae948d9`。
- Finding dispositions：F-01、F-02、F-03 全部 `RESOLVED`；未發現新的阻塞
  finding。
- Axis：Spec `GO`；Standards `GO`。
- Validation：39/39 tests（17 SRC + 22 SLC）、`py_compile` PASS、原 reviewer
  matrix 51/51、3/3 exploits BLOCKED、10 denied requests reader 0-call、
  diff/allowlist/dependency/production/prohibited/host-path/debug scans PASS。
- Callback：canonical path 與 receipt/callback path 相同；舊 zero-arg callback
  不相容但原 candidate 未接受或整合，列為後續 adapter migration note。
- Blocker：OQ-SRC-01 未解除，沒有 public source approved，SLC-02 仍 blocked。
- Evidence：`docs/evidence/REVIEW-TSKG-SRC-01/review.md` 的 Re-review Round 1。
- Re-review artifact commit：完整 SHA 由 reviewer 最終回報提供，避免 commit
  自參照。

---
card_id: TSKG-SRC-01
chain_id: TSKG-SRC
title: Fail-closed source governance gate
status: CARD_DRAFTED
type: implementation
owner: Codex 主線
assignee: TSKG-SRC-01 implementation thread
thickness: standard
risk: medium
model: gpt-5.5
reasoning: high
model_reason: 涉及來源治理、closed schema、存取前 fail-closed invariant 與跨檔離線測試，但不執行外部存取或 production mutation
source_kind: commit
source_sha: 300571e11d7d9cfe00c7ff297feeef768697ca1a
source_branch: codex/tskg-src-01
mainline_dispatcher: TSKG root thread
previous_card: TSKG-SLC-01
previous_implementation_thread: 019f70ef-6891-7f81-9199-f80a4c2db978
previous_review_thread: 019f70ff-7ce1-72e3-9038-500533156cac
previous_repair_thread: 019f75bd-007d-71e0-8f31-e1a4df27c2e7
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/TSKG-SRC-01/
---

# TSKG-SRC-01：Fail-closed source governance gate

任務：建立 SLC-02 前置的離線 Source Gate，讓任何 ingestion reader 在來源政策未完整核准時無法被呼叫。

這不是 SLC-02，也不代表任何 P1～P5 真實來源已獲准。只允許 synthetic policy fixture 與 deterministic preflight。

## Root question

在完全不連外、不保存公開來源內容的條件下，能否用 closed/versioned policy registry 證明：缺少 terms/legal basis、robots、allowed method/path/media、rate/concurrency、retention、redistribution、owner、review date 或 decision evidence 任一決策時，run 會在讀取來源前 fail closed？

## Dependencies and frontier

- 已完成並整合 `TSKG-SLC-01`，mainline acceptance：`300571e11d7d9cfe00c7ff297feeef768697ca1a`。
- 依 `docs/specs/TSKG_v1.1.md`，SLC-02 仍受 OQ-SRC-01 阻擋。
- 本卡是解除技術 preflight 缺口的前置 frontier；不解除法律／條款／source-owner approval blocker。
- 本卡完成後仍須由 source/compliance owner 核准一個特定 public source，才能開 SLC-02。

## Allowed scope

- `app/tskg/source_policy.py`
- `app/tskg/__init__.py`（只允許匯出本卡 public contract）
- `data/fixtures/tskg/source_policy_v1.json`
- `tests/test_tskg_src01.py`
- `docs/evidence/TSKG-SRC-01/verification.md`
- 本卡狀態與 Result

## Forbidden scope

- 不存取任何外部 URL、robots.txt、網站、PDF、API 或 SaaS。
- 不新增 Scrapy、Playwright、HTTP client、PDF parser、LLM、DB、Redis、scheduler 或 dependency。
- 不把 P1～P5 任一真實來源標為 `APPROVED`，不宣稱法律、條款、robots 或再散布核准。
- 不保存真實來源 HTML/PDF/snippet/raw bytes；不建立 RawArtifact、claim、Evidence 或 relationship。
- 不修改 `app/api/main.py`、requirements／lockfile、SLC-01 fixture、Top10 runtime 或交易／模型程式。
- 不實作 SLC-02 ingestion、SLC-03 graph、SLC-04 diff 或後續 persistence。

## Public contract

### Policy registry

- Registry 具有固定 `schema_version`，頂層及每筆 policy 都是 closed shape；未知、缺漏或型別錯誤一律 fail loud。
- 每筆 policy 至少保存：
  - `policy_id`, `source_id`, `source_class`, `publisher`, `owner`
  - `decision_status`：`APPROVED/BLOCKED/EXPIRED`
  - `terms_decision`, `legal_basis`, `robots_decision`
  - `allowed_methods`, `allowed_paths`, `allowed_media_types`
  - `authentication_constraints`
  - `rate_limit`, `concurrency_limit`, `user_agent`, `contact`
  - `raw_retention`, `snippet_retention`, `metadata_retention`
  - `redaction_policy`, `deletion_policy`, `redistribution_policy`
  - `reviewed_at`, `expires_at`, `decision_evidence`
- `source_class` 只允許 `SYNTHETIC/PUBLIC`。repo fixture 中只能有 synthetic `APPROVED`；所有 public examples 必須保持 `BLOCKED` 或 `EXPIRED`。
- 所有 timestamps 使用 RFC 3339 UTC；空字串不能代替決策。數量／速率須有界且為正值。
- canonical JSON checksum 在輸入順序改變後不變，供後續 run 綁定 policy version。

### Preflight

- Public interface 接受 `source_id`、requested method/path/media type、`as_of` 與 injectable reader callback。
- 只有 policy 狀態 `APPROVED`、未過期、所有 governance decisions 完整、且 request 位於允許 method/path/media/rate/concurrency 邊界時，才可呼叫 reader 一次。
- `BLOCKED/EXPIRED`、未知 source、缺欄位、過期 approval、method/path/media 不允許時，reader 呼叫次數必須為 0，回傳 stable structured error。
- robots 決策不可取代 terms/legal basis；`robots=ALLOW` 但 terms 或 legal basis 未核准仍阻擋。
- 本卡不做網路 I/O；reader 僅用 spy／in-memory callback 證明 ordering invariant。

## Acceptance criteria

- AC-10 negative path：registry 缺治理決策時，在任何 reader invocation 前阻擋。
- 完整 synthetic `APPROVED` policy 的允許 request 只呼叫 reader 一次並回傳綁定 `policy_id/checksum` 的 receipt。
- public `BLOCKED/EXPIRED` fixtures 永不呼叫 reader。
- closed schema、enum、timestamp、bounded numeric、duplicate ID/source、path traversal／prefix confusion 均有負向測試。
- deterministic checksum、重排 registry、相同 preflight request 產生一致 receipt。
- 不包含真實 source bytes、claim、relationship、prediction、score、target price 或模型權重。

## TDD and verification

1. RED：先寫 public-behavior tests，證明 `app.tskg.source_policy` 尚不存在或不符合契約。
2. GREEN：最小實作 registry loader、validator、deterministic checksum 與 preflight。
3. 使用 repo 既有離線 Python 環境，不安裝 dependency：
   - `<repo-root>/.venv/bin/python -m unittest tests.test_tskg_src01 -v`
   - `<repo-root>/.venv/bin/python -m py_compile app/tskg/source_policy.py tests/test_tskg_src01.py`
4. 驗證 changed-file allowlist、prohibited-field/source-byte scan、`git diff --check`、post-commit clean。
5. Evidence 記錄 RED/GREEN 命令、測試數、checksum、reader-call assertions、allowlist 與未解除 blocker。

## Stop conditions

- 需要連外、下載 terms/robots、決定法律基礎、把 public source 設為 approved、修改 forbidden path 或新增 dependency時，立即停止回主線。
- 規格不足以唯一決定 policy 語意時，保留 fail-closed，不能自行放寬。
- 同一 blocker 累計失敗三次即停，不做第四次嘗試。

## Delivery contract

- 執行線只可回報 `DELIVERED_CANDIDATE`，不得宣稱 source approved、SLC-02 unlocked、accepted 或 integrated。
- 交付須包含完整 candidate/parent SHA、changed files、RED/GREEN、test count、registry checksum、reader invocation proof、evidence path 與 blockers。
- Candidate 必須接受獨立 Review；`REVIEW_NO_GO` 時由另一條 Repair thread 修復，再回原 reviewer re-review。

## Result

`PENDING_IMPLEMENTATION`

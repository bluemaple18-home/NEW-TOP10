# TSKG-SRC-01 verification

Candidate verification：`PASS`。此結果只證明 synthetic/offline Source Gate 的技術
preflight 契約，**不代表**任何 public source 已核准、SLC-02 已解鎖、候選已接受或已整合。

## Preflight

- 固定 card commit／執行前 HEAD：
  `4f0470e133b763d5d5c5a232acddf3ab2bc94de8`
- Parent：`300571e11d7d9cfe00c7ff297feeef768697ca1a`
- `git merge-base --is-ancestor 4f0470e... HEAD`：exit `0`
- 平台 worktree 與 main worktree 路徑不同，且本 worktree 為 detached HEAD。
- 執行前 `git status --short --branch`：只有 `## HEAD (no branch)`。
- `git rev-parse --git-path index.lock` 所指檔案不存在；repo 內亦無其他
  `index.lock`。
- 全程使用既有 repo `.venv` Python，沒有安裝或下載 dependency。

## Public-contract TDD

### RED

命令：

```text
<repo-root>/.venv/bin/python -m unittest tests.test_tskg_src01 -v
```

在只有 public-behavior tests、尚無 implementation 時，exit `1`：

```text
ModuleNotFoundError: No module named 'app.tskg.source_policy'
Ran 1 test
FAILED (errors=1)
```

失敗發生在 module import；reader callback 尚不存在，因此 reader invocation 為 `0`。

### GREEN

相同命令在最小實作後 exit `0`：

```text
Ran 14 tests in 0.018s
OK
```

既有 SLC-01 回歸：

```text
<repo-root>/.venv/bin/python -m unittest tests.test_tskg_slc01 -v
Ran 22 tests in 0.794s
OK
```

編譯檢查：

```text
<repo-root>/.venv/bin/python -m py_compile app/tskg/source_policy.py tests/test_tskg_src01.py
exit 0
```

## Contract proof

- Closed shape：registry 與每筆 policy 都以 exact field set 驗證；未知、缺漏、
  root type 錯誤均 `SourcePolicyContractError`。
- Schema／value gate：enum、RFC 3339 UTC、空決策、list type、duplicate
  policy/source ID、rate `1..1000`、concurrency `1..100` 都有負向測試。
- Reader ordering：所有 validation、decision、expiry、method/path/media/rate/
  concurrency gate 都在 reader invocation 前完成。
- Path gate：拒絕 traversal、encoded segment、query/fragment、double slash 與
  `/records` 對 `/recordsevil` 的 prefix confusion。
- Governance：`robots=ALLOW` 無法取代 `terms_decision=APPROVED` 與
  `legal_basis=APPROVED`。
- Fixture：唯一 `APPROVED` policy 為 `SYNTHETIC`；兩筆 `PUBLIC` example 分別
  保持 `BLOCKED`／`EXPIRED`，且 fixture 無 URL、HTML、PDF 或 source bytes。
- Determinism：policy、allowed list 與 JSON key 輸入順序重排後 checksum 不變；
  相同 preflight request 的 receipt byte-equivalent。

Registry checksum：

```text
0ea9bfca08d343f796aa093d162d4c9153b6a7fd8c94064d870a9d89b8a07b4d
```

獨立 reader-call probe：

```json
{"approved_ok": true, "approved_reader_calls": 1, "blocked_code": "SOURCE_BLOCKED", "blocked_reader_calls": 0, "checksum": "0ea9bfca08d343f796aa093d162d4c9153b6a7fd8c94064d870a9d89b8a07b4d"}
```

## Acceptance mapping

| Acceptance | Evidence |
|---|---|
| AC-10 missing decision before read | empty governance fields fail loader；reader `0` |
| Synthetic APPROVED happy path | allowed reader `1`；receipt 綁定 policy ID/checksum |
| Public BLOCKED/EXPIRED | stable error；reader `0` |
| Closed/typed schema | closed shape、enum、timestamp、numeric、duplicate negatives |
| Request boundary | method/path/media/rate/concurrency negatives；reader `0` |
| Deterministic checksum/receipt | reordered registry 與 repeated request tests |

## Allowlist and prohibited scan

Changed-file allowlist：

- `app/tskg/source_policy.py`
- `app/tskg/__init__.py`（只新增本卡 public exports）
- `data/fixtures/tskg/source_policy_v1.json`
- `tests/test_tskg_src01.py`
- `docs/evidence/TSKG-SRC-01/verification.md`
- `docs/tasks/2026-07-18_TSKG-SRC-01_source_gate.md`（只更新 status／Result）

Runtime／fixture 掃描 external clients、URL、RawArtifact、RelationshipClaim、
prediction、target/model fields：`rg` exit `1`，即零匹配。未修改 dependency、lockfile、
API、SLC-01 fixture、Top10 runtime 或交易／模型程式。

`git diff --check`：exit `0`。Post-commit changed-file 與 clean 證據於 candidate
commit 建立後再次驗證。

## Remaining blockers

- OQ-SRC-01 仍未解：P1～P5 的 terms/legal basis、robots、allowed method/path、
  rate、retention 與 redistribution 尚未經 source/compliance owner 核准。
- 沒有任何 public source 被標為 `APPROVED`。
- SLC-02 仍是 `BLOCKED`；本卡沒有實作 ingestion、RawArtifact、claim、Evidence、
  relationship、persistence 或 external I/O。

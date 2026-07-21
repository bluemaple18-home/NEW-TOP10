---
card_id: TSKG-OSS-ACCEPT-01
status: DELIVERED_CANDIDATE
verified_on: 2026-07-20
verification_kind: acceptance_host_path_cleanup
source_candidate: 64e5bb2
card_commit: f723b64ebc13733bbcefc93feb460558246f018a
---

# TSKG-OSS-ACCEPT-01 verification

## 1. Preflight

| Check | Evidence | Result |
|---|---|---|
| 實際 cwd | `pwd` = 平台指派獨立 worktree 路徑 | PASS |
| HEAD 含卡片提交 | `git rev-parse HEAD` = `f723b64ebc13733bbcefc93feb460558246f018a` | PASS |
| source lineage | `git merge-base --is-ancestor 64e5bb2 HEAD` exit code `0` | PASS |
| worktree clean | `git status --short` 無輸出 | PASS |
| git-dir | `git rev-parse --git-dir` 指向主 repo 的 worktree metadata 目錄 | PASS |
| index lock | `find .git -name index.lock -print` 無輸出 | PASS |
| unrelated dirty paths | `[]` | PASS |

## 2. Scope

- 允許修改檔案僅三個：
  `docs/tasks/2026-07-20_TSKG-OSS-ACCEPT-01_host_path_cleanup.md`、
  `docs/tasks/2026-07-20_TSKG-OSS-02_external_open_source_reference_scout.md`、
  `docs/evidence/TSKG-OSS-ACCEPT-01/verification.md`
- 未修改研究語意、來源、版本、排序、review verdict、code、config、runtime、API、UI。
- 未執行連外、merge、push、ADR。

## 3. Exact change intent

- `TSKG-OSS-02` 僅將 receipt 的 `worktree_path` 從 host-specific 絕對路徑替換為 `<local-only-worktree verified in preflight>`。
- acceptance-cleanup 卡片僅更新本卡狀態與 receipt 交付欄位。
- 新增本 verification evidence。

## 4. Verification results

```bash
git diff --word-diff=porcelain                  # exit 0
git status --short                             # exit 0
git diff --check                               # exit 0
host-path scan on allowlist shared files       # exit 1
```

- 已觀測結果：

- `git diff --word-diff=porcelain` 只呈現指定 path 值替換與本卡/evidence 新增。
- `git status --short` 顯示兩個已修改檔與一個新增 evidence 目錄，合計仍只涉及 allowlist 三檔。
- host-path scan 無匹配，符合「無輸出且 exit code 1」。
- `git diff --check` exit code `0`。

目前變更檔：

```text
docs/tasks/2026-07-20_TSKG-OSS-02_external_open_source_reference_scout.md
docs/tasks/2026-07-20_TSKG-OSS-ACCEPT-01_host_path_cleanup.md
docs/evidence/TSKG-OSS-ACCEPT-01/verification.md
```

---
card_id: TSKG-OSS-02
status: REPAIR_READY
verified_on: 2026-07-20
verification_kind: repair_release_metadata
---

# TSKG-OSS-02 repair verification

## 1. Preflight

| Check | Evidence | Result |
|---|---|---|
| 實際 cwd | `pwd` 指向平台指派的獨立 worktree 路徑 | PASS |
| cwd 為獨立 worktree | `git rev-parse --git-dir` 指向主 repo 的 worktree metadata | PASS |
| HEAD 等於 repair card commit | `git rev-parse HEAD` = `b5e5019a64c85486f66edcb6c4b3fca690528379` | PASS |
| worktree clean | `git status --short` 空 | PASS |
| git-dir | `git rev-parse --git-dir` 指向主 repo 的 worktree metadata，而非本地 `.git/` 實體目錄 | PASS |
| index lock | `.git/index.lock` = absent | PASS |
| 卡片存在 | `docs/tasks/2026-07-20_REPAIR-TSKG-OSS-02_release_metadata.md` = present | PASS |
| 與主專案 cwd 不同 | worktree cwd 與主專案根目錄為不同路徑 | PASS |

## 2. External-operation gate

- network scope：公開網頁唯讀查證。
- external writes：`0`
- clone / install / execute external code：`0`
- login / token / OAuth / dataset download：`0`
- financial data endpoint calls：`0`
- modified runtime / config / source code：`0`

本次 repair 只接受 canonical GitHub repo 成功讀取到的 release / repo metadata 作為更正依據。

## 3. Canonical release check

| Source | Observed metadata | Result |
|---|---|---|
| `https://github.com/twjackysu/TWSEMCPServer` | repo 首頁 sidebar 顯示 `Releases 9`，latest release `v1.8.0`，日期 `Jul 19, 2026` | PASS |
| `https://github.com/twjackysu/TWSEMCPServer/releases` | releases 頁主列表仍顯示 `v1.7.0` 為 `Latest`，日期 `18 Jul 06:47` | RECORDED |

判定：

- 研究報告中的 latest release 結論已更正為 canonical repo 首頁 sidebar 呈現的 `v1.8.0 / 2026-07-19`。
- releases 頁仍顯示 `v1.7.0 Latest / 2026-07-18` 的 cross-page 不一致已明記，未被忽略或自行合理化。

## 4. Repair scope check

| Check | Result |
|---|---|
| 只修 reviewer 指出的單一 P2 | PASS |
| 未改其他候選排序或研究範圍 | PASS |
| 未更動 code / config / runtime / API / UI | PASS |

## 5. Allowlist check

Exact changed files：

```text
docs/tasks/2026-07-20_REPAIR-TSKG-OSS-02_release_metadata.md
docs/research/TSKG-OSS-02_external_open_source_reference_scout.md
docs/evidence/TSKG-OSS-02/verification.md
```

判定：PASS

## 6. Host-path scan

已執行 host-path scan，檢查共享檔案是否殘留本機絕對路徑或本機檔案 URI 類型字串。

預期：無輸出、exit code `1`。

## 7. Post-edit verification

```bash
git diff --check
git diff --name-only
rg -n '<old_twsemcpserver_latest_release_tag_or_date>' \
  docs/research/TSKG-OSS-02_external_open_source_reference_scout.md \
  docs/evidence/TSKG-OSS-02/verification.md \
  docs/tasks/2026-07-20_REPAIR-TSKG-OSS-02_release_metadata.md
```

預期：

- `git diff --check` exit code `0`
- `git diff --name-only` 只列出 allowlist 三檔
- `rg` 只應命中 task card 內的 reviewer 問題敘述，不應再命中研究報告或 verification 的 latest release 結論

## 8. Remaining risk

- canonical repo 的 repo 首頁與 releases 頁對 latest release 的呈現暫時不一致；本次僅能如實記錄，不替 upstream GitHub 狀態做額外推論。

---
card_id: TSKG-OSS-02
status: DELIVERED_CANDIDATE
verified_on: 2026-07-20
verification_kind: external_reference_scout_gate
---

# TSKG-OSS-02 verification

## 1. Preflight

| Check | Evidence | Result |
|---|---|---|
| cwd 為獨立 worktree | `git rev-parse --show-toplevel` = `<repo-root>`；`git rev-parse --git-dir` 指向主 repo 的 `worktrees/TOP10new4` | PASS |
| 非主 repo cwd | `pwd` 為平台指派 worktree，不等於主 repo 路徑 | PASS |
| HEAD 含 card commit | `git rev-parse HEAD` = `1a2b0eab8a3ed625d85fdeef6ce4ddb4726a7208`；`git merge-base --is-ancestor 1a2b0ea HEAD` = true | PASS |
| worktree clean | `git status --short` 空 | PASS |
| index lock | `.git/index.lock` 不存在 | PASS |
| Git metadata writable | 後續 candidate commit 成功即為正證 | PASS |

正式 receipt 已寫回 task card：

- `thread_id`: `019f7e58-df13-7d60-80c9-885af3e23f0f`
- `worktree_path`: `<local-only>/Users/matt/.codex/worktrees/245a/TOP10new`
- `turn_status`: `DELIVERED_CANDIDATE`

## 2. External-operation gate

- network scope：公開網頁唯讀查證。
- external writes：`0`
- clone / install / execute external code：`0`
- login / token / OAuth / dataset download：`0`
- financial data endpoint calls：`0`
- modified runtime / config / source code：`0`

本卡只接受成功讀到的原始 repo、package metadata、LICENSE 呈現或 Issue/Discussion 內容作為結論依據。

## 3. Candidate count gate

| Constraint | Result |
|---|---|
| candidate 上限 `8` | `7` candidates，PASS |
| 同一專案 repo/docs/releases 不拆名額灌水 | PASS |
| 真正 `T86` 候選若找不到要明記 | PASS |

## 4. Source tracker summary

| Status | Count |
|---|---:|
| `retrieved` | 11 |
| `failed` | 1 |
| `not_used` | 0 |

### Retrieved

- `https://github.com/FinMind/FinMind`
- `https://pypi.org/project/finmind/`
- `https://github.com/mlouielu/twstock`
- `https://pypi.org/project/twstock/`
- `https://pypi.org/project/twstocks-crawler/`
- `https://github.com/Asoul/tsec`
- `https://github.com/Asoul/tsec/issues/6`
- `https://github.com/Asoul/tsrtc`
- `https://github.com/twjackysu/TWSEMCPServer`
- `https://github.com/twjackysu/TWSEMCPServer/blob/main/CLAUDE.md`
- `https://github.com/arleigh418/python-and-Taiwan-stock-market/issues/76`

### Failed

- PyPI `twstocks-crawler` project link homepage click-through
  - 結果：無法在本輪成功解析為可讀 repo 正文。
  - 處置：只保留 PyPI package metadata，不對其原始碼內容下結論。

## 5. License and maintenance cross-check

| Candidate | Maintenance proof used | License proof used | Result |
|---|---|---|---|
| FinMind | GitHub release + PyPI release | GitHub repo license + PyPI metadata + README data-use note | PASS_WITH_BOUNDARY_RISK |
| twstock | GitHub release + PyPI release | GitHub repo license + PyPI metadata | PASS |
| twstocks-crawler | PyPI release | PyPI metadata only | PASS_WITH_SOURCE_GAP |
| tsec | GitHub release + README self-reported last update + issue activity | repo page inspected; `LICENSE` 未見 | PASS_WITH_LICENSE_GAP |
| tsrtc | GitHub release + README self-reported last update | repo page inspected; `LICENSE` 未見 | PASS_WITH_LICENSE_GAP |
| TWSEMCPServer | GitHub release + repo metadata | repo page `MIT license` | PASS |
| issue #76 | issue dates | discussion only，非 code license | PASS_AS_DISCUSSION_ONLY |

## 6. Shared-file path scan

要求：共享文件使用 repo-relative 或 `<repo-root>`；本機絕對路徑只可作 `local-only evidence`。

結果：

- research 檔：未寫入 `/Users/...` 或 `/private/...`。
- verification 檔：只有正式 receipt 需要保留的 `worktree_path` 用 `<local-only>/Users/...` 呈現。
- task card：`worktree_path` 同樣以 `<local-only>/Users/...` 呈現。

判定：PASS

## 7. Allowlist check

Exact changed files：

```text
docs/tasks/2026-07-20_TSKG-OSS-02_external_open_source_reference_scout.md
docs/research/TSKG-OSS-02_external_open_source_reference_scout.md
docs/evidence/TSKG-OSS-02/verification.md
```

符合卡片 allowlist，PASS。

## 8. Post-edit verification

交付前應通過：

```bash
git diff --check
git diff --name-only
rg -n '/(Users|private)/|file:/[/]' \
  docs/tasks/2026-07-20_TSKG-OSS-02_external_open_source_reference_scout.md \
  docs/research/TSKG-OSS-02_external_open_source_reference_scout.md \
  docs/evidence/TSKG-OSS-02/verification.md
```

本卡是研究卡，不涉及 runtime/test suite；因此沒有執行單元測試或外部整合測試。

## 9. Remaining risks

- 沒有找到仍在活躍維護、專做 `T86` 的單一純 parser/crawler repo。
- `FinMind` 的 code license 與 data-use note 需後續再拆解，不可直接簡化成「完全 Apache-2.0」。
- `tsec` / `tsrtc` 授權不明，只適合參考概念與風險，不適合直接搬 code。
- `twstocks-crawler` 原始 repo 未成功讀到，可信度最低。

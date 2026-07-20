---
card_id: TSKG-MOPS-01
status: DELIVERED_CANDIDATE
verified_on: 2026-07-20
verification_kind: source_trace_gate
---

# TSKG-MOPS-01 verification

## 1. Fixed source and workspace preflight

| Check | Evidence | Result |
|---|---|---|
| platform-managed independent worktree | `pwd` 與 `git rev-parse --show-toplevel` 均為平台指派 worktree，非主 repo cwd | PASS |
| fixed card commit | pre-change `git rev-parse HEAD` = `744bf934cd988b75322cb674c218691de6615b97` | PASS |
| clean worktree/index | pre-change `git status --short --branch` 只有 `## HEAD (no branch)`；`git diff --cached --name-only` 為空 | PASS |
| no index lock | `git rev-parse --git-path index.lock` 對應檔不存在 | PASS |
| detached platform HEAD | `## HEAD (no branch)` | PASS |

## 2. Scope verification

- External operation level：`read_only`。
- 使用工具：web search/open；未安裝工具、未登入、未要求 OAuth。
- External writes：0。
- Data endpoint calls：0。
- 公司資料查詢：0。
- PDF／CSV／JSON／HTML raw bytes 或附件下載：0。
- 表單提交、註冊、付費、rate-limit／load test：0。
- Runtime／code／config／fixture／test／registry 變更：0。

## 3. Source trace gate

| Metric | Result |
|---|---:|
| Official pages successfully opened | 11 |
| Of which retrieved with readable substantive text | 9 |
| Retrieved landing pages with no parser-readable text | 2 |
| Failed URL opens | 3 |
| Cited failed URLs | 0 |
| Non-official conclusion sources | 0 |

失敗與 recovery：

1. MOPS `robots.txt`：web open 回 non-retryable unsafe；沒有替代官方內容，因此 robots 欄標 `NOT_FOUND`，不重試、不推論。
2. 猜測的 TWSE `/zh/openapi/`：web open 回 non-retryable unsafe；改以官方 `openapi.twse.com.tw` landing 與政府 dataset 頁明示的 OAS URL證明文件通道存在。
3. MOPS 舊 `/mops/web/index`：轉至 error page；改以新版 MOPS landing、TWSE 服務介紹與官方 MOPS 優化專文證明入口／用途。

完整 URL/status/use tracker 位於 `docs/research/TSKG-MOPS-01_source_dossier.md` 第 4 節。只有 `retrieved`／`retrieved_limited` URL 出現在 substantive report；`retrieved_limited` 不承載正文政策結論。

## 4. Required-field completeness gate

| Required item | Dossier locator | Result |
|---|---|---|
| source/publisher/owner/contact | §3.1、§5 | COVERED |
| terms/legal basis | §5、§7 | COVERED_WITH_SCOPE_CONFLICT |
| robots and legal caveat | §4 S02、§5、§7 | GAP_RECORDED |
| method/path/media | §3.2、§5.1、§6.1 | GAP_RECORDED |
| auth | §5、§5.1 | GAP_RECORDED |
| rate/concurrency/frequency | §5、§9 | GAP_RECORDED |
| UA/contact identifier | §5、§9 | GAP_RECORDED |
| raw/snippet/metadata retention | §5、§5.1、§9 | GAP_RECORDED |
| redaction/deletion/tombstone/legal hold | §5、§9 | GAP_RECORDED |
| redistribution/derivative/commercial | §5、§6.2 | COVERED_WITH_SCOPE_CONFLICT |
| review/expiry | §5、§9 | GAP_RECORDED |
| decision evidence locator | §4、§5、§10 | COVERED_NOT_APPROVED |
| channel separation | §3.2、§5.1、§8 | COVERED |
| endpoint docs vs explicit programmatic permission | §6.1 | COVERED |
| automation/bulk/reproduction restrictions | §6.2 | COVERED |
| cross-source comparison | §7 | COVERED |
| limitations and blockers | §9 | COVERED |

缺口未被補猜；依卡片契約，缺一項必要治理欄即不可建議批准。

## 5. Decision verification

| Channel | Dossier recommendation | Gate result |
|---|---|---|
| `interactive_web` | `KEEP_BLOCKED` | PASS：缺 MOPS-specific policies |
| `official_api_or_open_data` | `KEEP_BLOCKED` | PASS：OGL 只覆蓋明確 dataset，技術與 deletion/review 欄仍缺 |
| `manual_file_download` | `KEEP_BLOCKED` | PASS：MOPS artifact 條款未證實，商店為不同申請式服務 |

- Executable `APPROVED` policy：未產生。
- Source Gate fixture／registry：未修改。
- OQ-SRC-01／SLC-02：未解除。
- RawArtifact／Evidence／claim：未建立。

## 6. Local verification commands

交付前執行並以實際輸出判定：

```bash
git diff --check
git diff --name-only
rg -n '/(Users|private)/|file:/[/]' docs/tasks/2026-07-20_TSKG-MOPS-01_source_dossier.md docs/research/TSKG-MOPS-01_source_dossier.md docs/evidence/TSKG-MOPS-01/verification.md
rg -n 'APPROVED|SLC-02|KEEP_BLOCKED|2026-07-20' docs/tasks/2026-07-20_TSKG-MOPS-01_source_dossier.md docs/research/TSKG-MOPS-01_source_dossier.md docs/evidence/TSKG-MOPS-01/verification.md
```

Expected exact changed-file allowlist：

```text
docs/evidence/TSKG-MOPS-01/verification.md
docs/research/TSKG-MOPS-01_source_dossier.md
docs/tasks/2026-07-20_TSKG-MOPS-01_source_dossier.md
```

本卡為純研究文件；TDD 不適用。驗收依 source-trace gate、exact allowlist、host-specific path scan、`git diff --check`、candidate commit 與 post-commit clean。

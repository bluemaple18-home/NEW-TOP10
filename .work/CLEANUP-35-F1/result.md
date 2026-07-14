---
id: CLEANUP-35-F1
status: ready-for-re-review
type: strict-bounded-repair-result
---

# CLEANUP-35-F1 Result

只處理 `C35-R1-F1/F2`，沒有修改 candidate runner 的 production/research 行為。

## Repair

- committed parity command：`uv run python scripts/verify_shadow_research_campaign_parity.py`
- legacy baseline：固定從 `9748b95` 的四支舊入口 Git objects 載入，不把舊 CLI 恢復到工作樹
- coverage：四 stage × valid/missing/failure，共 12 組 old/new execution
- comparisons：normalized JSON、exact Markdown、normalized TSV、console JSON、exit code、executed/artifact command order
- mutation sensitivity：`A1_SCHEMA_VERSION` 漂移會被判定 `FAIL`
- audit count：reference/lifecycle 均為 `430 tracked scripts`、`strict-new: PASS`

## Verification

- parity evidence：`.work/CLEANUP-35/evidence/parity.json` → `PASS`
- focused pytest：`15 passed`
- reference strict-new：`PASS`
- lifecycle strict-new：`PASS`
- py_compile：`PASS`
- full pytest：`267 passed, 1 failed, 28 subtests passed, 4 warnings`；唯一 failure 是 R1 已揭露的 gitignored research ledger evidence 缺口
- daily 四檔 SHA-256：與 card 基線一致
- `git diff --check`：`PASS`
- real replay/training：`0`

## Handoff

狀態為 `READY_FOR_RE_REVIEW`，不宣稱 GO。下一張卡必須由 `CLEANUP-35-R1` 原 reviewer 執行 `RE_REVIEW`。

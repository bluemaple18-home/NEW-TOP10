---
id: CLEANUP-35
status: done
type: result
---

# CLEANUP-35 Result

已完成 shadow research campaign 收斂：

- 新入口：`scripts/run_shadow_research_campaign.py`
- stages：`a1-forward`、`candidate-stress`、`overnight-training`、`risk-matrix-summary`
- retired：四支舊 runner/builder
- lifecycle：新入口明確分類為 research，舊 allowlist 項目移除

## Evidence

- parity：`.work/CLEANUP-35/evidence/parity.json` → `PASS`
  - 重建：`uv run python scripts/verify_shadow_research_campaign_parity.py`
  - frozen legacy source：`9748b95` Git objects；12 組 synthetic fixture，真實 replay/training `0` 次
- focused dry-run / mocked subprocess tests：`15 passed`（含 schema mutation sensitivity）
- candidate full pytest：`266 passed, 28 subtests passed, 4 warnings`
  - 原始 worktree run 為 `264 passed, 1 failed`；唯一失敗是既有 ledger verifier 缺 gitignored evidence
  - local-only adapter 只把 verifier evidence root 指向 canonical checkout；未 copy/symlink artifact，完整 suite 通過
- repair full pytest：`267 passed, 1 failed, 28 subtests passed, 4 warnings`
  - 唯一失敗仍為 `test_research_component_ledger` 的既有 gitignored evidence 缺口；本 repair 不處理
- lifecycle strict-new：`430 tracked scripts` → `PASS`
- reference strict-new：`430 tracked scripts, 0 new suspected orphans` → `PASS`
- 四支舊入口只保留於 parity harness 的 pinned Git source path，不恢復為可執行入口
- py_compile：新 runner 與 parity verifier 通過
- `git diff --check`：`PASS`

## Failure Semantics

- A1：四步驟全部執行，任一步失敗即 aggregate `FAILED` / exit 1；`--reuse-existing` 保留。
- candidate stress：第一個 subprocess failure 立即停止，不寫 stage artifact，CLI exit 1；stage-local 舊 `--dry-run` 行為保留。
- overnight training：失敗後續跑並執行 `summary.build`，每步保留 stdout/stderr tail 與 TSV row，aggregate exit 1。
- risk matrix summary：baseline missing 或 model hash mismatch 仍寫 JSON/Markdown errors 並 exit 1。
- 全域 dry-run：subprocess 0 次、不刪既有 steps TSV、不寫 stage artifact；只有明確 top-level `--output` 才寫 SKIPPED manifest。

## Daily Hashes

- `scripts/run_daily.sh`: `3a0a0905a9f24f79938eb8a5d24c4c0d20bf841833ce0a5c07b078be4718f4a3`
- `scripts/run_daily_publish.sh`: `ff001af0c95d100d7e077bf1a6735f488e36234dadd4a8d73223486d747e84c3`
- `scripts/com.new-top10.daily.plist`: `eba01f79b457916608b2a2ca5c42bf61af12a2ec81b5f1901934491859155995`
- `config/automation.yaml`: `c68ca07816a859103013323214cdd47da23ee277cab54e0bd08d59839d70004a`

## Boundary

所有驗證都使用 synthetic fixture、global/stage dry-run 或 mocked subprocess；沒有執行真實 replay、shadow ranking、training，也沒有修改 production ranking、model、publish 或 automation。

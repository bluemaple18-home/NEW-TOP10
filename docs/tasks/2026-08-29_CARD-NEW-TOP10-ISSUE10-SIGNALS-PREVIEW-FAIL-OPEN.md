---
id: CARD-NEW-TOP10-ISSUE10-SIGNALS-PREVIEW-FAIL-OPEN-20260829
title: Issue #10 daily signals preview fail-open
date: 2026-08-29
status: authorized
scope: minimum_recovery_only
traces_to:
  - "GitHub Issue #10 Acceptance：first failing boundary / minimum recovery"
  - "2026-08-29 本輪 Owner 授權"
---

# Issue #10 — Daily Signals Preview Fail-Open

## Goal

daily 執行時明確跳過 signals preview，使 ReportStage 不因 preview 阻斷；非 daily 路徑維持既有預設行為。

## Allowed Files

- `app/pipeline/report_stage.py`
- `scripts/run_daily.sh`
- `tests/test_daily_signals_preview.py`
- 本任務卡

## Forbidden

- storage policy、restart-denied marker、launchd、config
- ranking、model、backtest
- OpenClaw、production、dry-run、send
- merge、push、deploy
- 候選 `162e082d...`
- 所有既有 dirty files

## Implementation Contract

- 當 `TOP10_SKIP_SIGNALS_PREVIEW=1` 時，ReportStage 必須照常寫入 `etl_report.md`，且不得 import 或呼叫 `generate_signals_preview`。
- 未設定該環境變數時，維持既有 signals preview 呼叫。
- `scripts/run_daily.sh` 必須 export `TOP10_SKIP_SIGNALS_PREVIEW=1`。
- 僅做滿足此契約的最小修改，不擴張到其他 recovery 或 hardening。

## TDD 與驗證

1. 先新增 focused tests，實際執行並取得符合目標的 RED。
2. 再做最小實作，使測試轉為 GREEN。
3. 驗證：
   - focused tests
   - 受影響的既有測試
   - `bash -n scripts/run_daily.sh`
   - `git diff --check`
   - `rg '[DBG-'`

## Execution Boundary

本卡禁止 production run；也不授權任何 dry-run 或外部送出。

---
id: BC-CP2-R13-R1-FORWARD-CAPTURE-RETRY
status: completed
type: acceptance
---

# R13-R1 trusted-date forward-capture retry

## Root question

在 fixed source `f7f9d46fb29f0e52b3a276738370f4192a7c2d68` 上，能否用同一個已完成交易日 `2026-09-01` 的 fresh features、universe、regime history 與 hash-bound daily completion authority，完成一次隔離 create→capture→verify？

## 輸入與 authority

- Canonical read-only source：主 checkout 的 2026-09-01 `features.parquet`、`universe.parquet`、`ranking_2026-09-01.csv`、`automation_status_2026-09-01.json`。
- 隔離 worktree 必須複製輸入 bytes，不得 symlink／hardlink；複製前後 hash 必須一致，主 checkout hash 不得改變。
- 以 canonical builder 從複製後的 features 建立隔離 `market-regime-history.v2` 至 `2026-09-01`；必須驗 schema、date max、`as_of_date == trade_date`。
- `automation_status_2026-09-01.json` 是唯一 completed-date authority；validator 必須回傳與 strict snapshot 相同的 path/hash。
- 正式 ranking 只可作 `calendar_schedule_source`，不可當 scoring lineage 或 capture output。

## 執行邊界

- 使用 `scripts/research_regime_shadow_ranking.py` 的 `FORWARD_CAPTURE`，單一日期 `2026-09-01`、明示 `--capture-authority-artifact` 與固定 run identity。
- output 只在隔離 worktree 的 run-unique `artifacts/backtest/` 子目錄；session output 上限 256 MiB。
- 不修改 source、config、model、正式 data/ranking、主 checkout；不 network fetch，不讀 outcome/sealed data，不 replay/benchmark/training，不 external write。
- 不 merge、push、deploy、production；不准入 R14、Entry-Regime capacity、B0 Phase 2、B1、C1。

## 驗收

- preflight：fixed SHA、producer source clean、輸入 hash/date/schema/coverage 全 PASS。
- create→capture→COMPLETE manifest→`verify_complete_bundle` 全 PASS。
- receipt 綁定 ranking、model、config、universe、features、fresh regime history、industry map、calendar schedule source、completed-date authority、producer source 與 run identity。
- capture mode 為 `FORWARD_CAPTURE`、admission eligibility 只可 `pending_registration`；historical corpus 維持 `NON_ADMISSION`。
- 保存新 evidence：`docs/evidence/BC-CP2-R13-R1-FORWARD-CAPTURE-RETRY/01-session-verification.md`；不得改寫原 R13 blocked evidence。
- 跑相關 bundle verifier、`git diff --check`；只提交本 task card 與新 evidence，不提交 ignored session/data artifacts。

## 停損

- 任一 freshness/date/hash/producer/authority gate 失敗即停止，capture/bundle/verify 列 `NOT_RUN` 或實際失敗點；不得放寬 validator或換歷史來源。
- 同一 blocker 最多三次；此卡只允許一個 run identity、一次真正 capture 嘗試。

## Completion receipt

- Verdict：`NO_GO_EXISTING_SEAM_RUNTIME_FAILURE`
- Fixed source：`f7f9d46fb29f0e52b3a276738370f4192a7c2d68`
- Run identity：`r13-r1-20260901-f7f9d46`
- Evidence：`docs/evidence/BC-CP2-R13-R1-FORWARD-CAPTURE-RETRY/01-session-verification.md`
- Capture attempt：`FORWARD_CAPTURE` executed exactly once; exit `1`
- Failure point：existing seam runtime stopped before ranking/receipt/COMPLETE bundle because M4 inference data lacked training contract fields.
- COMPLETE bundle：`NOT_CREATED`

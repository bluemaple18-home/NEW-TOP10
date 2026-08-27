---
id: CARD-NEW-TOP10-ISOLATED-DAILY-BACKFILL-20260827
chain_id: NEW-TOP10-ISOLATED-DAILY-BACKFILL-20260827
status: ready
type: implementation
priority: P1
owner: TOP10new operations
role: implementation
cycle: 1
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: 歷史排名補跑會重建多日資料產物；規格已固定，但必須隔離正式輸出、通知、外部審查與目前 17:30 排程，並驗證日期與資料完整性。
date: 2026-08-27
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
external_write_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-ISOLATED-DAILY-BACKFILL-20260827/
---

# 隔離補回缺漏的每日 Top 10 資料

## 工作名稱

隔離補跑 2026-08 月缺漏的每日 Top 10 資料。

## Root question

能否在完全不碰正式每日產物、通知與排程的前提下，補回 2026-08-03 至 2026-08-26 的有效交易日資料，並逐日證明資料與排名產物完整？

## Scope and ownership

### 允許修改

- 新增或修正 bounded、date-explicit、output-root-explicit 的隔離補跑入口。
- 與該入口直接相關的測試。
- `artifacts/isolated_daily_backfill/2026-08-03_2026-08-26/` 內的補跑產物。
- 本卡 evidence 與必要 handoff。

### 禁止修改

- 現有正式 `artifacts/ranking_*.csv`、`daily_run_summary_*.json`、`automation_status.json` 與 daily latest pointer。
- 正式通知、Clawd 發送、ops report、ChatGPT／Gemini 外部審查或任何 provider write。
- LaunchAgent、17:30 正式排程與已安裝 plist。
- 模型、指標、權重、訓練資料、promotion gate 與使用者既有 dirty files／`.work/**`。
- Merge、push、deploy、production 補跑或把隔離資料發布成正式資料。

## Requirements and slices

- `IB-FR-001`（Slice A，frontier）：盤點現有 daily pipeline 的日期、輸出、通知與 latest-pointer seam；建立 dry-run／單日隔離契約。驗證所有可寫路徑皆在本卡隔離根目錄，否則 fail closed。
- `IB-FR-002`（Slice B，blocked by A）：先補一個已知交易日作代表性試跑；驗證 ranking、summary、必要原始／中間資料、資料日期與非空股票集合，且正式路徑 digest／mtime 不變。
- `IB-FR-003`（Checkpoint 1，blocked by B）：保存基線與試跑後容量、檔案數、RSS／swap、每日期增長估算、總量上限與停止方式；非 PASS 不得批次執行。
- `IB-FR-004`（Slice C，blocked by Checkpoint 1）：以 bounded sequential 方式補 2026-08-03 至 2026-08-26；只處理交易日，每日獨立狀態、失敗即停、不得無限重試。
- `IB-FR-005`（Slice D，blocked by C）：逐日驗證輸入資料日期、ranking rows／欄位、summary 狀態與 lineage；產出 completed／skipped／failed 清單與 digest manifest。
- `IB-FR-006`（Checkpoint 2，blocked by D）：重驗正式 daily 產物、通知 receipt、LaunchAgent 與外部審查狀態未被改動；交付隔離產物，不發布、不覆寫。

## Acceptance

- 日期範圍固定為 2026-08-03 至 2026-08-26；2026-08-27 留給 17:30 正式排程，不補跑。
- 代表性單日試跑與批次補跑都只寫入指定隔離根目錄；任何正式輸出、latest pointer、通知或外部 write 為零。
- 每個有效交易日都有可驗證的 ranking、daily summary、lineage／digest 與逐日狀態；休市日須明確標記 skipped 與判定來源。
- 補跑開始前先保存正式路徑 baseline；完成後 hash／mtime／launchd 狀態比對無非預期變化。
- 容量安全為 PASS，包含 bounded 檔案數／bytes、保留與可整批移除的 rollback path；未知增長或未登記路徑一律 NO-GO。
- Targeted tests、代表性單日、批次 manifest verifier 與 `git diff --check` 全綠。

## Stop conditions

- 任何正式資料或通知路徑被寫入、資料日期穿越、需要外部 write、容量 gate 非 PASS、今日正式排程可能受影響，或同一 blocker 第三次失敗：立即停止並回主線。
- 不得為求補齊而使用今日以後資料、改權重、補造缺失市場資料或把失敗日標成成功。

## Deliverable

- Candidate commit SHA、RED／GREEN、代表性單日證據、容量 receipt、逐日 manifest、正式路徑不變證據與 rollback 指令。
- 狀態只可為 `DELIVERED_CANDIDATE` 或 structured `NO-GO/BLOCKED`。

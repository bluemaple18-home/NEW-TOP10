---
id: BC-CP2-R13-R2-EVENT-COMPLETE-FORWARD-CAPTURE
status: completed
type: acceptance
---

# R13-R2 event-complete forward capture

## Root question

在 R13-R1 已證明的 authority/freshness 基線上，補齊 M4 明文需要的 fresh `events.parquet` staging 後，能否完成一次隔離 create→capture→verify？

## 已證明根因

- R13-R1 staging 沒有 `events.parquet`，M4 frame 缺 13 個模型要求的 `event_*` 欄位並在 `calculate_scores` fail closed。
- 同一模型、同一日期用 canonical `data/clean`（含 events）載入時，86 個 required model features 缺失數為 0。
- 本卡不得修改程式、補零、放寬模型契約或換模型；唯一變數是 staging 必須包含 fresh events。

## 執行契約

- Fixed HEAD：`af9c32bdd63d86918fbd9d57c4f909beaa03f936`；其中 source code 與 reviewed `f7f9d46fb29f0e52b3a276738370f4192a7c2d68` 相同。
- 主 checkout 只讀；複製 features、events、universe、authority、calendar ranking、model、config、industry map，不得 symlink/hardlink。
- features/events/universe max date 必須同為 `2026-09-01`，copy 前後 hash 相同、主來源 hash 不變。
- fresh regime history 由本卡副本重建至 `2026-09-01`，schema/as-of gates 全 PASS。
- capture 前先用 M4 loader 證明模型 required features missing count `0`；否則停止、不執行 capture。
- 單一 run identity：`r13-r2-20260901-af9c32b`；只允許一次真正 `FORWARD_CAPTURE`。
- output 僅在 run-unique `artifacts/backtest/` 子目錄，session <= 256 MiB；不 network、outcome、replay、benchmark、training、external write、merge、push、deploy、production。

## 驗收

- create→capture→COMPLETE manifest→`verify_complete_bundle` 全 PASS。
- receipt/manifest 綁定 ranking、model、config、universe、features、fresh regime history、industry map、calendar schedule、completed-date authority、producer source、run identity；events 雖由 feature frame loader消費，也必須至少在 session evidence 記錄 exact hash/date，並證明 run 前後未漂移。
- capture mode=`FORWARD_CAPTURE`，admission eligibility 只能=`pending_registration`；historical corpus 維持 `NON_ADMISSION`。
- 新 evidence：`docs/evidence/BC-CP2-R13-R2-EVENT-COMPLETE-FORWARD-CAPTURE/01-session-verification.md`；不得改寫 R13/R1 evidence。
- 只 commit 本 task card + evidence，不提交 ignored inputs/output。

## 停損

- 任一 preflight gate 失敗即 `BLOCKED`；runtime 失敗即 `NO_GO_EXISTING_SEAM_RUNTIME_FAILURE`；不得第二次執行 capture。
- R2 完成後無論 GO/NO-GO 均回 Mainline，不准入任何 downstream。

## Completion receipt

- Verdict：`GO_FORWARD_CAPTURE_SESSION_VERIFIED`
- Fixed HEAD：`af9c32bdd63d86918fbd9d57c4f909beaa03f936`
- Run identity：`r13-r2-20260901-af9c32b`
- Capture date：`2026-09-01`
- Evidence：`docs/evidence/BC-CP2-R13-R2-EVENT-COMPLETE-FORWARD-CAPTURE/01-session-verification.md`
- Capture attempt：`FORWARD_CAPTURE` executed exactly once; exit `0`
- M4 preflight：`86` model required features, missing count `0`; `13` event columns present.
- COMPLETE bundle：`COMPLETE.manifest.json` created and `verify_complete_bundle` returned `{"errors": [], "status": "OK"}`.
- Admission：receipt `admission_eligible=pending_registration`; historical corpus remains `NON_ADMISSION`.

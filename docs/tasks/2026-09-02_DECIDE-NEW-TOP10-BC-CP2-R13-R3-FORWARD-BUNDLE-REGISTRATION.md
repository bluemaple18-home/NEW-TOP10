---
id: DECIDE-NEW-TOP10-BC-CP2-R13-R3-FORWARD-BUNDLE-REGISTRATION
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: authority-boundary-decision
risk: high
model: gpt-5.6-terra
reasoning: medium
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
---

# BC-CP2 R13-R3 forward bundle registration boundary

## 工作名稱 → 正在做什麼 → 現在狀態

`R13-R3 Forward Bundle Registration Boundary` → 判定 R13-R2 的成功 forward-capture bundle 能否經既有 committed-evidence seam 註冊，以及最小必要 committed bytes → `READY_FOR_READ_ONLY_DECISION`

## Root question

R13-R2 已在隔離 session 產生並驗證一個 `FORWARD_CAPTURE / pending_registration` COMPLETE bundle。現有 repository contract 是否已有足夠 registration／admission seam，可以在不新增 registry、canonical writer、runtime 或 production authority 的前提下，把該 bundle納入 committed evidence？

## 固定事實

- Main fixed HEAD：`d3a76693f4e91bd756f9285b8aa6b329fd5eefaa`。
- R13-R2 evidence：`docs/evidence/BC-CP2-R13-R2-EVENT-COMPLETE-FORWARD-CAPTURE/01-session-verification.md`。
- Local audit source：`/private/tmp/top10new-r13-trusted-date-authority-20260902/artifacts/backtest/r13-r2-20260901-af9c32b/output/`；只讀，不得改寫、重跑或重新 capture。
- Governing contract：`docs/tasks/2026-08-16_CARD-NEW-TOP10-FORWARD-RANKING-PROVENANCE-RECEIPT-V1.md`。
- Existing historical admission seam：`docs/tasks/2026-08-16_CARD-NEW-TOP10-RANKING-PROVENANCE-ADMISSION-AUDIT-V1.md`、`app/research/ranking_provenance_admission.py`。

## 允許範圍

- 唯讀檢查 COMPLETE manifest、receipt、ranking、model snapshot 的 schema、hash binding、大小與 path semantics。
- 唯讀檢查現有 admission／availability contracts 與 tests。
- 產出 `docs/evidence/BC-CP2-R13-R3-FORWARD-BUNDLE-REGISTRATION/01-boundary-decision.md`。
- 明列 `why_not_less`、`why_not_more`、`do_not_absorb` 與 rollback/removal path。

## 禁止範圍

- 不複製或 commit bundle bytes；不修改 code、config、workflow、既有 evidence 或 availability manifest。
- 不執行 registration、admission、replay、benchmark、training、outcome read 或第二次 capture。
- 不啟用 R14、Entry-Regime capacity、preregistration、historical corpus、B0 Phase 2、B1、C1、production。
- 不新增 registry、database、authority ledger、canonical writer、runtime adapter 或第二套流程。
- 不 merge、push、deploy、production 或 external write。

## Verdict

只能選一個：

- `GO_EXISTING_REGISTRATION_SEAM`
- `DEFER_BUNDLE_NOT_CANONICALLY_AVAILABLE`
- `NO_GO_NEW_SUBSYSTEM_REQUIRED`

若為 GO，必須固定下一張 implementation card 的精確 allowlist、必要 committed bytes、驗證方式與 fail-closed 條件；不得在本卡直接實作。

## 驗收

- 判定現有 `ranking_provenance_admission.py` 是否直接支援 forward bundle registration，並引用具體函式／schema證據。
- 列出 bundle 每一類 artifact 是否必須 committed、僅 hash-bound 或必須排除，且總大小可重現。
- 解釋 committed evidence 如何保持 receipt／manifest／ranking／model identity 綁定，不把 R13-R2 GO 升格為下游 admission。
- 明確回答下一步是最小 implementation card、補 authority contract，或停止。
- `git diff --check` 通過；changed-files allowlist 只有本 decision evidence（task card由 Mainline預先建立）。

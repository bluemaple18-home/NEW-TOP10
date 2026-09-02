---
id: DECIDE-NEW-TOP10-BC-CP2-R13-R4-FORWARD-RECEIPT-AUTHORITY-CONTRACT
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: authority-contract-decision
risk: critical
model: gpt-5.6-sol
reasoning: high
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
---

# BC-CP2 R13-R4 forward receipt authority contract

## 工作名稱 → 正在做什麼 → 現在狀態

`R13-R4 Forward Receipt Authority Contract` → 裁決是否可在既有 provenance modules 上建立最小、可移除、R13-only 的 committed bundle authority → `READY_FOR_ARCHITECTURE_DECISION`

## Root question

R13-R3 已證明 R13-R2 bundle 完整，但現有 historical admission audit 沒有 forward receipt authority。能否只以既有 `ranking_provenance_receipt.py` verifier 與 committed evidence conventions，定義一個最小 authority contract；或任何可用設計都會變成禁止的新 registry／canonical writer／第二套流程？

## 固定輸入

- Main fixed HEAD：`d3a76693f4e91bd756f9285b8aa6b329fd5eefaa`。
- R13-R3 task／evidence：
  - `docs/tasks/2026-09-02_DECIDE-NEW-TOP10-BC-CP2-R13-R3-FORWARD-BUNDLE-REGISTRATION.md`
  - `docs/evidence/BC-CP2-R13-R3-FORWARD-BUNDLE-REGISTRATION/01-boundary-decision.md`
- Governing V1 receipt contract：`docs/tasks/2026-08-16_CARD-NEW-TOP10-FORWARD-RANKING-PROVENANCE-RECEIPT-V1.md`。
- Existing source seams：`app/research/ranking_provenance_receipt.py`、`app/research/ranking_provenance_admission.py` 與其 tests。
- R13-R2 output只作唯讀 schema/bytes reference；不得複製、修改或重跑。

## 必答 fork

1. Registration 是否只代表「exact COMPLETE bundle bytes 成為 committed evidence」，receipt仍維持 `pending_registration`；或 registration 必須同時產生另一個 admission decision artifact？
2. Forward R13 receipt 是否應與 historical 50-record admission audit 完全分離；若分離，最小 reader／verifier 的 repo-relative canonical path與輸出是什麼？
3. 哪個狀態才可解除 `pending_registration`，由誰驗證 committed status、bundle bytes、schema、scenario/date/run identity與 duplicate/conflict？
4. 單一 R13 bundle 能授權的下一 frontier 是什麼；必須明列仍不授權 R14、Entry-Regime capacity/split、preregistration、historical corpus、B0 Phase 2、B1、C1、production。

## 允許範圍

- 唯讀架構／schema／tests分析。
- 產出 `docs/evidence/BC-CP2-R13-R4-FORWARD-RECEIPT-AUTHORITY-CONTRACT/01-contract-decision.md`。
- 若 GO，固定下一張 implementation card 的 exact files、schema、states、CLI/API、positive/negative tests、committed bundle allowlist、removal path與 no-op/downstream boundary。

## 禁止範圍

- 不修改 code、tests、config、workflow、既有 evidence、availability/feasibility、ranking root 或 bundle。
- 不執行 registration/admission、copy、replay、capture、benchmark、training、outcome/sealed read。
- 不新增 database、registry、ledger、canonical writer、runtime adapter、scheduler或 production surface。
- 不把 `ranking_provenance_admission.py` 的 historical corpus scope 偷換成 forward corpus authority。
- 不 merge、push、deploy、production 或 external write。

## Verdict

只能選一個：

- `GO_MINIMAL_COMMITTED_BUNDLE_AUTHORITY_CONTRACT`
- `DEFER_AUTHORITY_CONTRACT_INSUFFICIENT_EVIDENCE`
- `NO_GO_AUTHORITY_REQUIRES_FORBIDDEN_SUBSYSTEM`

## 驗收

- 明確回答四個必答 fork，不以命名或 git commit 本身冒充 authority。
- 證明 why_not_less、why_not_more、do_not_absorb 與 rollback/removal path。
- GO 時必須讓下一張 implementation card無架構歧義，且預設 fail closed。
- `git diff --check` 通過；changed-files allowlist只有本 decision evidence（task card由 Mainline預先建立）。

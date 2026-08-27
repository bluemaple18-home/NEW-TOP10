---
id: CARD-NEW-TOP10-EXTERNAL-REVIEW-PREFLIGHT-RESTORE-20260827
chain_id: NEW-TOP10-EXTERNAL-REVIEW-RESTORE-20260827
status: ready
type: implementation
priority: P1
owner: TOP10new operations
role: implementation
cycle: 1
thickness: standard
risk: high
model: gpt-5.6-terra
reasoning: medium
model_reason: 既有 ChatGPT／Gemini provider preflight 的 bounded 修復與驗收；外部 session 與排程控制面風險高，但架構與正式入口均已固定。
date: 2026-08-27
production_change_allowed: true
live_activation_allowed: true
scheduler_change_allowed: true
external_write_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-EXTERNAL-REVIEW-PREFLIGHT-RESTORE-20260827/
---

# 恢復外部審查 Provider Preflight

## 工作名稱

修復並恢復 17:40 ChatGPT／Gemini 外部審查連線預檢。

## Root question

既有 `external-review-preflight` 正式入口能否在不送出 review packet 的前提下，可靠確認 ChatGPT／Gemini provider 可用，並受容量 guard 保護後恢復排程？

## Ownership

### 允許修改

- `scripts/run_external_review_provider_preflight.sh`
- `scripts/preflight_external_review_providers.py`
- `scripts/review_chatgpt_chrome.sh`、`scripts/review_gemini_chrome.sh` 中僅與 probe 契約直接相關的段落
- `scripts/com.new-top10.external-review-preflight.plist`
- targeted tests 與本卡 evidence

### 禁止修改

- Daily ranking、模型、指標、權重、推薦結果與 send payload。
- ChatGPT／Gemini cookie、profile、token、登入設定或永久授權。
- `external-review` 正式送件入口與其 LaunchAgent。
- 其他六個排程與使用者既有 dirty files／`.work/**`。
- Push、production 補跑或手動送出 review packet。

## Functional contracts

- `ERP-FR-001`：先建立 red-capable preflight command；身份為本機使用者 session，runtime 為 macOS local LaunchAgent，target 為既有 ChatGPT／Gemini browser/API provider，權限沿用既有 session／環境，不新增憑證。
- `ERP-FR-002`：preflight 僅 probe provider readiness，不送 review packet、不產生外部 review。
- `ERP-FR-003`：provider 缺失、登入失效、tab／API authority 不足必須 fail closed，留下 provider-specific evidence。
- `ERP-FR-004`：完成兩個代表性週期、寫入盤點、容量預算、回收與 stop-loss 證據；`launch_verified` 只能在完整證據後改為 true。
- `ERP-FR-005`：只啟用 `com.new-top10.external-review-preflight`，時間維持 17:40、`RunAtLoad=false`，不得補跑。

## Acceptance

- ChatGPT 與 Gemini preflight 均有明確 PASS 或 structured BLOCKED，不以「程式沒 crash」冒充成功。
- 正式 preflight 入口、plist 與 installed LaunchAgent 一致並走 `run_with_storage_guard.sh`。
- 兩週期容量證據、主機 free／RSS／swap、未知寫入、reclaim 與 stop-loss 全數通過。
- Targeted tests、shell syntax、plist lint、JSON validation、`git diff --check` 全綠。
- 若外部登入／權限需人工介入，交付精確 blocker，不自行登入或改 token。

## Stop conditions

- 無法建立 red-capable probe、需新增永久憑證、需送出正式 packet 才能證明 readiness，或同一 blocker 第三次失敗：停止並回主線。
- 容量 gate 非 PASS：不得啟用排程。

## Deliverable

- Candidate commit SHA、RED／GREEN、provider readiness evidence、容量 receipt、installed plist 驗證與 rollback 指令。
- 狀態只可為 `DELIVERED_CANDIDATE` 或 structured `NO-GO/BLOCKED`。

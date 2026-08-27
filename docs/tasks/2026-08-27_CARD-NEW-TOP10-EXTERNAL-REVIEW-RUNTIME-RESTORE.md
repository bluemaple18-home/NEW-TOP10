---
id: CARD-NEW-TOP10-EXTERNAL-REVIEW-RUNTIME-RESTORE-20260827
chain_id: NEW-TOP10-EXTERNAL-REVIEW-RESTORE-20260827
status: ready
type: implementation
priority: P1
owner: TOP10new operations
role: implementation
cycle: 2
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: 正式排程會把公開 review packet 寫入 ChatGPT／Gemini 並彙整外部回覆；規格已固定，但外送邊界、provider authority、容量與失敗語意需嚴格驗證。
date: 2026-08-27
production_change_allowed: true
live_activation_allowed: true
scheduler_change_allowed: true
external_write_allowed: true
evidence_path: docs/evidence/CARD-NEW-TOP10-EXTERNAL-REVIEW-RUNTIME-RESTORE-20260827/
---

# 恢復 ChatGPT／Gemini 外部審查

## 工作名稱

修復並恢復 17:50 ChatGPT＋Gemini 盤後外部審查。

## Dependency

- `CARD-NEW-TOP10-EXTERNAL-REVIEW-PREFLIGHT-RESTORE-20260827` 必須先達 `ACCEPTED`，且兩個 provider readiness 為 PASS。

## Root question

既有 `external-review` 正式入口能否只外送核准的公開 packet、可靠收回並驗證 ChatGPT／Gemini 回覆，且在容量與失敗邊界內恢復每日排程？

## External write authorization

- 使用者已在本對話明示要求恢復並啟動兩個外部審查排程。
- 目標：既有 TOP10 ChatGPT project conversation 與 Gemini provider。
- Payload：公開 Top 10 推薦、公開交易計畫、產業／概念標籤、公開 OHLC／量價與 daily 市場風險摘要。
- 禁止外送：演算法、權重、feature engineering、訓練資料結構、模型程式碼、內部 scoring formula、promotion gate internals。
- 影響：啟用後，每個交易日 daily 成功後由 17:50 排程送出一次 review packet，收集兩個 provider 的 research-only 意見；不得直接改排名。

## Ownership

### 允許修改

- `scripts/run_external_review_host_runner.sh`
- `scripts/run_external_review_host_runner.py`
- `scripts/build_external_review_packet.py` 與 verify／normalize／summary provider contract 的直接相關檔案
- `scripts/review_chatgpt_chrome.sh`、`scripts/review_gemini_chrome.sh`、`scripts/external_review_api_provider.py` 的 bounded provider seam
- `scripts/com.new-top10.external-review.plist`
- targeted tests 與本卡 evidence

### 禁止修改

- Daily ranking、模型、指標、權重、推薦結果來源與 promotion gate。
- 擴大 sendable packet、外送 local-only lineage、cookie、profile、token 或憑證。
- 自動接受外部建議、直接改排名、建立研究／promotion action。
- 其他五個排程、preflight 卡已接受成果、使用者既有 dirty files／`.work/**`。
- Push 或未經 gate 的 production 補跑。

## Functional contracts

- `ERR-FR-001`：先以 deterministic verifier 建立 red-capable 正式入口；packet 必須先通過 sendable safety boundary 與 exact lineage 驗證。
- `ERR-FR-002`：正式模式依既有 browser provider，必要時只使用既有官方 API fallback；不得新增連線、憑證或未知 provider。
- `ERR-FR-003`：每個 provider 只送一次；保存時間、provider、packet digest、result/status，partial failure 不得盲目重送。
- `ERR-FR-004`：回覆必須正規化並通過 `external-review.v1`；ChatGPT／Gemini summary 為 research-only，不能直接改 ranking。
- `ERR-FR-005`：完成兩個代表性完整週期、寫入盤點、容量預算、回收與 stop-loss；未知寫入或 authority 不足一律 NO-GO。
- `ERR-FR-006`：只啟用 `com.new-top10.external-review`，時間維持 17:50、`RunAtLoad=false`，不得補跑；preflight 與 daily 以外的排程狀態不變。

## Acceptance

- Preflight dependency 已接受且 provider readiness 為 PASS。
- Exact packet dry-run 顯示只有核准公開欄位；prohibited 欄位負向測試 fail closed。
- 在使用者既有授權範圍內完成一次 bounded provider write acceptance，保留遮蔽後 evidence；不得自動重試不確定的外部 write。
- 兩週期容量證據、主機 free／RSS／swap、未知寫入、reclaim、stop-loss 與保留期推估全數通過。
- Targeted tests、shell syntax、plist lint、JSON／contract verifier、`git diff --check` 全綠。
- Installed LaunchAgent 與 repo plist hash-equivalent，launchd 顯示 17:50、guarded、`runs=0` 或未補跑證據。

## Stop conditions

- Provider write 結果不確定、需要擴大 payload／權限、缺 preflight PASS、容量 gate 非 PASS，或同一 blocker 第三次失敗：停止並回主線。
- 不得用 dry-run fixture 冒充正式 provider 成功。

## Deliverable

- Candidate commit SHA、RED／GREEN、packet digest、provider result/status、容量 receipts、launchd 驗證與 rollback 指令。
- 狀態只可為 `DELIVERED_CANDIDATE` 或 structured `NO-GO/BLOCKED`。

---
id: CARD-NEW-TOP10-ISOLATED-EXTERNAL-REVIEW-BACKFILL-20260827
chain_id: NEW-TOP10-ISOLATED-EXTERNAL-REVIEW-BACKFILL-20260827
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
model_reason: 需要對 ChatGPT 與 Gemini 執行最多 36 次歷史外部 write；目標與 payload 已固定，但必須以 canary、逐次 receipt、去重與隔離回覆控制不確定寫入風險。
date: 2026-08-27
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
external_write_allowed: true
evidence_path: docs/evidence/CARD-NEW-TOP10-ISOLATED-EXTERNAL-REVIEW-BACKFILL-20260827/
---

# 隔離補回 ChatGPT／Gemini 歷史外部審查

## 工作名稱

讓 ChatGPT 與 Gemini 補做 2026-08-03 至 2026-08-26 的每日 Top 10 審查。

## Root question

能否以 1 日雙 provider canary 後再 bounded sequential 補齊 18 個交易日的 ChatGPT／Gemini research-only 審查，且每次外送可對帳、回覆只落隔離區、不得改正式排名或排程？

## Authorization

- 使用者已在本對話明示要求 ChatGPT 與 Gemini 也補隔離資料。
- ChatGPT 目標：19 帳號 `bluemaple19@gmail.com` 的既有「台股波段推薦分析」project conversation；不得改用 17／18 帳號或新對話。
- Gemini 目標：既有已驗證 provider／對話；不得登入新帳號、建立新連線或擴大 OAuth。
- Payload：每日公開 Top 10、公開交易計畫、產業／概念標籤、公開 OHLC／量價與 daily 市場風險摘要。
- 禁止外送：演算法、權重、feature engineering、訓練資料結構、模型程式碼、內部 scoring formula、promotion gate internals、cookie、token、profile 或憑證。
- 影響：最多 18 日 × 2 provider = 36 次歷史審查 write；回覆只作 research-only，不得改排名。

## Sources and isolation

- local-only source root：`/Users/mattkuo/.codex/worktrees/b2e8/TOP10new/artifacts/isolated_daily_backfill/2026-08-03_2026-08-26/`
- 回覆與 receipts 必須落在新隔離根目錄 `artifacts/isolated_external_review_backfill/2026-08-03_2026-08-26/`。
- 不覆寫 daily、external-review 正式 artifacts／latest pointer，不啟用或修改任何 LaunchAgent。

## Execution slices

- `IER-FR-001`：唯讀驗證 18 日來源 manifest、每日 ranking／summary 與現有 provider 連線／目標 marker；建立 exact per-day sendable packet、digest 與 36-slot ledger。
- `IER-FR-002`：dry-run 驗證 payload allowlist／prohibited-field fail-closed、日期 lineage、provider schema、idempotency 與不確定 write 停止語意。
- `IER-FR-003`：先送 2026-08-03 至 ChatGPT 19 與 Gemini，各一次；保存時間、目標 marker、packet digest、遠端 result/status 與正規化回覆。任一不確定即停止，不得重送。
- `IER-FR-004`：雙 canary 均 PASS 後，依日期、provider bounded sequential 補其餘 17 日；已成功 slot 必須跳過，partial failure 停在唯一 next slot。
- `IER-FR-005`：驗證 36 個 slot completed、每 provider 每日期恰一次、回覆符合 `external-review.v1`、正式 ranking／排程與 external-review 狀態不變。

## Acceptance

- 18 個交易日各有 ChatGPT 與 Gemini 回覆，共 36 個唯一 slot；或 structured PARTIAL／BLOCKED 明列未完成 slot，禁止假稱補齊。
- 每次 write 有 exact packet digest、provider、日期、target marker、started／finished、result/status；不確定寫入不得自動重試。
- ChatGPT 必須證明使用 19 帳號與既有指定 conversation；Gemini 必須證明沿用既有 provider target。
- 所有回覆 research-only 且只存隔離根目錄；不得自動接受建議、改排名、改排程、發布報牌或觸發 promotion。
- Targeted tests、packet verifier、ledger uniqueness、正式 baseline comparison 與 `git diff --check` 全綠。

## Stop conditions

- 帳號／對話不符、provider write 結果不確定、payload 越界、需要新登入／連線、重複 slot、正式路徑被改、容量非 PASS或同一 blocker 第三次失敗：立即停止並回主線。

## Deliverable

- Candidate commit SHA、雙 provider canary、36-slot ledger、回覆／receipt manifest、正式路徑不變證據與 remaining risk。
- 狀態只可為 `DELIVERED_CANDIDATE`、`PARTIAL` 或 structured `NO-GO/BLOCKED`。

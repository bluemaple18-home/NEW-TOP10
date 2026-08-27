---
id: REPAIR-NEW-TOP10-EXTERNAL-REVIEW-DOM-COLLECTOR-20260827
chain_id: NEW-TOP10-ISOLATED-EXTERNAL-REVIEW-BACKFILL-20260827
status: ready
type: repair
priority: P1
owner: TOP10new operations
role: repair
cycle: 1
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
date: 2026-08-27
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
external_write_allowed: true
evidence_path: docs/evidence/REPAIR-NEW-TOP10-EXTERNAL-REVIEW-DOM-COLLECTOR-20260827/
---

# 修復外部審查 ChatGPT DOM Collector

## 工作名稱

修復 ChatGPT 外部審查 collector，救回既有 2026-08-03 canary 回覆。

## Root question

能否在不重送 2026-08-03 ChatGPT 的前提下，以 DOM／ARIA 訊息順序與本次 prompt marker 找到其後完整 assistant 回覆，保存可對帳 evidence，並讓原隔離 backfill ledger 從 `UNCERTAIN` 收斂為明確 completed？

## Bounds

- 禁止重送 `2026-08-03:chatgpt`。
- 修復前與救回階段只能唯讀既有 ChatGPT 頁面。
- 只允許在既有 `artifacts/isolated_external_review_backfill/2026-08-03_2026-08-26/` 隔離根目錄保存救回 raw、correlation receipt、normalize 與 contract verify 結果。
- 不得改排名、排程、正式 `artifacts/external_review`、latest pointer、LaunchAgent、merge、push 或 deploy。
- Gemini 只有在 ChatGPT canary 明確 PASS 後，才可依原卡送 `2026-08-03:gemini` canary 一次；任何 write 結果不確定不得重送。

## Repair Contract

- ChatGPT collector 必須以最後一則含本次 user message markers 的 user message 作為 anchor：
  - `review_date=2026-08-03`
  - `provider=chatgpt`
  - `market=TW`
  - `"packet_date":"2026-08-03"`
- Collector 必須只取該 user message 之後的 assistant sibling／後續 assistant message，不得用「最長 assistant」或無 prompt correlation 的候選。
- Collector 必須等待 generation stop indicator 消失，且至少兩次完整 `innerText`／accessible snapshot 穩定後才接受。
- Collector 必須拒絕：
  - 8 字元 prefix 或其他明顯不完整回覆。
  - 舊 TSKG 回覆。
  - 無 prompt correlation 的內容。
  - 仍在 generating／streaming 的內容。
- 成功時必須保存：
  - raw response。
  - correlation receipt。
  - normalized `external-review.v1`。
  - contract verify status。

## Execution

1. 建立並提交本 Repair 卡。
2. 修復 ChatGPT collector retrieval bug 與 focused tests。
3. 用修復後 collector 唯讀救回既有 `2026-08-03:chatgpt` 回覆，不重送。
4. 若 raw 完整且 normalize／contract verify PASS，原地更新隔離 ledger slot 為 completed。
5. ChatGPT canary 明確 PASS 後，才送 Gemini `2026-08-03` canary 一次。
6. 雙 canary 明確 PASS 後，才按原卡 bounded sequential 補剩餘 slots。
7. 停在任何不確定 write／collect／contract 狀態，留下 structured `PARTIAL` 或 `NO-GO/BLOCKED`。

## Acceptance

- Repair card 有獨立 candidate commit。
- Tests 覆蓋 prompt-correlation collector：接受 correlated assistant、拒絕短 prefix、拒絕舊 TSKG、拒絕無 correlation。
- `2026-08-03:chatgpt` 若救回成功，ledger slot 從 `UNCERTAIN` 收斂為 completed，且有 raw／correlation／normalized／contract evidence。
- Gemini canary 最多送一次，只有在 ChatGPT canary 明確 PASS 後才可執行。
- 正式路徑、排名、排程與 deployment 狀態不變。

## Stop Conditions

- 無法唯一定位 correlated user message。
- 其後 assistant 回覆不完整、不穩定、仍在 generating，或疑似舊內容。
- normalize 或 contract verify 失敗。
- Gemini write 或 collect 結果不確定。
- 任一正式路徑被修改。

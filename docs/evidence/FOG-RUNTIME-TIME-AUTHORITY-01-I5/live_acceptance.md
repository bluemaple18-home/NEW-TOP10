---
id: FOG-RUNTIME-TIME-AUTHORITY-01-I5-LIVE-ACCEPTANCE
status: GO
type: evidence
---

# I5 live acceptance

## Fixed runtime lineage

- Direct-push policy：個人專案，由使用者明確授權直接推送 `main`，不走 PR。
- Recovery contract commit：`d6efc54`。
- Bounded-dry Repair 1 commit：
  `e6fc10a3251e61bb49ef0ae66e28d336f3a3adb1`。
- Installed plist與 repo rendered plist SHA-256：
  `f63ae67c4ae7b437246d31f8122307b5a5726778d36d302794b80fa342f664cb`。
- Canonical time-authority contract SHA-256：
  `67327c40206251adf4d377e76833dfd6261ce4fb3f56c7de0b0bf92c7231e357`。

## Bounded dry

- 首次 bounded dry在任何 circuit mutation前 fail closed，找出 topic generation
  caller未傳 explicit date。
- Phase 0 RED：`2 failed`。
- Repair 1 targeted：`2 passed`；affected suite：`98 passed`。
- Full suite：
  `589 passed, 4 warnings, 246 subtests passed in 89.12s`。
- 原失敗 CLI重跑：exit `0`。
- Controlled-grid host runner 11 steps：全數 `OK`。
- Inventory verifier：14 checks、0 failed；production impact：
  `NO_PRODUCTION_CHANGE`。

## Circuit recovery

- 只呼叫一次既有 explicit verifier gate。
- Recovery verifier：14 checks、0 failed。
- 原 state/context以 `.recovered.20260728170100`旋轉保留，未直接刪除。
- 原 state SHA-256：
  `acfbfbc43bc02af51e5fb6b1d3e285616bf2fcf846e41ceda8ee3b79cd74096c`。
- 原 context SHA-256：
  `528d5cca4482f0e9ccb9e6d2374e856ca57557ebd69df3deb87c858a787f3255`。
- Recovery後 active state/context不存在。

## Scheduler cycles

### Cycle 1

- 啟動方式：LaunchAgent load後唯一一次受控 kickstart。
- LaunchAgent：單一 PID、`runs=1`，完成後
  `state=not running`、`last exit code=0`。
- Receipt：`closed-regime-runtime-receipt.v3`、`status=OK`。
- Run context：
  `2026-07-28T09:01:55.189442Z`／market date `2026-07-28`。
- Generated：
  `2026-07-28T09:01:59.733213Z`。
- Daily source date：`2026-07-27`。
- Exact regime：`RISK_OFF|`。
- State：`VERIFIED_HISTORY -> CLOSED_RESEARCH_COMPLETED`。
- 獨立 verifier：`ok=true`、reason codes空、age
  `232.875`秒。
- Representative replay drain：6/6 batches、144 completed、97 appended、
  0 failed，stop reason `max_batches_reached`。

### Cycle 2

- 自然排程：`2026-07-28 17:42:13 CST`，
  LaunchAgent `runs=2`、`immediate reason=interval`。
- Receipt：`closed-regime-runtime-receipt.v3`、`status=OK`。
- Run context：
  `2026-07-28T09:42:13.162408Z`／market date `2026-07-28`。
- Generated：
  `2026-07-28T09:42:16.662779Z`。
- Daily source date：`2026-07-27`。
- Exact regime：`RISK_OFF|`。
- State：`VERIFIED_HISTORY -> CLOSED_RESEARCH_COMPLETED`。
- 獨立 verifier：`ok=true`、reason codes空、age
  `22.220`秒。
- Representative replay drain：6/6 batches、144 completed、46 appended、
  0 failed，stop reason `max_batches_reached`。
- Worker完成：`2026-07-28 18:04:11 CST`；LaunchAgent
  `state=not running`、`runs=2`、`last exit code=0`。

### Cycle 3

- 自然排程：`2026-07-28 18:19:12 CST`，
  LaunchAgent `runs=3`、`immediate reason=interval`。
- Receipt：`closed-regime-runtime-receipt.v3`、`status=OK`。
- Run context：
  `2026-07-28T10:19:12.380614Z`／market date `2026-07-28`。
- Generated：
  `2026-07-28T10:19:17.004667Z`。
- Daily source date：`2026-07-28`；既有 daily automation於
  `17:53:24 CST`更新 `data/clean/features.parquet`，receipt記錄的
  `0a4eccd...`與檔案實算 SHA一致。
- Market regime source trade date：`2026-07-27`，history SHA保持不變。
- Exact regime：`RISK_OFF|`。
- State：`VERIFIED_HISTORY -> CLOSED_RESEARCH_COMPLETED`。
- 獨立 verifier：`ok=true`、reason codes空、age
  `25.586`秒。
- Representative replay drain：6/6 batches、144 completed、36 appended、
  0 failed，stop reason `max_batches_reached`。
- Worker完成：`2026-07-28 18:46:31 CST`；LaunchAgent
  `state=not running`、`runs=3`、`last exit code=0`。

## Final runtime state

- LaunchAgent保持 loaded，`StartInterval=900`；三輪 acceptance結束時
  `state=not running`、`runs=3`、`last exit code=0`。
- Repo template render後與 installed plist byte-identical；SHA-256皆為
  `f63ae67c4ae7b437246d31f8122307b5a5726778d36d302794b80fa342f664cb`。
- Repo template與 installed plist均通過`plutil -lint`。
- Active retry state/context：不存在。
- Fog worker、queue-owner與 PM harness lock：不存在。

### Protected after hashes

| Role | Before | After | Result |
|---|---|---|---|
| model | `ce643797...` | `ce643797...` | unchanged |
| baseline | `c219b1b3...` | `c219b1b3...` | unchanged |
| ranking code | `b3d44da0...` | `b3d44da0...` | unchanged |
| weights | `b34c1a20...` | `b34c1a20...` | unchanged |
| promotion | `2add0872...` | `2add0872...` | unchanged |
| regime history | `96372f3e...` | `96372f3e...` | unchanged |

Queue依研究 worker契約更新：

- Before SHA-256：`099cfa7f...`
- After SHA-256：
  `114db2c6509694880a1586e916266ec9769aae5d5df3cfdc77b140c66b69f1a4`
- Final schema：`autonomous-research-next-action-queue.v1`
- Final action count：`10`

## Verdict

`GO`。Bounded dry、explicit circuit recovery、三輪跨 900 秒 scheduler
receipts、三輪 replay drain、final runtime state與 protected hashes全部通過。
本鏈沒有第四次 acceptance probe，也沒有外部 AI、Discord、交易或 PM harness
queue mutation。

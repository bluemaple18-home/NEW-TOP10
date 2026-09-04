# NEW-TOP10 A4 完成／A5 等待 Handoff

## Root question

三條核心 automation 是否完成 A5 規定的連續自然排程，足以從 partial recovery 升為 accepted。

## Current state

- Runtime fixed SHA：`ab7c4180422b028a6a2a39fa311ea0ba591d561e`。
- A4：`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`，CLI exit `0`。
- Daily、External Review Preflight、Fog 的 installed plist 與 launchd owner 均已指向隔離 runtime。
- A4 後未手動觸發 child、未 push、未修改其他五條 disabled job。
- `main` 與 `origin/main` 已同步在 `25d54dab6fa4514ee7f2b2ea0afc3da14a33f6de`。
- Fog 第一個自然週期已失敗；目前有 persistent restart-denied marker。
- Canonical frontier：`docs/operations/CURRENT_OPERATIONAL_FRONTIER.md`。
- Program authority：`docs/tasks/2026-09-03_P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY.md`。

## Waiting conditions

- Fog：連續 2 個 15 分鐘自然 cadence。
- External Review Preflight：連續 2 個 17:40 自然排程，兩個 provider 都要有可判讀 readiness result。
- Daily 自動報牌：連續 2 個交易日 17:30 自然排程；需 child exit `0`、正確 run-date artifact 與 publish/send terminal result。

## Blocker

Fog 在 2026-09-04 20:07 自然啟動後，於 20:12 因 `LIVE_SAMPLE_CADENCE_EXCEEDED` 被 guard 終止；後續 6 次 invocation 被 persistent marker 拒絕。A5 目前為 `BLOCKED_WITH_REPRODUCIBLE_EVIDENCE`。沒有新授權前不得清 marker 或 kickstart。

## Candidate fork

- A6 disabled-job intent reconciliation：`pending`，與 A5 分開；不得自動 enable。
- 任一自然週期失敗時，才依該次 receipt 建立最小 RCA／repair fork。

## Next step

決定 Fog bounded recovery：目前 sampler timing 已回復正常，但第一個 detailed STOPPED receipt 被後續 persistent-denial latest receipt 覆寫，無法證明昨晚五分鐘 stall 的精確來源。先保留 marker；若 Owner 授權 clear，僅允許等待下一次自然 cadence 重試，不做 manual kickstart。

## Evidence

- A4 verdict：`docs/evidence/P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-A4-PREACTIVATION-20260904/a4-activation-verdict-ab7c418.md`
- Activation receipt：同目錄下 `activation-receipt-ab7c418-20260904T195149+0800.json`
- Receipt SHA-256：`0a00d989c5f221feb02ec3bc90874ab2d46983c34bd65b32a93fe8b179b9f7a2`
- A5 Fog failure：`docs/evidence/P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-A5-NATURAL-20260905/a5-fog-first-natural-no-go.md`

## Limits

沒有新授權前，不 kickstart、不補跑、不改 launchd/plist、marker、runtime SHA，不送外部 write、不 push。

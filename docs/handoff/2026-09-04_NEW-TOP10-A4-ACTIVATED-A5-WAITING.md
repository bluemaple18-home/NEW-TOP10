# NEW-TOP10 A4 完成／A5 等待 Handoff

## Root question

三條核心 automation 是否完成 A5 規定的連續自然排程，足以從 partial recovery 升為 accepted。

## Current state

- Runtime fixed SHA：`ab7c4180422b028a6a2a39fa311ea0ba591d561e`。
- A4：`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`，CLI exit `0`。
- Daily、External Review Preflight、Fog 的 installed plist 與 launchd owner 均已指向隔離 runtime。
- A4 後未手動觸發 child、未 push、未修改其他五條 disabled job。
- `main` 與 `origin/main` 已同步在 `25d54dab6fa4514ee7f2b2ea0afc3da14a33f6de`。
- Fog 第一個自然週期已失敗；原 persistent marker 已依 Owner 的單次明確授權清除，目前未復生。
- Canonical frontier：`docs/operations/CURRENT_OPERATIONAL_FRONTIER.md`。
- Program authority：`docs/tasks/2026-09-03_P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY.md`。

## Waiting conditions

- Fog：連續 2 個 15 分鐘自然 cadence。
- External Review Preflight：連續 2 個 17:40 自然排程，兩個 provider 都要有可判讀 readiness result。
- Daily 自動報牌：連續 2 個交易日 17:30 自然排程；需 child exit `0`、正確 run-date artifact 與 publish/send terminal result。

## Blocker

Fog 在 2026-09-04 20:07 自然啟動後，於 20:12 因 `LIVE_SAMPLE_CADENCE_EXCEEDED` 被 guard 終止；後續 6 次 invocation 被 persistent marker 拒絕。Marker 已於 2026-09-05 02:21–02:22 清除，但 launchd 沒建立第 8 次 invocation。RCA 證明 2026-09-04 21:54 的 Restart 被 `cmux` 中斷後，GUI launchd domain 留在 on-demand-only mode；Fog interval event 只 pending，response `36`。A5 目前為 `BLOCKED_BY_GUI_LAUNCHD_DOMAIN`。

## Candidate fork

- A6 disabled-job intent reconciliation：`pending`，與 A5 分開；不得自動 enable。
- 任一自然週期失敗時，才依該次 receipt 建立最小 RCA／repair fork。

## Next step

取得 Owner 對完整 GUI login session／正常重開機的獨立授權，解除失敗 Restart 留下的 on-demand-only domain；之後只等待自然 cadence，不做 manual kickstart。Fog marker 目前不存在，不再重複清除。

## Evidence

- A4 verdict：`docs/evidence/P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-A4-PREACTIVATION-20260904/a4-activation-verdict-ab7c418.md`
- Activation receipt：同目錄下 `activation-receipt-ab7c418-20260904T195149+0800.json`
- Receipt SHA-256：`0a00d989c5f221feb02ec3bc90874ab2d46983c34bd65b32a93fe8b179b9f7a2`
- A5 Fog failure：`docs/evidence/P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-A5-NATURAL-20260905/a5-fog-first-natural-no-go.md`
- A5 GUI launchd domain blocker：`docs/evidence/P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-A5-NATURAL-20260905/a5-fog-marker-clear-launchd-domain-no-go.md`

## Limits

沒有新授權前，不 kickstart、不補跑、不改 launchd/plist、marker、runtime SHA，不登出／重開機，不送外部 write、不 push。

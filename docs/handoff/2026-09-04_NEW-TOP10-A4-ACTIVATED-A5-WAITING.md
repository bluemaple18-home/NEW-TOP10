# NEW-TOP10 A4 完成／A5 等待 Handoff

## Root question

三條核心 automation 是否完成 A5 規定的連續自然排程，足以從 partial recovery 升為 accepted。

## Current state

- Runtime fixed SHA：`ab7c4180422b028a6a2a39fa311ea0ba591d561e`。
- A4：`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`，CLI exit `0`。
- Daily、External Review Preflight、Fog 的 installed plist 與 launchd owner 均已指向隔離 runtime。
- A4 後未手動觸發 child、未 push、未修改其他五條 disabled job。
- Canonical frontier：`docs/operations/CURRENT_OPERATIONAL_FRONTIER.md`。
- Program authority：`docs/tasks/2026-09-03_P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY.md`。

## Waiting conditions

- Fog：連續 2 個 15 分鐘自然 cadence。
- External Review Preflight：連續 2 個 17:40 自然排程，兩個 provider 都要有可判讀 readiness result。
- Daily 自動報牌：連續 2 個交易日 17:30 自然排程；需 child exit `0`、正確 run-date artifact 與 publish/send terminal result。

## Blocker

目前沒有 implementation blocker；只有自然時間尚未滿足。不得用 manual run、kickstart 或舊 artifact 補證。

## Candidate fork

- A6 disabled-job intent reconciliation：`pending`，與 A5 分開；不得自動 enable。
- 任一自然週期失敗時，才依該次 receipt 建立最小 RCA／repair fork。

## Next step

只讀查核自然 invocation、child terminal、artifact、publish/provider、denial 與 lock evidence；兩輪未齊前維持 `PARTIAL_RECOVERY_NATURAL_ACCEPTANCE_PENDING`。

## Evidence

- A4 verdict：`docs/evidence/P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-A4-PREACTIVATION-20260904/a4-activation-verdict-ab7c418.md`
- Activation receipt：同目錄下 `activation-receipt-ab7c418-20260904T195149+0800.json`
- Receipt SHA-256：`0a00d989c5f221feb02ec3bc90874ab2d46983c34bd65b32a93fe8b179b9f7a2`

## Limits

沒有新授權前，不 kickstart、不補跑、不改 launchd/plist、marker、runtime SHA，不送外部 write、不 push。

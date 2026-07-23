---
id: VOLUME-CLIMAX-WARNING-SHADOW-01
status: COMPLETED_MONITORING
type: prospective-research-monitor
---

# Regime-conditioned Volume Climax Warning Shadow

## Root question

既有 `volume_climax_reversal` 歷史訊號能否在不改 Top10、不發推播的前提下，持續累積真正前瞻的 warning-only 證據？

## Frozen contract

- seal date：`2026-07-23`；只接受 seal 後的 ranking date。
- observation universe：該日及之前最近 7 個 canonical ranking files 曾出現的股票。
- 訊號必須只用 observation date 當下資料：
  - `volume_ratio_20d >= 1.8`
  - `long_upper_shadow = true`
- regime activation：只在 `RISK_ON` 啟用 warning；其他 regime 仍記 raw signal，但不啟用 warning。
- ledger 以 `ranking_date` 唯一、排序、append-only；既有日期不得重算。
- 訊息語意只能是「短線追價要保守」，不得寫成賣出、停損、減碼。

## Boundaries

- research／warning-only。
- 不改 model、ranking、`risk_adjusted_score`、權重、推薦文案或推播。
- monitor failure 只進 research receipt，不阻斷 production daily。
- 未達前瞻樣本門檻前，`promotion_allowed=false`。

## Acceptance

- 現有資料首跑為合法空 ledger，因沒有 seal 後 ranking date。
- fixture 證明新日期可追加、RISK_ON 才啟用 warning、重跑冪等。
- daily combined receipt 明確包含 volume-climax component。
- verifier 檢查 append-only key、邊界及 component／ledger receipt 一致。

## Result

- 真實資料：`WAITING_FOR_POST_SEAL_DATES`，`0` observation；符合 seal contract。
- fixture：RISK_ON raw `1`／active `1`，RISK_OFF raw `1`／active `0`。
- 同日重跑：追加 `0`，既有 observation byte-equivalent。
- combined daily receipt：`OK`，Chip／Event／Volume Climax 三個 component 均成功。
- production promotion：`false`。

驗證 receipt 見 `docs/evidence/VOLUME-CLIMAX-WARNING-SHADOW-01/result.md`。

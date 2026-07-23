# VOLUME-CLIMAX-WARNING-SHADOW-01 Result

## Decision

`MONITORING_PROSPECTIVELY`

`volume_climax_reversal` 保留為 regime-conditioned warning-only 候選。它不是賣出訊號，也不進 Top10 推薦；從 seal 後新日期開始累積前瞻證據。

## Frozen behavior

- signal：`volume_ratio_20d >= 1.8 AND long_upper_shadow`
- active regime：`RISK_ON`
- watchlist：最近 7 個 canonical ranking days 曾入榜股票
- seal：`2026-07-23`
- append-only key：`ranking_date`
- promotion／ranking mutation／push：全部禁止

## Verification

- Python compile：PASS
- fixture：
  - RISK_ON raw `1`／active `1`
  - RISK_OFF raw `1`／active `0`
  - 重跑 observations appended `0`
  - 舊 observation 未改寫
- 真實資料首跑：
  - latest ranking date：`2026-07-23`
  - post-seal observations：`0`
  - status：`WAITING_FOR_POST_SEAL_DATES`
- combined daily monitor：`OK`
- daily orchestration tests：`7 passed`
- Chip existing verifier：PASS
- Volume Climax verifier：PASS
- combined receipt verifier：PASS
- `git diff --check`：PASS

## Interpretation

目前沒有新前瞻績效結論；0 筆是正確結果，因 seal 後尚無 ranking date。下一個交易日 daily runner 會自動開始累積。達到 60 個前瞻 observation dates 後，才允許另開 promotion review，且 review 仍須檢查 5D downside、10D reversal 與月份穩定度。

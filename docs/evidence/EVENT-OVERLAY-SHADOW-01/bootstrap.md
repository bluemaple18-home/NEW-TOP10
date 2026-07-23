# EVENT-OVERLAY-SHADOW-01 Bootstrap Evidence

status: GO（shadow infrastructure）／WAITING（new OOS）

## Frozen candidate

- candidate：`event_liquidity_constrained_overlay_0.10_v1`
- config：`config/event_liquidity_overlay_shadow_v1.json`
- config SHA-256：`a665ed085403e2994114d005818b34d34c4371ef3313759283c744c3e5f5ef46`
- seal date：`2026-07-08`
- event weight：10%
- retain baseline：7/10
- candidate pool：Top30

## Verification

```bash
.venv/bin/python scripts/verify_chip_overlay_append_only_shadow.py
.venv/bin/python scripts/run_feature_group_overlay_append_only_shadow.py \
  --config config/event_liquidity_overlay_shadow_v1.json \
  --ledger artifacts/model_experiments/event_overlay_shadow_ledger_v1.json
```

- verifier：`CHIP_OVERLAY_APPEND_ONLY_SHADOW_OK`
- latest source date：`2026-07-22`
- latest mature date：`2026-07-08`
- observations：`0/60`
- status：`WAITING_FOR_NEW_OOS_DATES`

## Invariants

- config digest drift 時拒絕沿用 ledger。
- seal 前 regime anchor drift 時 fail loud。
- 同一 ranking date 不重算、不覆寫。
- acceptance 固定使用最早 60 個完整日期。
- unsupported regime、coverage 不足、OHLC 不完整均輸出結構化 warning。
- production model、ranking、weights 不修改。

## Waiting condition

資料出現 seal 後且完成 D+10 outcome 的新日期。等待成熟是正常狀態，不是權限或程式 blocker。

# CHIP-OVERLAY-SHADOW-01 Bootstrap Evidence

status: GO（shadow 基礎設施）／WAITING（新 OOS 日期）

## Evidence

- frozen config：`config/chip_liquidity_overlay_shadow_v1.json`
- runner：`scripts/run_chip_overlay_append_only_shadow.py`
- verifier：`scripts/verify_chip_overlay_append_only_shadow.py`
- runtime ledger：`artifacts/model_experiments/chip_overlay_shadow_ledger_v1.json`

## Verification

```bash
.venv/bin/python scripts/verify_chip_overlay_append_only_shadow.py
.venv/bin/python scripts/run_chip_overlay_append_only_shadow.py
```

- verifier：`CHIP_OVERLAY_APPEND_ONLY_SHADOW_OK`
- candidate config SHA-256：`347afdd8fc96e801c4942546f8440a686ab9b912a59b826406b4b873abb72ab2`
- regime anchor：271 rows through `2026-07-08`
- regime anchor SHA-256：`71e89bd35f8e82b59907a0ebb3944836eb4f70a428d394da4742a77d90dbf8b4`
- latest source date：`2026-07-22`
- latest mature date：`2026-07-08`
- observations：`0/60`

## Business invariants

- frozen config 改動後不得沿用既有 ledger。
- seal date 以前 regime label 漂移時 fail loud。
- observation 只能新增；同一日期重跑不覆寫。
- runtime ledger 採 primary integrator machine 單寫者契約。
- acceptance 永遠使用 seal 後最早 60 個完整日期；第 61 日以後不能翻案。
- unsupported regime、coverage 不足或 OHLC 不完整都輸出結構化 warning。
- runner 不修改 production model、ranking 或權重。

## Waiting condition

features 與 append-only regime history 出現 `2026-07-08` 之後、且已完成 10 個交易日 outcome 的新日期。等待資料成熟是正常狀態，不是 blocker。

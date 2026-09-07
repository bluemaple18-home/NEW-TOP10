---
id: REPAIR-RADAR-01-P1-D-G1-STABLE-PUBLIC-ERRORS
status: repair-ready
type: repair
generation: 1
---

# REPAIR-RADAR-01-P1-D-G1-STABLE-PUBLIC-ERRORS

## Finding

- `RADAR-P1D-STRICT-001`（P1）：P1-D public builder 對可到達的 malformed inputs 洩漏 pandas/Python native exceptions，違反 `AS-US001-06`。

## Reproduced RED

- `signal_column="rsi"` 且 `required_features=("rsi",)` 的合法 eligible SignalSpec → pandas `ValueError: cannot reindex on an axis with duplicate labels`。
- `snapshot_manifest_path=None` → built-in `TypeError`。
- external specs iterable 在 `__iter__` 拋 `RuntimeError` → native `RuntimeError` 穿透。
- Evidence：`.work/RADAR-01-P1-D/evidence/review_red_public_error_contract.json`。

## Root-cause hypotheses

1. `semantic_columns` 未先拒絕同一欄位同時作 required feature 與 signal result，造成 duplicate-label frame；加入明確 structural validation 後該 RED 應轉為穩定 `HIST_SIGNAL_COLUMN_CONFLICT`。
2. P1-D 在進 scanner path parsing 前未正規化公開 path 型別；只在 public boundary 驗證 `str | Path` 後，None 應轉為穩定 `HIST_*_PATH_TYPE_INVALID`。
3. `tuple(specs)` 只捕捉 `TypeError`，但 iterator 是外部 input 執行面；只包住 materialization 並捕捉其 `Exception` 後，外部 iterable failure 應轉為穩定 `HIST_SPEC_CONTAINER_UNREADABLE`，且不得 broad-catch 後續內部 pandas 計算。

## Scope

- 只修改 `app/signals/historical_statistics.py` 與 `tests/test_signal_historical_statistics.py`。
- 加入上述三個 public-interface RED/GREEN regression。
- 不改統計、baseline、effective-N、MAE、scanner seam、default eligibility 或其他產品範圍。

## Acceptance

- `/tmp/radar_p1d_review_red.py` exit 0，三條皆回 `HistoricalStatisticsError` + 穩定 `HIST_*` reason。
- P1-D targeted 與 P1-A～P1-C/Daily Close regression 全綠。
- 無 `[DBG-` 殘留；`git diff --check` 通過。
- 回原 Reviewer targeted re-review；不得由 Repair 自行關閉 finding。

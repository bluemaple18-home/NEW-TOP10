---
card_id: TSKG-MFO-01
status: DELIVERED_CANDIDATE
verified_on: 2026-07-20
verification_kind: schema_gate_and_regression
---

# TSKG-MFO-01 verification

## Implemented candidate

- 新增 closed-schema `SecurityFlowObservationFixture`。
- 新增 8 筆、2 個 synthetic Security、4 種 investor type 的 raw fixture。
- `net_buy_value_1d` 固定為 integer TWD。
- semantic key 固定為 `(security_id, trade_date, investor_type)`。
- 支援 deterministic ordering、exact lookup、defensive copy 與 summary。
- `formula_version=raw-only-v1`；5d/20d、價格、加速度、force ratio、anomaly 與交易／預測欄位均被 schema gate 拒絕。
- 沒有新增 API、資料庫、來源 adapter、Theme aggregation、Top10 feature/ranking 或 UI。

## TDD evidence

### RED

```text
uv run --with fastapi python -m unittest tests.test_tskg_mfo01
ModuleNotFoundError: No module named 'app.tskg.flow_observation'
```

### GREEN

```text
uv run --with fastapi python -m unittest tests.test_tskg_mfo01
Ran 7 tests in 0.004s
OK
```

Covered gates：

- top-level／provenance／evidence／observation closed schema。
- fixture/schema/formula version。
- ISO trade date、RFC 3339 UTC、retrieved ≥ observed。
- investor type、TWD、integer amount、freshness/is_stale coherence。
- duplicate observation ID／semantic key、dangling source/evidence。
- raw-only 與 prohibited derived/trading/prediction fields。
- deterministic order、exact lookup、defensive copy、summary。

## Regression attempts and stop condition

### Attempt 1

```text
uv run --with fastapi --with httpx python -m unittest \
  tests.test_tskg_mfo01 tests.test_tskg_slc01 tests.test_tskg_src01
Ran 46 tests
ERROR: app.api.main import environment missing pandas
```

結果：45 個 test path 已執行至通過；唯一 error 是環境 dependency import，不是行為 assertion failure。

### Attempt 2

```text
uv run --with-requirements requirements.txt python -m unittest ...
```

結果：系統預設 Python 3.14 無法 build pinned `lxml==4.9.4`；屬既有 requirements/Python compatibility blocker。

### Attempt 3

```text
uv run --python 3.13 --with fastapi --with httpx --with pandas python -m unittest ...
```

結果：sandbox 無法初始化共用 uv cache（operation not permitted）。

同一 validation-environment blocker 已累計三次；該輪依 repo 停損規則停止，未做第 4 次重試。

## Resumed validation

新一輪先嘗試 Python 3.13＋獨立 temporary uv cache，但 `uv 0.9.27` 在 macOS system-configuration 初始化時 panic；Codex bundled Python 3.12 又未包含 FastAPI。最後改用專案現成、依賴完整的 `.venv` 做行為回歸：

```text
<repo-root>/.venv/bin/python -m unittest \
  tests.test_tskg_mfo01 tests.test_tskg_slc01 tests.test_tskg_src01
Ran 46 tests in 1.153s
OK
```

結果：MFO-01 7 tests、SLC-01 22 tests、SRC-01 17 tests，共 `46/46 PASS`。執行器為 Python 3.11.14；Python 3.13 尚未成功 provision，故版本矩陣保持 caveat，不把 3.11 行為 PASS 冒充 3.13 runtime acceptance。

## Remaining boundaries

- MFO-01 focused contract：`PASS`。
- Full TSKG behavioral regression：`46/46 PASS`（Python 3.11.14）。
- Python 3.13 environment acceptance：`NOT_RUN / ENVIRONMENT_BLOCKED`。
- MFO-02/03、ThemeFlowObservation、rolling/derived formula：未開始。
- MOPS／TWSE／Tide 或任何真實來源：未使用、未核准。
- SLC-02、OQ-SRC-01 與 Source Gate：不受本卡解除。
- UI-MFR：仍為 `BACKLOG / NOT AUTHORIZED`。

## Candidate disposition

候選已具 focused gate 與完整 TSKG behavioral regression 證據，可進入 Review。Python 3.13 caveat 必須保留；在 Review 前不整合主線、不推送、不宣稱完成。

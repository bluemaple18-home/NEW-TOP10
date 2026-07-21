---
card_id: TSKG-MFO-01
status: INTEGRATED
accepted_on: 2026-07-20
acceptance_kind: synthetic_raw_observation_contract
---

# TSKG-MFO-01 mainline acceptance

## Accepted scope

- Synthetic-only raw `SecurityFlowObservation` closed schema。
- `net_buy_value_1d` 為 integer TWD；日期、RFC3339 UTC 字串、freshness、source/evidence 與 semantic uniqueness 具 deterministic gate。
- 支援 deterministic ordering、exact lookup、defensive copy 與 summary。
- Invalid JSON 轉為 `FlowObservationContractError` 並保留 `JSONDecodeError` cause；檔案系統 `OSError` 不被吞掉。
- 5d/20d、價格、加速度、force、anomaly、Theme aggregation 及交易／預測欄位維持禁止。

## Evidence lineage

- Original candidate：`11c68e9c32812a394788c95bc69a8763a92a8929`。
- Initial independent Review：`24657766a3484d77f3383b5ee8237df0e0614926`，verdict `NO_GO`。
- Repair-1 candidate：`69871f34adaf6ab475ae859718095fe581eee794`。
- Re-review：`879b4e930a4b30bc500a24d54fbf696de2687e67`，final verdict `GO`。
- Mainline integrated through：`7145762`。

## Mainline verification

```text
<repo-root>/.venv/bin/python -m unittest \
  tests.test_tskg_mfo01 tests.test_tskg_slc01 tests.test_tskg_src01
Ran 49 tests in 0.768s
OK
```

- Independent re-review malformed probes：`112/112 PASS`。
- `git diff --check`：PASS。
- Python 3.13：`NOT_RUN` caveat；行為驗證執行器為 Python 3.11.14，不宣稱 3.13 runtime acceptance。

## Boundary

本 acceptance 不批准真實法人資料來源、MOPS/TWSE ingestion、`ThemeFlowObservation`、rolling/derived formula、API、Neo4j/Postgres、scheduler、前端市場雷達或 Top10 feature/ranking。UI-MFR 仍為 `BACKLOG / NOT AUTHORIZED`，OQ-SRC-01 與 SLC-02 不受本卡解除。

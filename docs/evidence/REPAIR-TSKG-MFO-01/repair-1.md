# REPAIR-TSKG-MFO-01-1 Repair Evidence

## Lineage 與邊界

- 狀態：`REPAIR_DELIVERED`／`DELIVERED_CANDIDATE`，不代表 Review GO、整合或完成。
- Repair card parent：`b40fe8992be4471f0939d485c5e520ea4a03519b`。
- Review NO_GO：`24657766a3484d77f3383b5ee8237df0e0614926`。
- Reviewed candidate：`11c68e9c32812a394788c95bc69a8763a92a8929`。
- Reviewer thread：`019f7e09-5c64-7dd1-8018-e97e0bafc865`。
- Repair candidate：本次 repair commit；完整 SHA 由交付回報提供，避免 commit 自參照。
- 只修改兩個 P2；未修改 reviewer evidence/card、原 MFO card/evidence、fixture、
  exports 或 dependency，且未連外、整合或 push。

## TDD evidence

先只新增三個 public contract tests，再執行 MFO focused suite。

### RED

```text
<main-workspace>/.venv/bin/python -m unittest tests.test_tskg_mfo01
Ran 10 tests in 0.010s
FAILED (failures=2, errors=1)
```

- `observed_at` 與 `retrieved_at` 各注入 aware UTC `datetime`，兩案皆未丟出
  `FlowObservationContractError`。
- invalid JSON `{` 直接漏出 `json.JSONDecodeError`。
- missing-file probe 已是 `FileNotFoundError`，證明 repair 前 OSError passthrough 邊界。

### GREEN

最小 implementation：

- `parse_utc_instant()` 前要求兩個 timestamp 欄位皆為 `str`。
- `from_file()` 只捕捉 `json.JSONDecodeError`，轉譯為
  `FlowObservationContractError` 並使用 `raise ... from error`；不捕捉 `OSError`。

```text
<main-workspace>/.venv/bin/python -m unittest tests.test_tskg_mfo01
Ran 10 tests in 0.009s
OK
```

## Regression 與 malformed probes

三模組完整 suite（原 46 tests 加本次 3 tests）：

```text
<main-workspace>/.venv/bin/python -m unittest \
  tests.test_tskg_mfo01 tests.test_tskg_slc01 tests.test_tskg_src01
Ran 49 tests in 0.730s
OK
```

原 46-test regression 另以原 MFO 7 個 test methods 加 SLC/SRC 39 tests 精確重跑：

```text
Ran 46 tests in 0.734s
OK
```

Reviewer-equivalent temporary harness 完全離線，覆蓋所有 scalar 欄位與 top-level、
provenance、evidence、observation container/item 的 list／dict／null／bool confusion：

```text
type_confusion=112/112
datetime_gate=2/2
invalid_json_cause=JSONDecodeError
missing_file=FileNotFoundError
```

Probe script 位於 temporary path，未加入 candidate。

## Verification gates

- `git diff --check`：final verification 通過。
- Exact allowlist：只允許兩個 code/test 檔、本 Repair card 與本 Repair evidence。
- Host-path scan：final verification 通過；committed docs 不保留本機絕對路徑。
- Review evidence/card、原 MFO card/evidence、fixture、exports：diff 為空。
- Post-commit worktree/index：交付回報確認。

## Remaining risk

- Python 3.13：`NOT_RUN`；本次沿用既有 Python 3.11.14 離線環境，不宣稱
  Python 3.13 acceptance。
- 本 repair 只處理 raw MFO-01 contract；不批准 Theme、衍生公式、外部來源、API、
  UI 或 Top10 行為。
- Finding 是否關閉只能由原 reviewer re-review 判定。

---
id: REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01
status: mainline-accepted-local
type: result
---

# Result

## Changed files

- `docs/operations/top10-storage-policy.json`
- `docs/operations/top10-storage-safety.md`
- `tests/test_storage_safety.py`
- `.work/REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01/status.md`
- `.work/REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01/result.md`

## RED

```text
.venv/bin/python -W error::ResourceWarning -m unittest tests.test_storage_safety.StorageSafetyRegressionTest.test_fog_meters_sibling_external_review_changes_and_keeps_unknown_fail_closed
exit_code=1
AssertionError: ('artifacts/external_review/new.json', 'artifacts/external_review/old.json') != ()
Ran 1 test in 0.002s
FAILED (failures=1)
```

## GREEN

```text
.venv/bin/python -W error::ResourceWarning -m unittest tests.test_storage_safety.StorageSafetyRegressionTest.test_fog_meters_sibling_external_review_changes_and_keeps_unknown_fail_closed
exit_code=0
Ran 1 test in 0.004s
OK

.venv/bin/python -W error::ResourceWarning -m unittest tests.test_storage_safety
exit_code=0
Ran 90 tests in 15.717s
OK

.venv/bin/python -m pytest tests/test_fog_natural_acceptance.py -q
exit_code=0
34 passed in 2.18s

policy_load=OK jobs=8
policy_delta=OK only=fog-research-worker.meter_paths:+artifacts/external_review

git diff --check
exit_code=0
```

`tests.test_fog_natural_acceptance` 是 pytest function suite；先以 unittest runner 呼叫時
`Ran 0 tests`／exit `5`，改用 pytest 後執行 34 tests 並全綠。

## Residual risk

- 兩名獨立 blind Reviewer 均為 `GO`，無未解 P0/P1；Mainline acceptance 已通過。
- Reviewer A 記錄既存 `measure_paths()` 的檔案消失 TOCTOU P2；發生時會 fail closed，未造成容量
  漏算或本卡 contract 放寬，留待獨立 bounded repair。
- 未在 production 重跑 Fog／external-review overlap；production marker 保留，未清除、未部署、
  未 kickstart、未 push。
- 此 GREEN 只證明 exact shared subtree policy contract；不宣告 production fixed，也不處理
  external-review child exit `1`。

## Mainline verification

```text
tests/test_automation_runtime_activation.py: 58 passed
tests/test_fog_storage_validation.py: 11 passed
candidate inventory: 1291575653 bytes / 13434 files
Fog limits: 2147483648 bytes / 30000 files
fixed candidate hashes: MATCH
debug markers: none
git diff --check: PASS
```

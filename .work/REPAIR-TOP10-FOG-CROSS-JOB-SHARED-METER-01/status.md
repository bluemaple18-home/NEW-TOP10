---
id: REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01
status: mainline-accepted-local
type: status
---

# Status

root question：如何讓已觀察的 cross-job shared subtree 在 Fog 週期內受容量 hard ceilings 納管，且不誤報 unmetered write？

blocker：Fog policy 的 `registered_write_paths` 包含 `artifacts`，但 `meter_paths` 未包含 sibling job 合法寫入的 `artifacts/external_review`。

fork：若 exact subtree metering 會削弱 unknown-write gate、超出現有 ceilings 或需要新 scheduler/ledger，停止回 Mainline，不擴 scope。

目前狀態：`MAINLINE_ACCEPTED_LOCAL / PRODUCTION_MARKER_PRESERVED / DEPLOY_PENDING`。

限制：不清 marker、不 deploy、不 kickstart、不 push、不改 plist 或 production source。

## Worker fact gate

- task_as_stated：以單一行為測試重現 Fog 對 sibling `artifacts/external_review` 新增／刪除的 registered-unmetered RED，再只擴充 exact subtree meter。
- must_change：Fog `meter_paths`、對應操作文件、Storage Guard regression test。
- must_not_touch：production Python／shell／plist、整個 `artifacts` meter、ceilings、`launch_verified`、cleanup allowlist、其他 job policy、persistent marker。
- minimum_success_condition：shared subtree add/delete 不再 unmetered，該 subtree bytes/files 精確計量，`source.py` 仍 unknown fail closed，affected suites 與 policy load 全綠。
- files_expected_to_change：`docs/operations/top10-storage-policy.json`、`docs/operations/top10-storage-safety.md`、`tests/test_storage_safety.py`、本卡 `status.md`／`result.md`。
- source seam：`load_policy()` → `JobPolicy.meter_paths`；`measure_paths()` 去重計量；`registered_changed_paths_outside_meter()` 與 `unknown_changed_paths()` 維持既有 fail-closed 分類。
- rollback：回退上述三個交付檔與本卡 evidence；不涉及 runtime mutation。

## Worker outcome

- RED：新增 sibling add/delete 行為測試後，Fog policy 回傳
  `artifacts/external_review/{new,old}.json`，exit `1`。
- GREEN：Fog 只新增 exact `artifacts/external_review` meter；新增測試、Storage Guard 90 tests、
  Fog natural acceptance 34 tests、8-job policy load 與 exact policy delta 驗證均通過。
- 未執行：blind review、production capacity recheck、marker clear、deploy、kickstart、commit、push。

## Strict review 與 Mainline gate

- Blind Reviewer A：`GO`，無 P0/P1；記錄一項既存 `measure_paths()` 檔案消失競態的 P2，結果為
  fail closed，不影響本卡 shared-meter 契約。
- Blind Reviewer B：`GO`，無 findings；activation failure-state 58 tests 全綠。
- Mainline：Storage Guard 90 tests、Fog natural acceptance 34 tests、Fog storage validation
  11 tests、activation failure-state 58 tests 全綠；observed-path probe GREEN，policy delta 只有
  `fog-research-worker.meter_paths:+artifacts/external_review`。
- Candidate production inventory：`1,291,575,653 bytes / 13,434 files`，低於 Fog
  `2 GiB / 30,000 files` ceiling；尚未把 local acceptance 宣稱為 production fixed。
- Production 舊 marker 保留；未清除、未 kickstart、未 push。部署須另走既有 activation transaction。

---
id: REPAIR-NEW-TOP10-R17-CLEANROOM-FILE-BUDGET
status: COMPLETE / R18_EXTERNAL_GREEN
type: runtime-repair
risk: high
baseline: abb97d8
---

# R17 Clean-room File Budget Repair

👉 [假設與目標確認] 目標：讓 external fog clean-room 在既定 `50,000` files 內完成 cleanup；邊界：不調高 file／byte budget、不刪 source、不減代表性 workload、不啟用 launchd／push／deploy；驗收：copy-contract RED→GREEN、受影響回歸通過，R18 另取得授權。

## R17 evidence

- cycle 1：runtime `OK`，peak RSS `771,194,880 bytes`，topic run count `1`，unknown writes `[]`。
- cycle 2：runtime `OK`，peak RSS `810,205,184 bytes`，topic run count `1`，unknown writes `[]`。
- summary verdict：`PASS_CANDIDATE`；外層 lifecycle exit `2 / NO_GO: budget exceeded`。
- 唯讀重算 clean-room copy baseline：`3,710,152,782 bytes / 58,458 files`；因此超的是 `50,000` file count，不是 5 GiB bytes。

## Falsifiable hypotheses

1. 若超限主因是 clean-room 把可再生的歷史 replay／staging outputs 一併複製，排除這些 source outputs 後 projected baseline 應下降，runtime 仍可自行建立當日輸出。
2. 若 `artifacts/model_experiments` 全量是必要 authority，縮減後相關 runtime contract tests 應失敗；只允許保留 fog call tree 明確引用的 regime authority files，不以整個目錄作隱性 authority。

## Feedback loop

- RED：`.venv/bin/python -m pytest -q tests/test_external_fog_revalidation.py::ExternalFogRevalidationTest::test_copy_project_excludes_generated_outputs_and_keeps_explicit_regime_authorities`；舊 copy 保留 4,829 個額外 model-experiment files，測試因實際 copy contract 不符而失敗。
- GREEN：同一命令修後 `1 passed`；實際 sandbox copy 另斷言 `<50,000 files / <5 GiB`。

## History

- 2026-09-02：CodeGraph 未指出 clean-room copy 的直接測試 seam；原始碼確認 public seam 為 `copy_project()`／`copy_ignore()`，既有 `tests/test_external_fog_revalidation.py` 已覆蓋 docs authority。
- 2026-09-02：排除可再生的 `artifacts/weekend_training/staging` 與歷史 `replay_runs_*`；`artifacts/model_experiments` 改為 explicit authority，只複製 base regime history 與 append-only extension 兩檔。
- 2026-09-02：projected copy baseline 降為 `3,319,144,297 bytes / 48,707 files`，未調高 5 GiB／50,000 上限。
- 2026-09-02：受影響回歸 `86 passed, 31 subtests passed`；等待 R18 外接完整 cleanup evidence。
- 2026-09-03：R18 以相同 5 GiB／50,000 files lifecycle budget 完成兩輪代表性 fog runtime，外層 lifecycle exit `0` 且 clean-room 已移除；file-budget blocker 關閉。兩輪 peak RSS `799,424,512`／`758,562,816 bytes`，topic run count 各 `1`，unknown writes `[]`。

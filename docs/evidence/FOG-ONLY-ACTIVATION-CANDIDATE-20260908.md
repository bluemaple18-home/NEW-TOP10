# Fog-only activation candidate evidence（2026-09-08）

## 結論

- 狀態：`CANDIDATE_GREEN / NON_PRODUCTION`
- 範圍：沿用既有 `ActivationTransaction`，新增 allowlist job selector。
- Fog-only 參數：`--job fog-research-worker`。
- 未指定 `--job` 時仍維持既有三條核心 job，保留相容性。
- 尚未 push、deploy、清除 marker、kickstart 或恢復 `top10-fog` heartbeat。

## 邊界證據

- selector 在任何 runtime probe、檔案或 launchctl 副作用前驗證；空、重複、未知值均 fail closed。
- Fog-only 成功與 rollback 路徑只迭代選取後的 `self.jobs`。
- 未選的 daily、external-review-preflight plist 納入 out-of-scope hash 驗證。
- receipt 的 `target_labels` 與 `jobs` 只記錄實際選取範圍。
- failure-state 測試涵蓋 denial mirror／clear、bootout、plist replace、bootstrap、receipt seal。
- 測試明確驗證未選 job 不產生 marker、lock、prestate snapshot，且 launchctl topology 不變。
- 未選核心 plist 若在 transaction 中漂移，activation 會拒絕成功並 fail closed。

## 驗證

- `tests/test_automation_runtime_activation.py`：`74 passed`。
- 關聯 suite（storage safety、activation、Fog runtime health、Fog natural acceptance）：`218 passed, 38 subtests passed`。
- `py_compile`：通過。
- `git diff --check`：通過。

## 獨立審查

- Blind-A：初審提出 CLI error boundary 與 selector-specific artifact invariant 兩項 P2；修補後 re-review 為 `GO`，無殘留 P0/P1/P2。
- Blind-B：初審提出相同兩類 P2；修補後 re-review 為 `GO`，無新增或殘留 P0/P1/P2。

## Production 前置條件

本文件不授權 production mutation。部署前仍需 Owner 明確授權，且只可操作 Fog job；不得順帶切換 daily 或 external-review-preflight。

---
id: REPAIR-NEW-TOP10-STORAGE-DENIAL-EVIDENCE-PRESERVATION
status: READY_FOR_AUTHORIZED_ACTIVATION
type: bounded-repair
risk: standard
---

# 保留 Storage Guard 首次停損證據

👉 [假設與目標確認] 目標：後續被 persistent marker 拒絕時，latest receipt 仍保留首次停損原因與違規路徑；邊界：不放寬 write allowlist、不清除 marker、不重啟 launchd、不修改 production runtime；驗收：回歸測試先 RED 後 GREEN，受影響測試與 `git diff --check` 通過。

## 事實與假說

- 2026-09-03 09:32:49，worker 執行期間由另一條主線寫入 `docs/tasks/2026-09-03_MONITOR-NEW-TOP10-FOG-LIVE-REVALIDATION.md`。
- 09:32:55 worker 收到 SIGTERM，09:33:05 marker 記錄 `UNREGISTERED_WRITE_PATH`；後續嘗試把 latest receipt 覆寫成只有 `PERSISTENT_RESTART_DENIED_MARKER`，且清空 `unknown_changed_paths`。
- 假說一：若 denial marker 保存首次 receipt 的 path evidence，後續拒絕 receipt 可完整保留 RCA 線索。
- 假說二：若只修 latest receipt、不修 marker，第一次 receipt 被覆寫後仍無法還原 path，故不足。
- 已證偽：不是 worker 自己寫入 `docs/tasks/`；該檔案是 09:33:04 的 Mainline monitor dispatch commit，worker 入口與其呼叫鏈沒有 docs task writer。
- 已證偽：不是容量或 cadence ceiling 先觸發；持久 marker 的唯一原始 reason 是 `UNREGISTERED_WRITE_PATH`。

## 驗證計畫

1. 新增會觸發 unregistered write、再重跑一次的測試；修復前應因第二份 receipt 遺失原始 evidence 而失敗。
2. 最小修改 marker payload 與 persistent-denial receipt 組裝；同一測試應轉綠。
3. 執行 storage safety 受影響測試、全檔測試與 `git diff --check`。

## Task history

- CONTEXT_READY：CodeGraph 指向 `run_guarded_job`、`unknown_changed_paths` 與 `tests/test_storage_safety.py`；原始碼確認 marker 與 latest receipt 在同一 public command seam 產生。
- RED：`.venv/bin/python -m pytest tests/test_storage_safety.py::StorageSafetyRegressionTest::test_persistent_denial_preserves_original_unknown_write_evidence -q` 因 marker 缺少 `unknown_changed_paths` 而失敗，重現首次證據無法跨 persistent denial 保存。
- GREEN：同一測試 `1 passed`；`tests/test_storage_safety.py` 為 `69 passed, 31 subtests passed`。
- 全專案回歸：`1250 passed, 285 subtests passed, 10 failed`；十項失敗均位於既有 Research Spine／proposal authority drift 或舊 fixture 缺新參數，與本卡只修改的 storage guard evidence seam 無交集。
- 未清除現有 restart-denied marker、未啟停 launchd、未操作 production runtime。
- Activation Review Round 1：兩位獨立 Reviewer 均 `NO-GO`；共同指出 exception branch 會洗掉已觀察 evidence，semantic malformed marker 可能拋 `TypeError`，且缺少 failure injection coverage。
- Round 1 RED：malformed marker 測試因 `reasons=null` 拋 `TypeError`；exception-after-detection 測試顯示 marker 的 `unknown_changed_paths=[]`。
- Round 1 repair：persistent denial 僅接受 JSON list-of-strings；exception branch 合併既有 stop reasons、unknown paths 與 registered-unmetered paths；補 legacy/malformed、termination failure、registered-unmetered、command-not-spawned、marker/receipt one-time write failure測試。
- Round 1 GREEN：受影響測試 `3 passed, 2 subtests passed`；單次 marker/receipt write failure `1 passed, 2 subtests passed`；storage safety 全檔 `72 passed, 35 subtests passed`；`py_compile` 與 `git diff --check` 通過。
- Activation Review Round 2：一位 Reviewer `GO`；另一位 `NO-GO`，證明直接進 exception branch 時若首次 marker write 暫時失敗，可能沒有 durable marker。Mainline 保留分歧並採 fail-closed `NO-GO`。
- Round 2 RED：直接 preflight sampler error＋首次 denial marker write `OSError` 會向外拋出，且 marker／receipt 均不存在。
- Round 2 repair：exception branch 對 denial marker 增加一次 bounded、無 sleep retry；持續失敗仍明確拋錯，不形成無限 retry。
- Round 2 GREEN：新 failure injection `1 passed`；storage safety 全檔 `73 passed, 35 subtests passed`；`py_compile` 與 `git diff --check` 通過。
- Activation Review Round 3：兩位互不讀取對方 verdict 的獨立 Reviewer 均 `GO`，無 blocking activation finding。

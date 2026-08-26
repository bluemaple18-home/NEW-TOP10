# Verification 與最終判定

## 最終判定

`READY_FOR_REVIEW / GLOBAL NO-GO`。

本卡沒有八個 job 各兩個代表性完整週期，因此不能解除 storage NO-GO。八個 production
`launch_verified` 全部維持 `false`；八個 launchd label 全程 disabled，沒有 load、enable、
kickstart、restart、reload、merge、push、deploy、發布或外部訊息。

## Spec axis

- AC-1 validation-only 隔離：`PASS`。無 `.git` sandbox、manual marker、root/job、非 symlink
  path、cache/temp 收斂與 production fail-closed 都有 tests/receipts。
- AC-2 兩個代表性週期：`FAIL`。只有 retrain scheduled monitor 完成兩週期，但沒有觸發真正
  retrain；其他 job 分別 stop、empty、external-authority blocked 或 child gate failed。
- AC-3 預算與峰值：`PARTIAL`。只對 retrain monitor 分支有兩週期 projection；其餘不填猜測值。
- AC-4 回收與隔離停損：`PASS`。實際回收 `151684204` bytes／`5964` files；hard-RSS target
  被停止、restart 被拒絕、unrelated process 存活、main protected hashes 不變。
- AC-5 逐 job/global 判定：`PASS`。八 job 都有明確 reason-coded `NO-GO`，global 為 `NO-GO`。

## Standards axis 與 code review

依 `code-review-gate` 審查 correctness、regression、security/path traversal、performance 與
testing。Review 中發現 validation path 原先在 `resolve()` 後檢查 symlink，無法辨識 symlink
component；已改為 lexical root 內逐 component 檢查，再 strict resolve 並確認仍在 resolved
root。另補 non-finite hard runtime 拒絕。修後未發現阻塞 code finding。

剩餘風險是產品 evidence，而不是未修 code finding：重型 retrain 分支、非空 PM workload、
reference file-count budget、fog 完整兩週期、baseline review gate 與外部 provider authority
都尚未通過，因此 production 仍 fail closed。

## Tests 與 checks

```text
uv run pytest tests/test_storage_safety.py -q
19 tests passed, 16 subtests passed

bash -n scripts/run_with_storage_guard.sh scripts/run_daily_research_quota.sh
PASS

.venv/bin/python -m py_compile app/storage_safety.py scripts/storage_safety.py tests/test_storage_safety.py
PASS

jq empty docs/operations/top10-storage-policy.json docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/job-verdicts.json
PASS

git diff --check
PASS
```

Full suite：

```text
.venv/bin/python -m pytest -q
652 passed, 1 failed, 270 subtests passed, 4 warnings
```

唯一 failure：
`tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`。
這與 parent evidence 相同：isolated worktree 沒有未納入 git 的 live evidence，verifier 的
`evidence_exists` 因此失敗；本卡沒有為轉綠而複製或修改 forbidden live `artifacts/`。

## Changed-file allowlist

- `app/storage_safety.py`
- `scripts/storage_safety.py`
- `tests/test_storage_safety.py`
- `docs/operations/top10-storage-policy.json`
- `docs/operations/top10-storage-safety.md`
- `docs/tasks/2026-08-03_TOP10-STORAGE-REPRESENTATIVE-CYCLES-02.md`
- `docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/**`

以上全部位於任務卡 allowlist。candidate SHA 由單一 candidate commit 產生後，在正式交付
receipt 回報；commit 無法在自身內容內可靠記錄自己的 SHA。

## Final host evidence

- main checkout 三個 protected SHA-256 與 preflight 完全相同。
- `launchctl print-disabled`：八個 label 全為 disabled；`launchctl list` 無命中。
- process scan：沒有 TOP10 validation workload。
- `lsof +L1`：沒有 TOP10 open-deleted file。
- 八個卡片專屬 validation temp root 均已清除；未清理 production data／artifact／model。
- 收尾 free：`57034854400` bytes（`df available=55698100 KiB`），仍高於 start/runtime 門檻。
- 收尾 swap：used `6190.94 MiB`，metric 可讀；因代表性證據未完成，這不構成 GO。

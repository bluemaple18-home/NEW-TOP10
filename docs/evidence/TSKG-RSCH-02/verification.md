# TSKG-RSCH-02 verification

新增 `research-evidence-tskg-adoption.v1` 封套與純驗證器，並把 compact 摘要附加到 Research Component Ledger 和新產生的 PM research card。

已驗證行為：

- 舊 archive 可 `GRANDFATHERED`，缺新欄位不會被判失效。
- 新研究缺證據為 `NEEDS_EVIDENCE`，不硬阻擋研究進行。
- reuse／promotion／model-input 缺證據為 `BLOCKED`，在使用邊界 fail closed。
- open conflict、竄改 decision、非 repo-relative evidence ref、錯誤 UTC 時間格式會被拒絕。
- verifier 不讀寫 queue／ledger、不執行研究、不呼叫外部服務。
- 既有 builder 只新增 `tskg_adoption` 欄位，原 route、status、verdict 與 runner 控制流不變。

精準測試命令：

```bash
<repo-root>/.venv/bin/python -m pytest -q \
  tests/test_tskg_research_evidence_contract.py \
  tests/test_tskg_research_adoption_inventory.py \
  tests/test_pm_approved_work_queue.py
```

## 整體驗收

- Research-related suite：93 passed、4 subtests passed；另有 1 個既有 ledger evidence existence 失敗。
- Full suite：376 passed、182 subtests passed；同一個既有失敗。
- 該失敗已在本次變更前的固定 commit `0650006` 重現，故不屬於本次 regression。
- `git diff --check` 與 `py_compile` 通過；環境沒有安裝 `ruff`，未執行 lint。

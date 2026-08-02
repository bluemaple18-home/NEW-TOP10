---
id: FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01-status
status: INTEGRATED_OFFLINE
type: task_status
---

# Root question

如何讓default-v2 replay正確終結queue，且任何零進度batch不再重播？

# Current state

- RED-capable artifact diagnostic：exit 1。
- 根因候選已定位於history canonicalization與drain progress invariant。
- Repair 02 candidate `62c31c3` 已經 re-review `GO` 並 fast-forward 至 `main`。
- Runtime：LaunchAgent未載入；容量閘門仍為 `NO-GO`，本卡未啟用。

# Frontier

`READY_FOR_CAPACITY_ACCEPTANCE`

# History

- `SLICE-RED`: target-symptom fixture executed RED (exit `1`); completed default-v2 evidence retained expanded identity and did not close base/default.
- `SLICE-CANONICALIZATION`: minimal identity mapping passed the target test and research-map boundary suite (`7 passed`).
- `SLICE-DRAIN-STOPLOSS` RED: unchanged 144-ID queue plus `appended_run_history_count=0` replayed six batches and returned `OK / max_batches_reached` (exit `1` assertion failure).
- `SLICE-DRAIN-STOPLOSS` GREEN: unchanged identity plus zero append stops after batch `1` as `NO_PROGRESS / no_progress`; forced append is ignored as progress.
- Targeted contract/lifecycle/drain suite: `13 passed`.
- Affected weekend/Fog suite: `38 passed, 6 subtests passed`.
- Full suite: `629 passed, 252 subtests passed, 1 failed`; the isolated worktree lacks the pre-existing artifact/data evidence required by `test_verifier_accepts_generated_ledger`, and the same test fails alone on `evidence_exists`.
- CodeGraph: indexed HEAD matched base; context/query localized the seam to `canonicalize_lifecycle_history()` → `apply_run_history()` → weekend inventory base lookup.
- `REPAIR-02 P1-01` RED：mismatched raw topic/combo 被錯誤 canonicalize 到 target base；
  GREEN：raw identity 不一致時保留原 combo，valid lifecycle default/non-default v2 維持契約。
- `REPAIR-02 P1-02` RED：相同 queue identity 的第二次 invocation 再次執行 batch；
  GREEN：第二次與後續相同 identity 在 replay 前 blocked，identity 改變才恢復。
- Repair targeted：`17 passed, 2 subtests passed`；affected：`38 passed, 6 subtests passed`。
- Repair full：`633 passed, 254 subtests passed, 1 failed`；既有 isolated evidence
  availability failure 已單獨重現。
- Re-review 02：`GO`；原兩個 P1 均關閉。保留非阻塞 P2：損壞／缺 identity 的 prior
  progress 尚缺一致的結構化降級處理。
- Mainline：已離線整合，尚未 deploy、載入排程、live probe 或做容量驗收。

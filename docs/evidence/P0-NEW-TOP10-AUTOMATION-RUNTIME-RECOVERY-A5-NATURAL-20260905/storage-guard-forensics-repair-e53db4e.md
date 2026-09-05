# Storage Guard forensics repair receipt

日期：2026-09-05

Candidate：`e53db4efcef8f69aeeba2c32d6d7faefb04067d6`

狀態：`CANDIDATE_GREEN / PRODUCTION_NOT_ACTIVATED / A5_BLOCKED`

## Root question

修復 Fog 首次自然週期因 `LIVE_SAMPLE_CADENCE_EXCEEDED` 停止後，root-cause receipt 被 persistent retry 覆寫、host probe 無 timeout，以及自然 invocation 缺乏可辨識 metadata 的問題。

## 變更邊界

- 每次非 persistent-denial invocation 產生獨立 archive receipt；`latest` 仍維持相容入口。
- STOPPED marker 綁定 root invocation、archive path 與 SHA-256；marker 先於 receipt 落盤，維持 fail closed。
- persistent denial 不覆寫有效 STOPPED receipt；若 latest 是舊成功，會從 hash-bound archive 恢復 root receipt。
- `/bin/ps` 與兩個 `sysctl` probe 均加上 5 秒 timeout；sample 保存每個 probe 的 duration／availability。
- wrapper 與 CLI 保存 `scheduled_at`、`trigger_type`、`invocation_id`；receipt 明確維持 `accepted_natural_cycles=0`，避免只靠 Storage Guard 成功誤標完整 A5 acceptance。
- Fog health 直接檢查 restart-denied marker；marker 優先於 stale success receipt。
- archive 由既有 allowlisted reclaim 管理：30 日、最多 256 檔／128 MiB、至少保留最新 2 檔。

## RED → GREEN

已建立並跑過下列 red-capable regression；修復前分別因 receipt 被覆寫、`TimeoutExpired` 外洩、CLI 不接受 metadata、stale success 未被 marker 覆蓋，以及 Fog health 誤判成功而失敗。

- `test_persistent_denial_preserves_original_unknown_write_evidence`
- `test_host_metric_subprocesses_are_bounded_and_timeout_as_unavailable`
- `test_storage_guard_cli_accepts_scheduler_invocation_metadata`
- `test_legacy_denial_replaces_unrelated_success_latest`
- `test_restart_denied_marker_overrides_stale_success_receipt`

最終驗證：

```text
145 passed, 38 subtests passed in 16.46s
bash -n scripts/run_with_storage_guard.sh: PASS
jq empty docs/operations/top10-storage-policy.json: PASS
git diff --check: PASS
[DBG-*] residue: none
```

測試範圍：`tests/test_storage_safety.py`、`tests/test_automation_runtime_activation.py`、`tests/test_fog_runtime_health.py`。

## Review status

Review tier：`full / strict`。Mainline correctness／regression／security／performance／test-gap 複查後未發現剩餘 P0/P1；正式 production activation 前仍需對固定新 SHA 執行獨立 Reviewer gate。

## Remaining blocker

- Production runtime 尚是 `ab7c418…`，本 candidate 未安裝、未 reload、未 restart。
- GUI launchd domain 仍為 on-demand-only，Fog 尚未取得新的自然 interval invocation。
- `artifact_run_date`、publish/provider terminal result 尚未由 job-specific acceptance 聚合器核對，因此 A5 必須維持 pending。
- 本輪沒有清 marker、操作 launchd、重啟 GUI session 或修改 production runtime。

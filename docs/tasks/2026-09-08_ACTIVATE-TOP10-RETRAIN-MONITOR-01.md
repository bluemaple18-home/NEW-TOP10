---
id: ACTIVATE-TOP10-RETRAIN-MONITOR-01
status: IMPLEMENTATION_AUTHORIZED / PRODUCTION_ACTIVATION_AUTHORIZED
type: bounded-production-activation
risk: critical
owner: TOP10new operations
date: 2026-09-08
production_change_allowed: true
live_activation_allowed: true
scheduler_change_allowed: true
external_write_allowed: false
push_allowed: false
---

# ACTIVATE-TOP10-RETRAIN-MONITOR-01

👉 [假設與目標確認] 目標：只把 `com.new-top10.retrain` 的每日 02:00 `monitor --trigger scheduled` 接到 accepted detached runtime 並啟用；邊界：不執行 model retraining、不碰 Fog／其他 job、不 push、不外送；驗收：selector fail closed、preflight／rollback／雙盲 review 通過，activation receipt 精確只含此 label，之後等待自然週期證據。

## Root question

既有 activation transaction 是否能在不改變三條核心 job 預設範圍的前提下，安全支援 retrain-monitor-only selector，並以顯式 authority 將原本 disabled／unloaded 的 target 納入可驗證 rollback transaction？

## Blocking edges

1. `ACT-RM-SEL`：activation allowlist 支援 `retrain`，且未指定 selector 時仍只處理原三條核心 job。
2. `ACT-RM-DORMANT`：只有額外顯式 dormant-target authority 才可接納 confirmed disabled／unloaded prestate；transaction 必須保存並可回復 disable override、loaded state 與 plist bytes。
3. `ACT-RM-POLICY`：排程改用獨立 `retrain-monitor` storage identity；`retrain-monitor.launch_verified=true` 只涵蓋已量測 monitor branch，原 `retrain.launch_verified=false` 維持模型重訓 fail closed。
4. `ACT-RM-TEST`：retrain-monitor-only happy path、缺 dormant authority 的零 mutation拒絕、enable/bootstrap failure rollback 與 out-of-scope invariants 有 deterministic tests。
5. `ACT-RM-CAP`：目前 host／project capacity、歷史兩輪 exact monitor evidence、reclaim 與 stop-loss 可重現。
6. `ACT-RM-REVIEW`：兩名互不先讀 verdict 的 Reviewer 均為 GO。
7. `ACT-RM-LIVE`：只在前六項通過後執行一次 activation transaction。

目前 frontier：`ACT-RM-SEL`。

## Allowed files

- `scripts/activate_automation_runtime.py`
- `tests/test_automation_runtime_activation.py`
- 本卡與 `docs/evidence/ACTIVATE-TOP10-RETRAIN-MONITOR-01/`
- `docs/operations/CURRENT_OPERATIONAL_FRONTIER.md`

## Forbidden

- 不修改 retrain／monitor workload、模型、ranking、promotion policy。
- 不 enable 其他 disabled job，不改 daily／external-review-preflight／Fog plist。
- 不 manual run／kickstart；自然驗收只能等 launchd 排程。
- 不清除任何 marker，不刪除 lock／artifact，不 push。

## Acceptance

- activation selector 只接受 allowlist，`retrain` 可被單選。
- legacy no-selector default 仍精確是 daily、external-review-preflight、Fog。
- scheduled plist 的 storage identity 必須是 `retrain-monitor`；原 `retrain` policy 持續拒絕未驗證的模型重訓。
- disabled／unloaded target 缺額外顯式 authority 時必須在任何 mutation 前拒絕；取得 authority後的 rollback 必須回復原 disabled／unloaded state。
- transaction 的 prestate、out-of-scope hashes、rollback 與 terminal receipt 完整。
- installed retrain plist 最終只指向 fixed detached runtime；其他 installed plist byte hash 不變。
- activation 後狀態只能是 `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`；不得在首個自然週期前宣稱 healthy。

Trace preflight：`not-applicable`；本卡是既有 `A6-DISABLED-JOB-INTENT-RECONCILIATION` 的單一 operational activation slice，不新增產品需求或 Jira mutation。

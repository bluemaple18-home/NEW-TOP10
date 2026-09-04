# Reviewer A re-review — candidate eaea74e

- Fixed SHA: `eaea74ef53b50bad2b7bbf0f7153a246636d7cf2`
- Mode: clean-context、archive-only、未讀其他 reviewer evidence。
- Verdict: `NO_GO`

## P1 finding

- `scripts/activate_automation_runtime.py:977`：在 receipt rename 後、parent-directory fsync 故障前排入真實 SIGTERM；failure path 的 mask restore 會在 outer cleanup 與 lock release 前把 pending signal 交給 original handler。若 original handler 為預設 SIGTERM，程序可在回傳 `ACTIVATED_RECEIPT_DURABILITY_UNCONFIRMED_NO_GO` 前終止，留下已切換 topology 與未確認 durability。

## Evidence

- Candidate activation suite：`47 passed`。
- Reviewer 的獨立臨時注入：`1 failed, 8 passed`；失敗案例即上述 cleanup-before-delivery 契約破口。

## Required repair

- Durability 未確認時保持 watched signals blocked，直到唯一 outer teardown 完成 cleanup／lock release；加入真實 `os.kill(SIGINT/SIGTERM)` 與 subprocess/default-handler 驗證。

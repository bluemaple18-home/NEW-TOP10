# Reviewer B re-review — candidate eaea74e

- Fixed SHA: `eaea74ef53b50bad2b7bbf0f7153a246636d7cf2`
- Mode: clean-context、archive-only、未讀其他 reviewer evidence。
- Verdict: `NO_GO`

## P1 findings

1. `scripts/activate_automation_runtime.py:351-354,521-534,679-687`：receipt directory 有 fsync，但三次 plist `os.replace` 後沒有 fsync `LaunchAgents` directory。斷電後可能保留 durable success receipt，排程 plist directory entry 卻回復舊狀態。
2. `scripts/activate_automation_runtime.py:945-948,975-984,1010-1021,1082-1092`：pending SIGINT 加 receipt-parent fsync failure 時，original handler 可在 outer NO-GO branch 前拋 `KeyboardInterrupt`；CLI 沒有輸出 durability-unconfirmed 終態，receipt 可見且 topology 已啟用。

## Evidence

- Isolated candidate archive：`125 passed, 35 subtests passed`。
- 獨立 observer 證實 receipt directory 有 fsync、`LaunchAgents` directory 無 fsync。
- 前輪 partial-arm、pre-syscall mask、rollback second-signal findings 已通過 targeted re-check，但上述 durability P1 仍阻塞。

## Required repair

- plist file 與 `LaunchAgents` directory mutation／rollback 均須 durable；durability-failure path 不得在 cleanup 與可稽核 NO-GO decision 前交回 pending signal。

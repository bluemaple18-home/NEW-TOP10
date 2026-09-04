---
id: MISSION-NEW-TOP10-SIGNAL-SAFE-ACTIVATION-ARCHITECTURE-20260904
chain_id: NEW-TOP10-SIGNAL-SAFE-ACTIVATION-ARCHITECTURE-20260904
supersedes_blocked_chain: NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-20260903
status: CODE_ACCEPTED_NO_PRODUCTION_AUTHORITY
type: architecture-mission
priority: P0
owner: TOP10new operations
owner_authorization: "2026-09-04：那就改吧，我授權，繼續"
repair_2_owner_authorization: "2026-09-04：授權"
repair_3_owner_authorization: "2026-09-04：這版本我認為可以直接轉給 Codex 當 Repair 3 的實作範圍"
thickness: strict
risk: critical
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
push_allowed: false
---

# Signal-safe Activation Architecture Mission

👉 [假設與目標確認] 目標：以 no-throw signal capture、同步 safe-point abort、單次 terminal receipt seal 取代會從 Python signal handler 非同步拋例外的 activation control flow；邊界：只修改既有 activation／Storage Guard seam 與 targeted tests，保留舊 chain 的 NO-GO findings，不清 marker、不切 runtime、不碰 launchd、不 push；驗收：fixed candidate 通過完整 affected tests 與兩個互不先讀 verdict 的獨立安全 review。

## 1. Architecture decision

採用：

1. Python signal handler 不得 raise、不得 append event list、不得執行 receipt I/O；只更新 bounded、idempotent signal state。
2. `_arm()` 必須在任何 production mutation 前完成；handler 安裝期間以 calling-thread signal mask 關閉 SIGINT／SIGTERM 的部分武裝窗口，安裝完成後恢復原 mask。
3. Main transaction 在明確 safe points 同步檢查 abort state，並由正常 Python control flow 進入唯一 rollback path；rollback 期間不再從 signal handler 注入 exception。
4. Receipt 使用一次 authoritative seal；signal evidence 採 bounded snapshot，不使用事件集合收斂的無界 rewrite loop。
5. Seal cutoff 與 post-seal signal ownership 必須寫入 receipt/test contract；B4 依序釋放 staging、locks、handlers 與原 signal mask。不得宣稱 terminal receipt 包含 seal 後才到達的訊號。
6. `pthread_sigmask()` 只用於 handler install/restore 與明確 seal/release boundary，不把「handler 第一行呼叫 mask」視為原子入口保證。

## 2. Allowed scope

- `scripts/activate_automation_runtime.py`
- `tests/test_automation_runtime_activation.py`
- `app/storage_safety.py`（只有既有 denial lock finally regression 需要調整時）
- `tests/test_storage_safety.py`（同上）
- 本 mission 與固定 SHA 的 reviewer evidence。

若需第五個 runtime/code 檔，回報 `CONTRACT_GAP / HOLD`。

## 3. Required RED cases

- SIGINT／SIGTERM 在 `_arm()` 兩個 handler 安裝之間到達。
- 第一個 signal 到達後，另一 signal 在 Python handler 的第一個可重入 seam 到達；handler 不得拋第二個 exception。
- signal 在每個 external mutation 前後到達，下一個 safe point 必須導向 rollback。
- signal 在 rollback 的 plist restore、bootout/bootstrap、marker restore、cleanup、verification 期間到達，exact restore 不得中斷。
- signal 在 receipt payload snapshot、atomic write、seal cutoff 與 release 期間到達；receipt 必須符合明定 cutoff，不得無界重寫。
- terminal receipt write failure 必須保持 NO-GO 並釋放 protection。
- denial receipt failure 後 job lock 可由獨立程序重新取得。

## 4. Acceptance

- Signal handler 的所有路徑皆 no-throw、bounded、無 I/O、無 event-list append。
- Abort exception 只可由同步 safe-point 產生。
- Mutation 前已存在 rollback obligation；signal 到達後不得再 commit activation success。
- Receipt 對每次 invocation 只做一次 authoritative atomic write，無無界 loop。
- exact bytes、loaded topology、marker hashes、staging residue 與 locks 都以外部可觀察狀態驗證。
- `tests/test_automation_runtime_activation.py`、`tests/test_storage_safety.py`、syntax check、`git diff --check` 全部通過。
- Candidate 必須成為固定 commit；兩個 clean-context Reviewer 審同一 SHA，各自把 verdict 寫入 repo evidence，且不能先讀對方結論。

## 5. Hard stops

- 不 merge、push、deploy、clear marker、kill PID 或執行 launchctl mutation。
- 不把本 mission 視為 A4 activation authority。
- 任一 Reviewer 有 P0/P1 即 `NO_GO`；只允許一個 bounded Repair generation。

## 6. Candidate evidence

- 實作範圍：`scripts/activate_automation_runtime.py`、`tests/test_automation_runtime_activation.py`。
- Signal handler 已改為 bounded scalar capture；abort 僅由同步 safe point 觸發。
- Receipt 先完成同目錄 staging 與 signal-mask release，之後才以單次 `os.replace` 成為 authoritative receipt，避免 success receipt 與 rollback topology 分歧。
- RED/GREEN 已涵蓋 final safe point 至 seal cutoff、receipt mask restore failure、cross-signal、signal storm、rollback interruption 與 lock release。
- 第一個 fixed candidate `4aa9b95f6c62c0e1899f6459656b6553bf591577` 經兩位獨立 Reviewer 判定 `NO_GO`；原始 findings 已保存於本 mission evidence 目錄。
- 唯一一次 bounded Repair generation 已補：signal ownership handoff、partial-arm restore obligation、arm-time original mask exact restore、fresh receipt path、parent-directory fsync、rollback second-signal matrix。
- Mainline Repair 驗證：`123 passed, 35 subtests passed`；四個受影響 Python 檔案通過 `py_compile`；`git diff --check` 通過。
- Production／launchd／marker mutation：0。下一步僅建立 repair fixed candidate commit 並重新執行兩次互相獨立的唯讀安全 review。
- Repair fixed candidate `eaea74ef53b50bad2b7bbf0f7153a246636d7cf2` 經第二輪兩位獨立 Reviewer 再次判定 `NO_GO`：durability-failure cleanup 前 pending-signal delivery，以及 `LaunchAgents` directory durability 均仍有 P1。
- 第一個 bounded Repair generation 已用完；目前 `BLOCKED_BY_SECOND_REPAIR_AUTHORIZATION`，不得自行再改 code 或碰 production。
- Owner 已於 2026-09-04 明確授權第二次 Repair；範圍只限第二輪 reviewer 的兩個 durability P1 與 targeted tests，production 邊界不變。
- 第二次 Repair 已補：staging plist file fsync、每次 activation／rollback plist replace 的 `LaunchAgents` parent-directory fsync、durability-failure cleanup 後 bounded pending-signal drain，以及 success seal 前 bounded handler handoff。
- Mainline 驗證：`129 passed, 35 subtests passed`；四個受影響 Python 檔案通過 `py_compile`；`git diff --check` 與 debug-marker 檢查通過。
- 下一步只建立 Repair 2 fixed candidate，交由兩位全新 clean-context Reviewer 審查；production／launchd／marker mutation 仍為 0。
- Repair 2 fixed candidate `696c15d7436f8f8af3be918bd652394c4279351c` 經第三輪兩位 Reviewer 一致 `NO_GO`；剩餘單一 P1 為 signal teardown 結果未參與 terminal return／receipt truth。
- 第二次 Repair 已用完；目前 `BLOCKED_BY_THIRD_REPAIR_AUTHORIZATION`，production 邊界不變。
- Owner 已明確授權收斂後的 Repair 3：只修 teardown-before-terminal-status 排序、receipt teardown attestation 與對應 RED；不動其他已通過部分。
- Repair 3 已移除 `run()` try／except 內 early return，保留 `ReceiptDurabilityError` 與 rollback 互斥，並讓 `_disarm() -> bool` 以 original handlers／mask readback post-condition 決定唯一 terminal status。
- Receipt 已固定標示 teardown 需由 process exit status 驗證；teardown 未確認時統一回 `SIGNAL_TEARDOWN_UNCONFIRMED_NO_GO`，不混入 topology 組合狀態。
- Mainline 驗證：`133 passed, 35 subtests passed`；`py_compile`、`git diff --check` 與 debug-marker 檢查通過。production／launchd／marker mutation 仍為 0。
- Repair 3 fixed candidate `3023ed022b72738c49afca5a3311044a19eb0b72` 第四輪 review 分歧：Reviewer A `GO`；Reviewer B `NO_GO`，指出 lock cleanup exception 可跳過 `_disarm()`。
- Mainline 已用真實 `LOCK_UN` failure injection 重現 P1，並在原授權 teardown boundary 內收斂：逐 lock 釋放、B4 各步獨立 exception boundary、signal teardown 必跑、CLI unexpected exception exit 75。
- 收斂後 Mainline 驗證：`134 passed, 35 subtests passed`；`py_compile`、`git diff --check` 與 debug-marker 檢查通過。下一步只建立新 fixed candidate 並做兩次全新獨立 review。
- Final fixed candidate `70ff1e9dda855e1030a8bb169e77931d49f629a8` 已由兩位全新 clean-context Reviewer 獨立審查：Reviewer A `GO`；Reviewer B 初判的 dependency success no-op P1 經 production fault-contract 裁決後由 Reviewer 明確撤回，final `GO`。
- 本 mission 已完成 code／test／雙 review acceptance；不包含 A4 activation、launchd、marker、push 或任何 production mutation authority。

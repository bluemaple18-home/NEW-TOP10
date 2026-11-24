# RECOVER-TOP10-AUTOMATION-BBD32B4-01

## 目標

以 `bbd32b4f017498b413a32a1171aec76f426441a3` 為原驗證基線；identity repair 的 `1f3aa307b3a2e61f2220e6cc48809b7151ba0b77` 已整合至本機 main，使用既有 canonical linked worktree 完成 production activation 前核對。

## 範圍

- 候選 runtime 總量上限：6 GiB。
- 兩輪完整 Daily 隔離週期與資源／程序群組證據。
- 受控安全停止、restart-denied marker recovery 與精確 rollback 驗收。
- 真實 Google Chrome 的 Gemini probe-only；不得填入或送出 review packet。
- 原 preactivation 階段保留 production 原狀；2026-09-30 Owner 已明確核准核對通過後正式修復，僅准入 Daily／provider preflight 切換。舊 denial marker 保留。

## 禁止事項

- 未獲授權前不切換 launchd；2026-09-30 核准的兩個 job 切換已完成，不延伸至其他 job。
- 不清除 production marker。
- 不執行 production Daily。
- 不送出任何外部 review packet。
- 不 push、merge；deployment 僅限 2026-09-30 已核准的兩個 job／exact candidate。

## 驗收結果

1. **PASS**：runtime 為同 repo、detached HEAD、exact accepted commit，tracked tree clean；實際約 1.98 GB，低於 6 GiB。
2. **PASS**：Foundation important-usage 扣除 6 GiB 後為 28,995,299,209 bytes，高於 24,510,719,590 bytes reserve；Daily guard fresh measure PASS。
3. **PASS**：兩輪 Daily 隔離週期成功，外送關閉，final process group quiescent，沒有 unknown write。
4. **PASS**：fresh fixture 的安全停止留下 hash-bound marker；後續 invocation 在 child 前 exit 75；latest 可由 marker 精確還原；rollback tests 5/5 PASS。
5. **EXACT CANDIDATE GUI PROBE PASS**：修補已成為本機 commit `1f3aa307b3a2e61f2220e6cc48809b7151ba0b77`。2026-09-30 11:41 +08:00 改用 Codex 本機 host exec（受審核的 `require_escalated` 通道），同一候選腳本 exit 0、`ok=true`、`phase=execute`、`readiness=input_ready`、`hasComposer=true`。未改程式、未帶 packet、未輸入或送件；tracked tree 維持 clean。Native2 兩次失敗保留為歷史證據，不再視為當前 GUI blocker。
6. **ACTIVATION READBACK PASS**：2026-09-30 14:42 的 production plist／launchctl 已指向 canonical `1f3aa30` runtime；兩個 job loaded／enabled，schedule 不變。舊 production marker SHA-256 與 precheck 一致，新 runtime marker absent；其他服務 plist 全數未變。

## 裁決

`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`

Identity parser 修補、canonical candidate 與 GUI probe 已通過。Owner 清理容量後明確授權正式修復；14:41 +08:00 重測原 6 GiB 預算仍有約 3.34 GB margin，launchd 通道實測載入／卸載及清理通過，遂以既有 transaction 完成兩個 job 的正式切換。切換 exit 0，獨立回讀 PASS。probe 的 `hasSendButton=false` 不代表外送已驗收；自然 Daily 與 provider preflight 仍待原排程執行。

## 證據

- [收斂報告](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/report.md)
- [Evidence manifest](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/manifest.json)
- [Host 通道 exact-candidate probe 與 production 前後核對](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/gemini-host-channel-probe-20260930.json)
- [正式 activation receipt](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/activation-1f3aa30.json)
- [本次重核、真實 launchd 通道與切換後獨立回讀](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/activation-precheck-20260930.json)
- Candidate 原始 Daily receipts 與歷史失敗 logs 保留於固定 runtime，未刪除或改寫。

## 狀態

`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`

### 2026-09-30 17:43 自然驗收續作

2026-10-01 Owner 要求開卡：已將 Fog 待決範圍具體化為[小型隔離驗證入口卡](2026-10-01_TOP10-FOG-BOUNDED-VALIDATION-INPUT-OUTPUT-01.md)，狀態 `SCOPE_APPROVAL_PENDING`。僅新增控制文件，不開始實作、不重置 Repair 2 成本／次數。每10分鐘 heartbeat 已依 Owner 要求刪除；正式17:30／17:40排程不變，自然驗收仍待第二輪。

19:13 範圍裁決：既有 Fog 小型隔離重現路線 `NOT_READY`，唯讀核對已收斂，停止重複查相同歷史及重派可行性研究。現有入口至少複製3.07GB／42,054檔，要求sandbox內完整Python；目前共用暫存policy為256MiB，現況6GiB預留亦不過容量線。Daily source/output分離不能直接套到Fog固定cwd及下游寫入。待Owner決定是否擴至「既有Fog代表性驗證入口的輸入／輸出分離」：唯讀共用source/interpreter、hash-bound必要資料、唯一受管output；不改production預設、不加服務、不提高globalpolicy、不回Apple路線。验收必須有來源防寫反例、<=256MiB實測、代表性topic與正常／失敗停止證據；超限即交回，不自行擴張。這是超出原本兩檔診斷修補的範圍決策，不重問Repair2成本。Fog保持封鎖；Daily／provider今日成功與送出回執不變，下一自然週期待驗。

18:33 診斷前置完成：Worker `01a0f1d7-d857-7732-85c8-64e58e3661bc` 已交付兩檔最小差異。回報 host RED（缺 `internal_error`）→ GREEN，全回歸102 passed／41 subtests；Mainline 獨立抽驗4 passed／4 subtests，diff check通過。只在內部例外receipt加入型別、整數errno與最多4個guard相對frame；不輸出message／locals／外部路徑，原停止與hash-bound marker邏輯不變。裁決為 `LOCAL_DIAGNOSTIC_PATCH_REVIEWED`，不是Fog根因修復或部署通過。未commit／push／部署。下一步限定查9/15可得主機中斷／I/O證據，禁止反覆改採樣時間猜修。今日Daily／provider receipt及平台回執hash未變；launchd加info/debug重查仍不足以補齊自然來源。

18:23 有界診斷修補契約：Fog 歷史 PermissionError 缺失敗位置，現況無法重現；先修既有 guard 的證據缺口，不宣稱修復原始 cadence 事故。範圍只限 `app/storage_safety.py` 與對應測試，於內部例外 receipt 留下有界 exception type／errno／程式位置，不記任意 exception message、locals、環境值或憑證。不可改 schema version、既有原因碼、停止／清理／marker／自然驗收邏輯或門檻；不得操作 production。驗收：離線 PermissionError 反例證實新 receipt 可定位失敗位置且保持 STOPPED／restart denied，敏感 message 不外洩，既有安全回歸通過。此為原根因排查的診斷前置，不新增或重置 recovery 修復輪次。Mainline 只寫控制文件；單一 native Worker 寫上述兩檔。

18:13 續查：Daily／provider 仍 runs=1、exit=0。17:29:50–17:40:20 的 launchd unified log 只保留 provider inactive，無足夠 calendar launch 事件；自然來源仍 pending，不能以零事件推定人工啟動。Fog exact 67f2d28 的唯讀 meter 基準（20秒上限）成功：13,281 files／1,567,928,938 bytes／0.5985秒，未重現 PermissionError。其 guard 與 1f3aa30 無 diff，已有去重與70%提前採樣，不能重做舊修補。9/14兩輪驗證在外接volume，不能排除9/15內碟及並行負載下的尖峰。下一步沿既有receipt／exception seam定位可達路徑；若歷史資料不足，先補最小離線診斷證據，不猜改policy、不跑production。

18:03–18:07 更新：Daily 18:00:47 完成，launchd exit 0、guard OK／child exit 0／final process group quiescent；當日 automation status OK，Clawd 報牌與營運摘要均有非 dry-run 的平台 message ID 回執。第一輪產物／送出／停止子鏈通過；独立自然來源與第二輪仍待驗，整體狀態不變。peak RSS 約 1.93 GB，project 增量 55.25 MB，unknown writes 空；host swap 增量約 2.54 GB，現有 guard 在 pressure sensor 可用時不以單獨 swap delta 判停，不能歸因全為 Daily 使用。overlay 缺歷史檔導致 shadow FAILED，LLM 改寫 FALLBACK，已保留降級證據，未冒稱所有子功能正常。

Fog P0 已開始定位：9/15 最後 meter_paths 約 98.33 秒、整筆 sample 約 99.29 秒，前後 sample 間隔約 135.09 秒；persistent denial 說明後续 exit 75，並非每輪都重新執行研究。PermissionError 只有類型，尚不足指認失敗 syscall／path；不能把「放寬60秒」或「清 marker」當修復。舊卡保留 Fog 原線 ownership，下一步先核對交接及 exact source，避免重複修復。以上續查皆未改 production。

- Owner 已授權先驗收，再由 Mainline 選擇 P0 推進；當前 P0 為既有 Daily／provider 自然全鏈驗收，不新增修復輪次。
- Daily：launchd `runs=1`、`state=running`、`immediate reason=xpc event`；17:30 啟動，17:43 仍在 FetchStage（132/301）。尚無當日報牌／送出終端結果。`daily_latest.json` 仍為 9/29 隔離驗證，不得當成本日證據。
- Provider：17:40 執行完成，launchd exit 0；ChatGPT／Gemini 均 PASS、probe-only、未送 review packet；guard exit 0、程序群組已停止、無 denial。此為當日子鏈通過，獨立自然來源與第二輪仍待驗，不把 `trigger_type=natural` 單獨視為證明。
- Foundation 可用量約 36.41 GB；實體可用約 32.21 GB。當下容量讀值不取代 Daily 全程資源終端驗收。
- 後續 P0 候選：Fog 最新 launchd exit 75；其 guard latest 留在 9/15 STOPPED，原因為 `LIVE_SAMPLE_CADENCE_EXCEEDED`／`GUARD_INTERNAL_ERROR_PermissionError`。Daily 第一輪收斂後先確認 Fog 現況與根因，保留 fail-closed，不直接清 marker 或重啟。
- 已建立本對話 heartbeat `top10-p0`，每 10 分鐘續查；無狀態變化時安靜。完整驗收需兩個連續自然週期，不能以人工重跑湊數。
- 證據：[本次精簡驗收快照](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/natural-acceptance-20260930.json)。未變更 production，未 commit／push。

以下為 14:42 切換回讀及更早紀錄。

最新：2026-09-30 14:41:40 +08:00 已完成 Daily／provider preflight → canonical runtime `/Users/mattkuo/TOP10-runtime-automation-bbd32b4`、HEAD `1f3aa307b3a2e61f2220e6cc48809b7151ba0b77`。14:42:58 回讀兩者 loaded、enabled、not running、runs=0；保留平日 17:30／每日 17:40 排程，未 kickstart、未人工 Daily。舊 production marker SHA-256 未變，新 runtime marker absent，非目標 plist 全數未變，回退快照已保存。等待自然來源、當日 artifacts／送出 receipt 與資源終端證據，不用切換成功冒稱完整恢復。以下為本次切換前的歷史核對。

2026-09-30 續作：本機 main 精確為 `1f3aa30`；canonical candidate 沿用 `/Users/mattkuo/TOP10-runtime-automation-bbd32b4`，HEAD 已更新至相同 SHA 並通過同 repo／detached／clean 驗證。新候選 20 tests／11 subtests 及 GUI probe PASS，既有 Daily／rollback 程式與原驗收基線相同。正式 Daily 與 provider preflight 的切換、失敗回退與自然驗收方案已寫入原報告，未執行 activation。

11:58 的歷史 Foundation 量測在原 6 GiB 預留後曾不足 **168,243,200 B**，當時保持 `NO_GO`。Owner 其後完成容量清理並核准修復；14:41 重測與正式切換結果以上方最新狀態為準。該次不足的原始證據保留，不再當作當前待辦。


### 2026-10-07 Rule25 適用性裁決

- 正式 recovery 線已由 `TOP10-FOG-FORMAL-RECOVERY-CANARY-20261007` 更名為 `TOP10-FOG-FORMAL-RECOVERY-ACTIVATION-20261007`。實際操作是以既有 `scripts/activate_automation_runtime.py` 原子 transaction 替換單一既有 Fog LaunchAgent runtime，不建立、派送或推進 canary。
- Rule25 只適用於 production canary 建立／派送／推進，並要求 `create → run → select → publish → transaction → tag → push` 完整 capability receipt。本線沒有這七步產品能力，因此裁決為 `NOT_APPLICABLE`；不執行 gate，也不建立假 receipt。
- `scripts/push_changes.sh` 含 `git add -A`、commit、pull --rebase、push main，禁止用來製造 Rule25 證據。
- 這項裁決只移除錯套的 Rule25 blocker。Rule24 exact-candidate PASS、clean frozen candidate、activation failure-state review、兩名 blind Reviewer `GO/GO` 與正式 production 授權仍是必要條件；本次未清 denial、未改 launchd、未啟 Fog。
- evidence：[Rule25 applicability decision](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-rule25-applicability-decision-20261007.json)、[更新後 formal preflight](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-formal-recovery-host-preflight-20261007.json)。


### 2026-10-07 Formal Fog frozen candidate checkpoint

- exact candidate：`983010803b0a78955117c0579005777eb923cfd2`（tree `3fa46198daacd4ce9b3f6c700cbe700e3fa00f94`），base `25348435c5049c5d2ac486fe504c8c0abd4d19fd`；detached、clean、29 files，source/candidate SHA mismatch `0`。
- portable bundle：`fog-formal-recovery-candidate-98301080.bundle`，SHA-256 `cfe6b3973adb365b9594bc0a43f6854c02d2a6b1453e4498d20abdc1995d754a`；fixture SHA-256 `44d21ca8ab606c6dc8d1f2ec5da8fa6473fce4604b2109cbf564d889b62ed0ac`。
- host-native affected suite：`277 passed, 66 subtests passed in 32.48s`；activation failure-state suite：`95 passed in 1.11s`。
- exact candidate Rule24：`PASS`；Foundation admission `43,234,811,968 B`，10% floor `24,510,719,590 B`，margin `18,724,092,378 B`，memory pressure `1`。容量具波動性，activation 前仍須 fresh remeasure。
- 狀態：`CANDIDATE_HOST_ACCEPTED_BLIND_REVIEW_PENDING`。兩名 blind Reviewer 已以 clean context 並行審查；未清 denial、未改 launchd、未啟動 Fog、未執行 activation。
- evidence：[candidate acceptance](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-formal-recovery-candidate-acceptance-20261007.json)、[activation review packet](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-formal-recovery-activation-review-packet-20261007.json)、[formal preflight](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-formal-recovery-host-preflight-20261007.json)。


### 2026-10-07 Current launchd prestate drift

- 最新 host-native `launchctl print gui/501/com.new-top10.fog-research-worker` 回 `SERVICE_NOT_FOUND`（exit `113`）；installed plist 仍存在，SHA-256 `b6d5646469aa09d89b8d0cc8d108878981bcd5c3cecc29894bf185120af62227`，仍指向 `/Users/mattkuo/TOP10-runtime-automation-67f2d28`；disabled map 為 `enabled`。
- 目前實際狀態是 `enabled + unloaded`。現行 `activate_automation_runtime.py` 對 non-dormant target 要求 prestate `loaded`，因此會在任何 bootout／replace／bootstrap mutation 前 fail closed。
- 新 blocker：`FOG_LAUNCHD_PRESTATE_UNLOADED`。未執行 bootstrap、kickstart、denial clear 或其他 launchd mutation。candidate correctness 與 current activation readiness 分開判定。


### 2026-10-07 Unexpected launchd topology drift incident

- 直接證據已把 Fog 的卸載窗口縮至 2026-10-07 15:41:58–15:43:26 +08:00：前者仍可 launchctl print，後者已 SERVICE_NOT_FOUND。
- 目前四個核心 job：daily、external-review-preflight、fog-research-worker、retrain 全為 enabled + unloaded；launchctl print exit 113。Fog restart-denied marker 仍存在，SHA-256 9cc55c5dfdb7e6fe1a85f1ad017f68adc5df0599028323c69ce52fea5c59ce3f。
- Blind Reviewer A 在該窗口只有 read-only git/rg/sed/nl；Reviewer B 的 activation pytest 於 15:43:59 才開始，晚於 first-known unloaded。PID 12066/12065 未對應到 Codex 頂層 CommandExecution，unified log PID lookup 也未取得可歸因證據。
- 事件分類：CONFIRMED_UNEXPECTED_PRODUCTION_SIDE_EFFECT_SOURCE_UNRESOLVED。不得把來源歸給 reviewer、setup_launchd 或其他單一命令，除非後續有新證據。
- recovery prestate 以四 job enabled + unloaded 為準。現有 activation transaction 對 non-dormant target 預期 loaded prestate，故 current readiness 為 BLOCKED_TOPOLOGY_DRIFT；重新設計／驗證前不得自動 bootstrap、kickstart、clear denial 或執行 production activation。
- evidence：../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/launchd-topology-drift-incident-20261007.json。


### 2026-10-12 enabled+unloaded prestate repair

- 已在既有 activation transaction 加入顯式 enabled+unloaded prestate 模式；只接受明確 --job + 額外 opt-in，且 launchctl print 必須明確 SERVICE_NOT_FOUND、print-disabled 必須證明 enabled。預設 legacy 行為不變，dormant retrain 路徑不變。
- success path 對此 prestate 不做 bootout，只做 plist replace + bootstrap；bootstrap/後續 failure rollback 會恢復 old plist 並驗證回原 enabled+unloaded。disabled、未知 disabled state、transient launchctl error 都 fail closed。
- 驗證：focused 30 passed；完整 activation suite 101 passed；git diff --check PASS。未改 launchd、未啟服務、未清 denial、未執行 production activation。
- 狀態：LOCAL_REPAIR_VERIFIED_NOT_ACTIVATED。下一步是凍結 exact repaired candidate、host-native regression + fresh Rule24、再做兩名 blind review。
- evidence：../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/enabled-unloaded-prestate-repair-20261012.json。


### 2026-10-12 enabled+unloaded final GO/GO checkpoint

- exact candidate：ec08e846db21a1601fa5e3995138e46015eaceb7，tree 36aa408921635c12e15e89dfc324b2422c224ff8；working tree clean。
- enabled+unloaded rollback 缺口已補：replace failure、post-bootstrap verify failure 都實際走 transaction.run() → rollback → rollback verification，驗證 old plist、loaded=false、disabled=false。
- activation suite 103 passed；兩名 clean blind reviewer 對 exact candidate re-review 均 GO。
- Rule24 仍 BLOCKED：Foundation important-usage 對 exact candidate、source repo、/private/tmp 均回 total=245107195904、physical=35202785280、admission=0。依契約不得以 raw free fallback。
- frontier：ACTIVATION_CONTRACT_GO_GO / FROZEN_ACCEPTED_FOR_HOST_GATE / PRODUCTION_BLOCKED_RULE24。未改 launchd、未清 denial、未啟服務。
- evidence：../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-formal-recovery-enabled-unloaded-final-review-20261012.json。


### 2026-10-12 post-reboot Rule24 executor limitation

- 重開機後 exact candidate ec08e84 已由 verified bundle 重建，HEAD/tree/clean identity 重新確認。
- raw/physical available 由約 35GB 上升至約 73GB，但 Foundation important/opportunistic 仍回 0；Rule24 仍 fail closed。
- 同一執行通道的 diskutil 無法使用 DiskManagement framework，且目前工具 registry 沒有可用 host-native/elevated exec，因此此 0 不再當作可信 host admission 真值。
- 狀態：EXECUTOR_HOST_FRAMEWORK_LIMITATION_UNRESOLVED / PRODUCTION_BLOCKED。不得 raw fallback；下一步須由能存取 macOS Foundation/DiskManagement 的 host-native execution path 對 exact candidate fresh remeasure。
- evidence：../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/rule24-post-reboot-executor-limitation-20261012.json。


### 2026-10-12 exact candidate Rule24 host-native PASS

- exact candidate `ec08e846db21a1601fa5e3995138e46015eaceb7` host-native Rule24：`PASS`；Foundation admission `72,849,588,288 B`，raw free `72,007,708,672 B`，memory pressure `2`，decision reasons 空。
- 既有 activation suite `103/103 PASS`、blind review `GO/GO`、enabled+unloaded rollback boundary 已關閉。
- 狀態：`ALL_RECOVERY_GATES_CLOSED / PRODUCTION_ACTIVATION_READY_FOR_OWNER_AUTHORIZATION`。尚未執行 activation、未改 launchd、未清 denial、未啟服務。
- evidence：../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/rule24-host-native-pass-ec08e84-20261012.json。

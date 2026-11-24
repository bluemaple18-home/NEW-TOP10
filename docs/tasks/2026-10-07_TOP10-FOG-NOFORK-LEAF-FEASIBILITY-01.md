# TOP10-FOG-NOFORK-LEAF-FEASIBILITY-01

- 工作名稱：固定 Fog 代表性驗證 no-fork 葉節點可行性。
- slice_id：`FOG-NF-001`。
- traces_to：`TOP10-FOG-BOUNDED-VALIDATION-INPUT-OUTPUT-01` 的 FOG-TOPO-003／004、擬核准範圍 3–4、驗收與交付 3–4。
- 狀態：`CANDIDATE_GREEN / NATIVE_TWO_CYCLE_PASS / TWO_BLIND_REVIEWS_GO / FORMAL_FOG_RESTART_BLOCKED`。
- frontier：AI Core `finite2_nonfork_prototype_only` 已交付；FOG-NF-001-A～E 已在固定候選、exact recovery、兩個 native 週期與兩名獨立唯讀 Reviewer 範圍內關閉。正式 Fog restart／canary 仍是另一個 strict scope，未獲本卡授權。

## 目標

只為固定 `2026-08-31 / NARROW_LEADER / BIG_BULL+HIGH_CHOPPY / 12-1-1-8` 代表性驗證建立兩個候選葉節點：

1. 準備 fixture、釘定來源身分並發布 Batch Intent。
2. 執行 baseline、candidate、compare 與 batch verify，全部沿既有 Python callable 在同一程序完成。

此切片只回答「既有 finite2 no-fork 介面是否有合法 TOP10 葉節點可接」；不解除 Fog、Daily 或 production 封鎖。

## Blocking edges

- `FOG-NF-001-A`：Batch owner 必須接受由 trusted validation caller 傳入且與環境釘定值一致的 project head；未提供時維持原 Git authority。
- `FOG-NF-001-B`：research runner 必須可注入固定 step runner；預設仍使用 subprocess。
- `FOG-NF-001-C`：matrix／compare CLI 必須與 callable 共用同一 argv parser，不借用父程序 `sys.argv`。
- `FOG-NF-001-D`：兩個候選葉節點須在任何 Git／matrix／compare subprocess 被呼叫時測試失敗。
- `FOG-NF-001-E`：產品接線前需由 AI Core 原 no-fork observer 對凍結候選給出實際 PASS 或保守 BLOCKED。

目前 frontier：A、B、C、D `GREEN`；E 已完成 exact bounded recovery、兩個 native 代表性週期及兩名 blind Reviewer R2 `GO`，狀態為 `PASS_WITH_BOUNDED_SCOPE`。此 PASS 只回答固定兩葉的 no-fork stop proof 與 evidence lifecycle，不授權正式 Fog restart。

## 範圍與 likely files

- `app/research/batch_owner.py`
- `scripts/publish_research_batch_intent.py`
- `scripts/run_autonomous_research.py`
- `scripts/run_backtest_strategy_matrix.py`
- `scripts/compare_strategy_matrices.py`
- `scripts/run_fog_representative_validation.py`
- 一個 validation-only 候選 CLI 與定向測試

Mainline 直接實作理由：候選依賴目前同一工作樹尚未提交的 FOG-TOPO-004 差異；clean Worker 看不到該基線，`fork_context=true` 又未取得額外成本核准。維持單一 writer，後續用 clean read-only Reviewer 驗證。

## 約束

- 不新增通用 controller、runtime、registry、FSM、DB、daemon 或清理 authority。
- 不改 AI Core lifecycle、TOP10 guard、policy、容量門檻、研究參數與正式入口預設。
- 不清 `restart_denied`、不啟 Fog／Daily、不送外部 review packet、不 commit／push／deploy。
- supplied project head 僅在 `TOP10_STORAGE_VALIDATION_MODE=1` 且等於 `TOP10_VALIDATION_SOURCE_COMMIT` 時可用；其他情況沿原 Git 查核或 fail closed。
- no-fork step runner 只允許既有 matrix 與 compare 兩個固定 script；任意 command 一律拒絕。
- 任何實際 fork、observer unknown、容量不足或輸入身分不符皆維持 `LIVE_BLOCKED`。

## TDD 與驗收

1. RED：封鎖 `subprocess.run`，證明現況 publish／research 執行會失敗。
2. GREEN：supplied project head 不呼叫 Git；baseline／candidate／compare 使用固定 callable，保留原 step receipt、失敗後 skip 與輸出格式。
3. 回歸：預設 CLI／subprocess 路徑不變；既有 FOG-TOPO-004、batch owner、matrix／compare 相關測試通過。
4. bounded native：用現有 AI Core `require_complete_stop_proof` 對兩個候選 argv 執行；記錄 child identity、fork observer、退出碼、root／marker／evidence 結果。測試資料與輸出必須位於受管 root，來源 hash 前後一致。
5. `git diff --check` 通過，保存精簡 receipt；明確區分 candidate feasibility、入口接線與正式 Fog readiness。

## Trace preflight

- slice ID 唯一；traces_to 的原卡與節點存在。
- blocking edges、驗證方式、likely files 已明列。
- Jira／US／FR schema：`not-applicable`，沿既有本機恢復卡，不建立第二套 backlog。
- 替換／退場：無預設路徑取代；只新增 opt-in validation candidate，原 subprocess 路徑保持相容。

## 2026-10-07 實機准入結果

- 候選驗證：`git diff --check` 通過；固定葉節點、同程序 representative、batch owner 與 receipt 相關定向測試 `69 passed`。這只證明候選控制流與相容路徑，不等於 native no-fork proof。
- 凍結身分：TOP10 `HEAD=25348435c5049c5d2ac486fe504c8c0abd4d19fd`；候選、必要 config／fixture、AI Core lifecycle／capacity sensor 與 runner 已保存 SHA-256 freeze。
- 外接卷身分：`/Volumes/VibeCode` 由 `mount + ioreg + open-fd` 共同核對為 `/dev/disk5s1`、device `16777240`、inode `2`、UUID `27BEBF8F-6320-4E2F-965B-FF4517016A1F`。原 `diskutil` 在目前 runtime 無法使用 DiskManagement；替代查核未降低 UUID 門檻。
- 容量 gate：原 AI Core `assert_projected_capacity` 以 Foundation important-usage 量測時，外接卷回 `total=230000001024`、`physical_available=93526007808`、`admission_available=0`；內建亦回 `admission_available=0`。依共用 sensor 契約，零值屬 unknown，必須 `NO_GO`，不得降級 raw free。
- 停止邊界：兩次 preflight 都在 `create_root`、isolation marker 與 leaf spawn 前停止；沒有 managed root、沒有 prepare／execute child、沒有 no-fork proof，也沒有 evidence export。正式 Fog／Daily／restart denial 全未變更。
- 裁決：兩個葉節點候選可供後續實機重跑，但 `FOG-NF-001-E` 未通過。只有 authoritative Foundation admission 恢復為正值後，才能用已保存的 exact runner 執行兩個代表性週期；不得修改門檻或以 raw 容量冒充准入。
- evidence：[實機准入阻擋 receipt](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-nofork-native-preflight-20261007.json)、[凍結版本](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-nofork-native-freeze-20261007.json)、[可重跑 runner](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-nofork-native-runner-20261007.py)。

## 2026-10-07 最終實機驗收與雙盲複核

- 根因收斂：先前 `admission_available_bytes=0` 只出現在受限 sandbox；未修改的 Foundation sensor 在主機原生環境回傳正值。Rule24、sensor 與容量門檻均未放寬。
- Exact recovery：cycle-1 舊 root／marker 已完成 `recovered-quarantined`；active root／marker 消失，quarantine 永久保留，30 檔、429,731 bytes evidence 已跨卷發布並重算 manifest。repo lock 正常釋放。
- Frozen dependency：共享 AI Core main 已漂移，因此以 preserved finite2 commit `8d72381386cf3903ec59a668b02294145dde7383` 的精確 bytes 建立 evidence-local dependency bundle；bound runner 只重綁 `AI_CORE` 路徑，未更改 runner 邏輯。
- Native cycle 1：`PASS`；prepare／execute 均 exit 0，兩個 native no-fork proof，13 項 pass condition 全 true；RSS sampled peak 322,011,136 bytes，swap sampled growth peak 46,326,088 bytes。
- Native cycle 2：`PASS`；prepare／execute 均 exit 0，兩個 native no-fork proof，13 項 pass condition 全 true；RSS sampled peak 290,291,712 bytes，swap sampled growth peak 0。
- 第一輪 blind review：Reviewer A 為 `GO` 並提出 recovery 測試漂移 P2；Reviewer B 為 `NO_GO`，提出 protected-state 前後基準 P1 與同一測試漂移 P2。
- 修復：新增 protected-state bridge，綁定 2026-10-05 既有 before／after receipt、三份 operation receipts 與主機 post observation；六個舊 delete／clear API 測試改為現行 quarantine 契約。production recovery 程式未因本修復修改。
- 測試：`tests/test_fog_nofork_native_recovery.py` 為 `10 passed`；舊 `delete_exact_frozen_tree`／`clear_exact_marker` 引用為 0；`git diff --check` 通過。
- R2 blind re-review：Reviewer A 與 Reviewer B 均為 `GO`，未解 P0／P1／P2 皆為 0；兩者各自重算 SHA、protected-state 鏈與 freeze，並獨立重跑 10 項測試。兩者均未讀取對方 verdict。
- Acceptance mapping：FOG-NF-001-A～E 全部 `PASS`，其中 E 僅代表固定兩葉、兩週期的 native no-fork feasibility 與 evidence lifecycle 驗收。
- 保護邊界：Daily plist、Fog restart denial、Daily restart denial 維持既有 SHA；未啟 Fog／Daily、未清 denial、未 commit／push／merge／deploy。
- 最終裁決：`FOG-NF-001-E = ACCEPTED`；`formal_fog_restart_allowed=false`；`production_promotion_allowed=false`。正式 Fog recovery／canary 必須另走 Rule24／Rule25 strict 驗收。
- evidence：[R2 review packet](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-nofork-native-final-review-packet-r2-20261007.json)、[protected-state bridge](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-nofork-native-protected-state-bridge-20261007.json)、[review repair](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-nofork-native-review-repair-20261007.json)、[cycle 1 receipt](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-nofork-native-cycle-1-rerun-20261007.json)、[cycle 2 receipt](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-nofork-native-cycle-2-rerun-20261007.json)、[最終 acceptance receipt](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-nofork-native-final-acceptance-20261007.json)。

## 回退

只撤本卡新增的 candidate、keyword parameters、argv callable 接點、測試與 evidence；不得 reset 工作樹或覆蓋 10 月 4–5 日既有修補。

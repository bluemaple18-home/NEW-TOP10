# RECOVER-TOP10-AUTOMATION-BBD32B4-20260929

## 裁決

- **最新裁決（2026-09-30 14:42 +08:00）：`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`**。
- **Daily／provider preflight 正式切換成功；獨立回讀 PASS，自然全鏈路驗收 PENDING**。Owner 已授權；容量缺口與 launchd 通道在 mutation 前重新量測／實測通過。文末為本次切換證據；先前 NO-GO 保留為歷史，不代表當前 activation 狀態。
- Daily 兩輪隔離執行、安全停止、restart denial、marker recovery、rollback、容量與 production 不變性均已通過。
- 真實 Chrome 的精確 profile／tab／composer readiness 與「未送件」已通過。
- Identity parser 修補 `1f3aa307b3a2e61f2220e6cc48809b7151ba0b77` 已整合至本機 main；canonical linked candidate 的定向測試與真實 GUI probe 均 PASS。原 Native2 GUI blocker 已解除；本次尚未完成的項目是切換後自然週期與正式外送的驗收。

## 原始固定候選（切換前歷史）

- Runtime：`/Users/mattkuo/TOP10-runtime-automation-bbd32b4`
- Commit：`bbd32b4f017498b413a32a1171aec76f426441a3`
- 狀態：detached HEAD、tracked tree clean。
- 實際大小：`1,980,448,768` bytes，低於 6 GiB 上限。

## Identity repair 隔離候選（11:35 歷史）

- 當時 canonical checkout 的 `.git/index.lock` 因 Native2 權限回傳 `Operation not permitted`，因此先在隔離 clone 提交；後續已透過本機 host 通道將同一 `1f3aa30` 整合回主線，詳見本機整合段落。
- 隔離本機 clone：`/private/tmp/TOP10new-gemini-repair-20260930`。
- 本機 commit：`1f3aa307b3a2e61f2220e6cc48809b7151ba0b77`（未 push）。
- Exact commit bundle：`local-repair-1f3aa30.bundle`，SHA-256 `bc39d187ce3af4fd7c2c1d73246fe218417925522b7cc3100db4916024d9774a`。
- Detached candidate：`/private/tmp/TOP10-runtime-automation-1f3aa30`。
- `validate_runtime_checkout.py`：`RUNTIME_CHECKOUT_GO`。
- Candidate：detached HEAD、tracked clean、denial marker ABSENT。

## Daily 隔離驗證

| 週期 | 結果 | elapsed | peak RSS | swap delta | project bytes delta | files delta | unknown writes |
|---|---:|---:|---:|---:|---:|---:|---|
| cycle-1-r3 | PASS | 105.518s | 1,598,111,744 | 658,767,872 | 309,991,116 | +21 | `[]` |
| cycle-2 | PASS | 70.518s | 2,289,926,144 | 423,236,731 | 309,990,519 | +21 | `[]` |

兩輪均產出 ranking、daily report、Clawd payload/message 與 `automation_status=OK`。`external_send_contract` 明示 Clawd／Ops／Discord send=false、LLM rewrite=false；沒有外送。

- cycle-1 receipt：`/Users/mattkuo/TOP10-runtime-automation-bbd32b4/logs/storage_safety/runtime/daily/preactivation-cycle-1-r3/daily_validation_cycle-1.json`
- cycle-2 receipt：`/Users/mattkuo/TOP10-runtime-automation-bbd32b4/logs/storage_safety/runtime/daily/preactivation-cycle-2/daily_validation_cycle-2.json`

## 安全停止、marker recovery 與 rollback

Fresh unsandboxed `/private/tmp` fixture 透過正式 `app.storage_safety.run_guarded_job` seam 驗證：

- 可控未註冊寫入觸發 `STOPPED`，exit 70。
- target process group 已收束，`final_process_group_quiescent=true`。
- denial marker 與 root receipt SHA-256 精確綁定。
- 第二次 invocation 在 child 前 exit 75；child 未啟動，latest root evidence 保持不變。
- latest 被替換成無關 success 後，第三次 invocation 在 child 前 exit 75，並精確還原 root receipt。
- dedicated rollback tests 5/5，各自在獨立 pytest process 通過，涵蓋 mirror、clear 前中斷、second signal restore、新 marker 與同 hash replacement 保留。

證據：`safe-stop-marker-recovery.json`、`marker-rollback-independent-tests.json`。

## Gemini probe 與 identity parser repair

### 固定候選原始失敗

`bbd32b4` 候選腳本以 `probe` 模式執行，未帶 packet，沒有進入 send／submit／collect，但在 activate 階段失敗：

- `Invalid Gemini window/tab identity`
- `review_packet_sent=false`

既有 Chrome 連線的純唯讀核對仍成立：

- Browser：Google Chrome；Profile：`留痕`。
- 精確 URL：`https://gemini.google.com/app/ea58b54eef550ded`。
- Tab：`TOP10 External Review - Gemini PROD - Google Gemini`。
- 帳號 guard 可見、composer 可見且維持空白 placeholder。
- UI actions：`[]`；沒有輸入、點擊或送出。

### 根因與 bounded repair

Chrome AppleScript dictionary 內的 bare `tab` 是分頁 class，不是 tab 字元。離線字典執行的實際輸出為：

- 舊表達式：`41tab73\n`
- Python 舊 parser：`split("\t")`
- 結果：無法得到兩個 decimal identity。

Working tree 已改為不會出現在 decimal ID 的 `|` 分隔符：

- AppleScript：`return (selectedWindow as text) & "|" & (selectedTab as text)`
- Python：`split("|")`
- 新輸出：`41|73\n`

測試：

- `bash -n scripts/review_gemini_chrome.sh`：PASS。
- `tests/test_gemini_probe_wakeup.py`：5 passed、11 subtests passed；包含 native AppleScript compile。
- `tests/test_external_review_provider_preflight.py`：15 passed。
- `git diff --check`：PASS。

證據：`gemini-identity-parser-repair.json`、`gemini-identity-parser-repair-tests.txt`。

### 新 exact candidate 的 Native2 probe（11:35 歷史）

新 candidate `1f3aa307b3a2e61f2220e6cc48809b7151ba0b77` 已執行兩次同一 `probe-only`：一次直接執行，一次透過 `launchctl asuser`。兩次均未帶 packet、未輸入、未送件，且都在 activate phase、接觸 composer 前失敗：

- `com.apple.hiservices-xpcservice`：`Connection invalid`。
- Chrome dictionary 未能在此 command context 載入，AppleScript 回 `-2741`。
- `pgrep` 亦回 `sysmond service not found`／`Cannot get process list`，無法綁定現有 Chrome bootstrap。

證據：`gemini-new-candidate-probe-direct.json`、`gemini-new-candidate-probe-asuser.json`、`gemini-new-candidate-probe-result.json`。

當時因執行環境阻塞，preactivation 維持 PARTIAL PASS、production 維持 NO-GO。後續 11:41 的 host 通道與 canonical 候選重驗已取得 script-level PASS；本段保留失敗歷史，不是當前 blocker。

## 容量與 production 不變性

- Host total：245,107,195,904 bytes。
- Foundation important-usage available：35,437,750,153 bytes。
- 扣除 6 GiB 後 projected：28,995,299,209 bytes。
- Hard reserve：24,510,719,590 bytes。
- Margin：4,484,579,619 bytes；**容量 admission PASS**。
- Daily guard fresh measure：PASS；memory pressure=2、swap=10,529,674,362 bytes。
- Production plist SHA-256：`17b9f9fb601ec7c58aa68e9b276515d1d5af907812f82900953cdf265d14176a`。
- Production plist／launchctl 仍指向 `/Users/mattkuo/TOP10-runtime-automation-bb55fc4`。
- Production Daily：not running；last exit 75。
- Production denial marker SHA-256：`4338bfbb298ee15eb6abd33c0de9302edd3f1d109d550cbcab67a2c1c1734255`，與 precheck 完全一致。
- Candidate denial marker：ABSENT。

## 保留的失敗證據

`failure-index.json` 列出所有失敗與原始路徑。後續 PASS 沒有覆寫：初始 snapshot window 不符、缺 reference input、錯誤 trigger type、sandbox process identity 限制、Gemini 固定候選 identity parser 失敗、Native2 dictionary／GUI session 限制，以及 detached HEAD synthesis helper 失敗。

## Preactivation 階段邊界（歷史）

截至 preactivation 階段沒有切 launchd、清 production marker、執行 production Daily、送出 review packet 或 push／merge／deploy。14:41 的已授權正式切換另列於文末；不得把這段歷史 NO-GO 當成切換尚未執行。

## 2026-09-30 11:41 GUI 阻擋解除

先以 Codex 本機 host exec 的受審核通道唯讀確認 Chrome PID、AppleScript engine 與 Chrome version 均可取得，再對 exact candidate `1f3aa307b3a2e61f2220e6cc48809b7151ba0b77` 執行原腳本的 `probe`。結果 exit 0、`ok=true`、`phase=execute`、`readiness=input_ready`、`hasComposer=true`；程式未修改，tracked tree 仍 clean。這支持前次 Native2 GUI／XPC 失敗屬執行環境邊界；不需新增 Apple entitlement、常駐 client 或再跑同一失敗通道。

未帶 packet、未輸入、未送件。`hasSendButton=false`，本次 PASS 僅符合既有 probe 的 composer readiness 契約，不證明送件／收件能力。Production marker 與 Daily plist 的 SHA-256 前後完全一致。詳見 [執行與邊界證據](gemini-host-channel-probe-20260930.json) 及 [原始 probe](gemini_probe_20260930_114107.json)。前述 Native2 失敗仍保留為歷史紀錄。

## 2026-09-30 本機整合與正式切換準備

本機 main 現為 `1f3aa307b3a2e61f2220e6cc48809b7151ba0b77`，Git commit object 與原隔離 clone 完全相同。原 commit 包含兩個修補檔及 25 個當時的任務／證據文件；沿用原 metadata 完成本機 commit，沒有 merge／push。較新的 GUI、整合及容量紀錄保留於工作樹，不覆寫為歷史版本。

沿用 `/Users/mattkuo/TOP10-runtime-automation-bbd32b4` 作為 canonical linked candidate，現已 detached pin 至 `1f3aa30`；目錄名稱保留歷史名稱，實際版本以 HEAD 為準。更新前確認無程序與 installed／loaded 排程引用且 Git clean；更新後由主線 repo 執行 `validate_runtime_checkout.py` 得到 `RUNTIME_CHECKOUT_GO`。未新建 worktree 或大型資料副本。`/private/tmp` clone／candidate 合計僅約 146 MB，仍保留，不宣稱可解決容量缺口。

驗收版本對應：`bbd32b4 → 1f3aa30` 在 `app/`、`scripts/`、`config/` 及 dependency manifests 的唯一產品差異為 `scripts/review_gemini_chrome.sh`。兩輪隔離 Daily、guard 與 activation／rollback 的實作未改；原 receipts 仍屬 `bbd32b4`，以此差異核對保留其適用性，沒有冒稱重新執行新版完整 Daily。canonical 新候選本輪定向測試 **20 passed、11 subtests passed**，原腳本 GUI probe **exit 0、execute、input_ready**；測試暫存已回收。

### 容量裁決

11:58:27 +08:00 Foundation：raw **26,587,152,384 B**、important-usage admission **30,784,927,334 B**；reserve **24,510,719,590 B**。原卡 6 GiB 預留後 margin 為 **-168,243,200 B**，因此原預算口徑為 `NO_GO`。Daily guard 單次 measure PASS 只代表它自己的當時門檻通過，不取代這項預留要求。此次未自行縮小預算，也未以背景波動輪詢到 PASS 為止。

### 切換方案（原審核版本；14:41 已依此執行）

- 僅 Daily 與 provider preflight：舊 root `/Users/mattkuo/TOP10-runtime-automation-bb55fc4` → 上述 canonical `1f3aa30` candidate。Fog、retrain monitor、正式 external-review 保持原設定。
- 已比較 installed 與候選 plist：除了 runtime 路徑沒有其他差異；Daily 平日 17:30、provider preflight 每日 17:40；兩者 `RunAtLoad=false`。切換不包含 kickstart 或人工 production Daily，後續自然 Daily 仍可能依既有產品設定產生正式報牌／外送，須包含於 Owner 的 production 授權。
- 執行前必須容量重新通過原預算、candidate HEAD／同 repo／clean／marker absent 仍相符、兩個 job 均未 running、舊 root 與 plist／marker 雜湊未漂移。容量不足時不執行下列命令。
- 使用既有正式 transaction；CLI 沒有 dry-run，不能為了驗證把 `run()` 或 `_prepare()` 當成純讀取（prepare 也會取得舊 identity lock）。本輪只讀取實作與比較 plist，未呼叫它們。

```bash
cd /Users/mattkuo/TOP10new
.venv/bin/python -B scripts/activate_automation_runtime.py \
  --runtime-root /Users/mattkuo/TOP10-runtime-automation-bbd32b4 \
  --accepted-commit 1f3aa307b3a2e61f2220e6cc48809b7151ba0b77 \
  --expected-old-root /Users/mattkuo/TOP10-runtime-automation-bb55fc4 \
  --job daily --job external-review-preflight \
  --receipt docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/activation-1f3aa30.json \
  --activate
```

receipt 必須為未存在的本次 invocation 路徑。執行入口會保存 `activation-1f3aa30.prestate/` 原 plist、持有舊／新 guard locks、核對 identity 後建立並清除**自己建立的新 runtime marker mirror**，再依序 bootout／replace／bootstrap 兩個 job。舊 production denial marker 原件不刪除。任何新 marker／identity 漂移須拒絕，不得手動 `rm` 繞過。

### 回退與驗收

- transaction 尚未提交時任一步失敗／中斷：由原入口依副作用紀錄反向回退，restore snapshot plist 及原 loaded 狀態，核對原 marker／非目標 plist 雜湊；新出現或被其他 writer 替換的 denial marker 保留。若 rollback verification 失敗，維持失敗裁決，不重試 activation 掩蓋錯誤。
- 切換提交後若自然週期再出錯：這不屬於同次 transaction 的自動 rollback。先依 storage guard 停損；恢復舊 root 前須確認新版程序已停止，使用本次 prestate 還原兩份 plist 與原 loaded 狀態，保留舊 STOPPED marker，因此回退回的是可核對的安全停止基線。禁止把逆向 activation（舊 root 尚有 marker）當作可直接重跑的通用 rollback。
- bootstrap 成功只得到 `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`；仍須保存自然週期來源、ranking／report／payload、按原契約的外送 receipt、資源曲線與終端狀態。此次 GUI probe 不證明 send／collect 或自然排程已恢復。

11:58 的 [整合與上線前核對](integration-preflight-20260930.json) 記錄測試、canonical GUI probe、版本適用性及當時容量。**當時 production 為 NO-GO；其後 Owner 完成清理並授權，本次 14:41 重核與正式切換結果如下。**

## 2026-09-30 14:41 正式切換完成

Owner 明確表示「可確認沒問題就 核准修復」。本次授權限 Daily 與 provider preflight；未 push、未改 Fog／monitor／正式 external-review，也未人工觸發工作。

- Mutation 前：canonical exact SHA／clean／同 repo GO，32 個 manifest entry 原始 size／SHA-256 一致，兩個 job loaded／enabled／未 running、舊 runtime／plist／marker 與前次證據一致。Foundation admission **34,288,936,550 B**，原 6 GiB 預留及 reserve 後 margin **3,335,766,016 B**，PASS。
- 真實 host launchd 通道：唯一名稱、僅執行 `/usr/bin/true` 的一次性 agent bootstrap exit 0、command exit 0、bootout exit 0；最後 service absent，暫存目錄已回收。不是 production workload 或常駐系統。
- 使用上方既有正式 transaction，14:41:40 完成；命令 exit **0**，sealed [activation receipt](activation-1f3aa30.json) status=`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`，failure=null、rollback_errors=[]、mask_restore_errors=[]。receipt 的 signal teardown 欄位要求 process exit status，已由實際命令 exit 0 補足，不能只看 receipt 自稱完成。
- 14:42:58 獨立回讀：Daily、provider preflight installed SHA-256 分別為 `f412991ad943aef117878d49bf972e63769db0a59b58272efa5e12df153608de`、`79bd601886853dbaac8875a56fd8e3a86027dc1e91a50f9afc391cda29fbbdff`，與 transaction 完全相符；loaded argv 指向 canonical runtime，兩者 enabled、not running、runs=0，未在切換時偷偷執行。
- 舊 `bb55fc4` Daily marker 原件 SHA-256 仍為 `4338bfbb298ee15eb6abd33c0de9302edd3f1d109d550cbcab67a2c1c1734255`；新 runtime 兩個 marker 均 absent。全部非目標 plist 未變。`activation-1f3aa30.prestate/` 兩份原 plist 與切換前雜湊相符，可作回退基線。
- 切換後 Foundation admission **34,294,556,262 B**，原預算後 margin **3,341,385,728 B**。未改預算、門檻或 storage policy。

完整重核與獨立回讀沿用單份 [activation-precheck-20260930.json](activation-precheck-20260930.json) 的 `post_activation` 欄位；未修改 sealed transaction receipt。

下一步是原排程的自然驗收：今日 17:30 Daily、17:40 provider preflight（Asia/Taipei）。目前尚無新版自然執行、報牌／外送成功的證據；必須讀取新版 runtime 的當日 receipt、calendar-origin、輸出、send receipt 與資源終端狀態，不可用本次 bootstrap 或舊版 success 取代。若新 marker 出現即依原 guard 停損，保留證據，不自動 clear／kickstart 或反覆切換。後續若需回退已提交的切換，依前述 prestate 流程回安全停止基線；本次並未執行回退。

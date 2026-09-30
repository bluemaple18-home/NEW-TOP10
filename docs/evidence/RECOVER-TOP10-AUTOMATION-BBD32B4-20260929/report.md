# RECOVER-TOP10-AUTOMATION-BBD32B4-20260929

## 裁決

- **候選 preactivation：PARTIAL PASS／NO-GO**。
- **production activation：NO-GO**。
- Daily 兩輪隔離執行、安全停止、restart denial、marker recovery、rollback、容量與 production 不變性均已通過。
- 真實 Chrome 的精確 profile／tab／composer readiness 與「未送件」已通過。
- `Invalid Gemini window/tab identity` 的根因與修補已在 source working tree 驗證；`bbd32b4` 固定候選未改動，也尚未建立新 commit／新候選。當前 Native2 command context 沒有可用的 macOS GUI／XPC session，故仍缺修補後的真實 host probe。

## 固定候選

- Runtime：`/Users/mattkuo/TOP10-runtime-automation-bbd32b4`
- Commit：`bbd32b4f017498b413a32a1171aec76f426441a3`
- 狀態：detached HEAD、tracked tree clean。
- 實際大小：`1,980,448,768` bytes，低於 6 GiB 上限。

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

### 真實 host rerun 限制

修補後的兩次 probe 都未帶 packet、未輸入、未送件，但目前 Native2 command context 不共享使用者 GUI session：

- 使用 application name 時，`com.apple.hiservices-xpcservice` connection invalid，無法載入 Chrome dictionary。
- 使用 absolute Chrome dictionary path 的暫存腳本可編譯，但此 command context 回報 `Gemini browser is not running`。

這兩次屬執行環境限制，不當作產品 probe verdict。Identity parser repair 已驗證，但 `bbd32b4` 固定候選仍未包含修補，且尚缺新 exact candidate 在有效 GUI host session 的 script-level probe；因此 preactivation 維持 PARTIAL PASS，production 維持 NO-GO。

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

## 邊界確認

本輪沒有切 launchd、沒有清 production marker、沒有執行 production Daily、沒有送出 review packet、沒有 push／merge／deploy。只新增本卡與 evidence 文件；production activation 維持 NO-GO。

## 下一個必要 slice

將目前兩檔 bounded repair 納入新的本機 commit，建立新的 detached exact candidate，再於可存取使用者 Chrome GUI session 的環境重跑同一 `probe-only`。本輪未 commit、未 push。取得新 candidate script-level PASS 後，仍需另取得 production mutation 明確授權，才能評估切換 launchd 與 marker handling。

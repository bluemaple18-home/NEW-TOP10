# TOP10 自動化全鏈路排查結果

> 2026-09-27 容量整理：本目錄原始輸出與重現腳本已逐檔 SHA-256 核對後合併為 [證據壓縮包](raw-evidence-2026-09-27.tar.gz)。文中原始檔名為包內路徑；需重跑時先在本目錄執行 `tar -xzf raw-evidence-2026-09-27.tar.gz`，再依原說明操作。歷史驗證結果不變。

查核日：2026-09-22，Asia/Taipei。主要快照：15:58:07～16:02:54；全部早於當日 17:30／17:40 排程。

研究終態：`INVESTIGATION_BLOCKED_WITH_EVIDENCE`。已定位中斷機制與目前狀態；主機 swap 的程序歸因、Chrome 分頁內部逾時原因、歷史自然觸發 provenance 仍無法由現有證據證明。這不是 automation 恢復驗收。

## 判定

1. **Daily 自 9/9 被容量停損，之後被持久標記封鎖。** 當日 17:55:47 的可用空間低於 deployed guard 的 10% 門檻，guard 終止 ETL。空間現在回升，標記仍禁止自動重啟；並非每天都重新跑到同一處 crash。
2. **停損時最大可見變化是主機 swap，並非專案檔案膨脹。** 最後 57 秒 free 減少 3.223 GB、swap 增加 3.264 GB，專案僅增加 32,301 bytes。Daily 同期進入向量化指標運算且 RSS 上升，但 swap 是全機統計，不能把全數歸因給 Daily，也不能直接宣稱記憶體洩漏。
3. **9/8 確實完成報牌並取得 Discord 訊息 receipt。** 9/9 停在 ETL 量能指標計算，無當日 ranking／payload／LLM rewrite／send artifact。舊 `automation_status.json=OK` 仍是 9/8；wrapper 已識別過期，不能拿它當現在健康。
4. **Provider preflight 的近期主要故障是 Gemini Chrome 分頁執行 JavaScript 逾時。** 9/18～21 每輪 ChatGPT PASS、Gemini `-1712`。9/14、16、17 兩者曾同時 PASS；不是永久失去登入或所有 Chrome 操作都壞。`has_send_button=false` 不違反現行 probe contract，但 probe PASS 也不證明正式問答可完成。
5. **正式 external-review 是尚未重新啟用的 production candidate。** disabled、unloaded 且 plist 仍指向 development checkout；獨立 external-send authority、detached runtime、容量與自然驗收尚未齊備。預檢成功不會自行啟動送審。
6. **Retrain label 跑的是 monitor，並未自動重訓。** 9/9～22 共 14 份 guard receipt：13 次 OK、9/12 一次因啟動空間不足而未 spawn。9/22 monitor 成功，但 health report 是 WARN，所讀最新 ranking 仍為 9/7；不能推論生產資料已同步更新或模型健康全綠。自然觸發的歷史證據仍缺。

## 身分與狀態矩陣

路徑別名：`D=<home>/TOP10-runtime-automation-bb55fc4`；`R=<home>/TOP10-runtime-automation-8fe9366`；`W=<repo-root>`。實體完整路徑、argv、plist digest、環境欄位在 `closing-snapshot.json.jobs`。

| label | installed／loaded／runtime | 日曆（台北） | 本次狀態 | 結果／驗收 |
| --- | --- | --- | --- | --- |
| daily | D，detached `bb55fc4c1b316c43398774133d9f6b73ecb53dbe`；tracked clean；loaded argv 與 plist 相同 | 週一～五 17:30 | enabled、not running、runs=10、exit=75 | root receipt 9/9 STOPPED，marker 存在；未恢復 |
| external-review-preflight | 同 D；tracked clean；loaded argv 相同 | 每日 17:40 | enabled、not running、runs=14、exit=1 | 最新 9/21 CHILD_FAILED；marker absent；provider BLOCKED |
| external-review | plist 指向 W，當下 main=`225a32bec22970e9c04672e4889388d9486b878a`；沒有 loaded runtime | 每日 17:50 | disabled、service not found | 預期尚未 activation；不得把 W 的 HEAD 當成 deployed SHA |
| retrain | R，detached `8fe93667e2673a366239aa84b36f481fba79d89e`；tracked clean；loaded argv 相同 | 每日 02:00 | enabled、not running、runs=14、exit=0 | 最新 9/22 monitor OK；marker absent；natural acceptance pending |

三個 enabled job 都經 `run_with_storage_guard.sh`，該 wrapper 在 source 第 5～6 行切至自身 runtime；四份 plist 都沒有 `WorkingDirectory`，不是 cwd 已被設定成 development checkout。Retrain exact child 為 `daily_retrain.sh monitor --trigger scheduled`，installed env 只有 `TOP10_RESOURCE_PROFILE=host_full`；Daily／preflight 無 plist env override。瀏覽器 profile 未在 plist 或 adapter 中釘選。

四份 plist digest 都與既有 retrain activation verdict 的記錄相同。15:58 與 16:02 的 61 個來源 digest 無變化。這是本次短窗一致性，不能回溯證明每輪歷史 identity。Git 工作樹初始只有未追蹤研究卡；本輪僅新增研究檔並更新該卡。

## 時間線與產物鏈

以下時間均為台北；JSON 原始 ISO 時間多為 UTC，invocation 名稱中的 Z 也是 UTC。每列可在 `snapshot.json`／`details.json` 及 manifest 回查。排程時間接近只支持關聯，不能單獨證明 calendar fire。

| 時間 | 已保存事件 | 解讀 |
| --- | --- | --- |
| 9/8 17:30:01～17:58:40 | Daily guard `daily-20260908T093001Z-16718` OK，child=0、process group quiescent | 最後可證實完整執行；natural_trigger_verified=false |
| 9/8 17:40 | preflight guard CHILD_FAILED；dated log 顯示兩 provider BLOCKED | 後續同日人工 probe 覆蓋 dated report，不能拿今天讀到的 PASS 替代此輪 |
| 9/8 17:58:33 | Clawd provider receipt 有 primaryPlatformMessageId、sentAt；send status OK、dry_run=false | 已取得 Discord 送出回執；不代表收件者已閱讀 |
| 9/8 18:51 | `external-review-preflight-20260908T105122Z-60843` manual、OK | 兩 provider PASS；非自然週期驗收 |
| 9/9 02:00 起 | retrain monitor 新 runtime 開始留下成功 receipt | 日期採台北；invocation 為前一日 18:00Z |
| 9/9 17:30:05～17:55:50 | Daily 先通過 preflight，17:55:47 live sample 越線，child=-15；marker root 綁定此 invocation | 當日 ETL 中止；最終 process group quiescent |
| 9/9 17:40 | ChatGPT／Gemini 均 `review tab not found` | 與 9/10 起的 JS 執行逾時是不同症狀 |
| 9/10 17:40 | ChatGPT PASS、Gemini AppleEvent `-1712` | 目前 retained post-activation 資料內第一個此型逾時 |
| 9/11、12 17:40 | preflight `HOST_START_FREE_SPACE_BELOW_THRESHOLD`，未 spawn | 這兩日無 provider report，不能判成瀏覽器故障 |
| 9/12 02:00 | monitor 同樣因 host start free 不足而 NO-GO | 主機容量曾跨鏈影響；未留下持久 restart-denied |
| 9/13 17:40 | 兩 provider tab not found | 現在 Chrome 主程序的啟動時間為 9/13 17:40:03；無法以今日程序還原更早分頁 |
| 9/14 | preflight 兩者 PASS | 日曆候選成功，缺獨立 provenance |
| 9/15 | ChatGPT PASS、Gemini `-1712` | 故障非永久性 |
| 9/16、17 | preflight 兩者 PASS | 兩個相鄰成功候選仍不等於驗收完成 |
| 9/18～21 | 每輪 ChatGPT PASS、Gemini `-1712` | 最新連續四日相同失敗層 |
| 9/13～22 02:00 | monitor 連續十份 OK；9/22 終端 artifact finished=02:02:45 | 13 份成功 guard 都 quiescent；health 為 WARN，不是訓練／promotion |
| 9/22 15:58～16:02 | Daily 仍 exit=75、marker 存在；host free 約 34.5 GB | 本日 17:30／17:40 尚未到，不列 missing run |

### Daily 各段是否完成

| 階段 | 9/8 | 9/9 |
| --- | --- | --- |
| ETL／資料驗證 | terminal steps `etl`、`data.validate`、`data.freshness.after_etl` OK | 資料回補／整合有進展，停在 ETL 量能指標 VWAP 計算；不能宣稱 ETL 完成 |
| ranking／Top10 | ranking step、artifact、payload top10_count=10 | ranking artifact absent |
| payload／訊息 | 當日 payload、canonical message 存在 | 當日 payload absent |
| LLM rewrite | status OK，selected_model=`gemini-2.5-flash-lite` | 當日 rewrite artifact absent |
| publish／send | send_attempted=true、exit=0、Discord 訊息 receipt 存在；ops report 亦成功 | 當日 send artifact absent；wrapper 未走到 sending |
| 狀態 | dated terminal status 與 guard、send 時間相符 | latest automation status 仍停留 9/8；log 明示拒絕 stale status |

9/8 LLM rewrite 是模型 API 工作，與 ChatGPT／Gemini browser external-review 是不同鏈。Artifact 缺統一 guard invocation_id：此處以 exact runtime、當日 guard 時窗、wrapper log、dated terminal artifact 和 provider receipt 交叉關聯，沒有假裝存在更強的 invocation 綁定。

## Daily：根因與替代假說

Deployed `app/storage_safety.py` 以 `shutil.disk_usage(root)` 取得 free；runtime threshold 為 `max(21,474,836,480 bytes, 245,107,195,904 × 10%)`，即 **24,510,719,590 bytes（24.51 GB／22.83 GiB）**。不能簡稱「只需 20 GB」，也不是 free=0 的磁碟滿。

| 觀測 | 數值與意義 |
| --- | --- |
| 啟動 free | 27,378,577,408；距 runtime reserve 僅約 2.87 GB |
| 17:54:50 → 17:55:47 | free 27,264,446,464 → 24,041,295,872；swap 7,632,458,874 → 10,896,602,562 |
| 同一分鐘 Daily RSS | 1,023,475,712 → 2,435,825,664；process tree 包含 `app.pipeline_cli run --start-date 2025-07-16 --end-date 2026-09-09` |
| 專案整輪增長 | 22,817,022 bytes、18 files；終值 3,286,637,406 bytes、31,051 files，低於 6 GiB／60,000 上限 |
| 前一成功輪 | 9/8 主機 free 淨減約 3.16 GB；因此 9/9 啟動剩餘 headroom 小於已觀測成功輪的主機淨減量，但該淨減量仍非專案獨占歸因 |
| 現在 | shutil 約 34.50 GB free；diskutil 同 APFS container 約 34.50 GB。當下恢復不能否定歷史 raw free 越線 |

| 假說 | 反證／限制 | 判定 |
| --- | --- | --- |
| 專案 log／檔案暴增吃光容量 | 最後一分鐘 project 只增加 32 KB；整輪約 22.8 MB，未越 project budget | 不支持作為主要下降來源 |
| Daily 自己的 swap 尖峰造成 raw free 下降 | 時間與 ETL RSS 尖峰相符；全機 swap 增量與 free 降幅近似，但缺各程序 swap 歸因／其他 writer 歷史增量 | 有力候選，**未確認程序根因** |
| guard RSS 或 swap 數值預算直接殺掉工作 | receipt 唯一原因為 host free；RSS peak <4 GiB。source 中 swap 超額且 pressure 可讀不等於直接 stop | 排除為此次實際 stop reason |
| APFS snapshot／purgeable 造成 raw 與實際可用量差異 | 沒有 incident 時 Foundation important-usage／snapshot 序列；今日 diskutil 不能重建當時 | UNKNOWN；不宣稱 guard 誤判 |
| 現在 scheduler 沒跑或 lock 卡死 | daily enabled/loaded、runs=10、exit=75；source 有 exact marker match 後直接 return 75；目前 lock 無 lsof 開啟者 | 持續封鎖機制已定位；後續每輪起因缺 archive，不能逐輪證明 |

Persistent denial 是第二段因果：marker 的 root invocation 與 9/9 receipt 一致，`automatic_clear_allowed=false`。Source 1785～1810 顯示匹配既有 root receipt 時直接 return 75，保留舊 latest、不新增每輪 denial receipt。因此「latest 停在 9/9」**不代表 scheduler 自 9/9 完全未觸發**。runs=10 與 2 次原始執行加後續 8 個工作日吻合，但 count／時間吻合不足以替代逐次歷史事件。

容量規則另有版本落差：本機現行 `rules/24-storage-capacity-safety.md` 要求 macOS raw＋Foundation important-usage、projected reserve；D 的 deployed guard 仍用 raw free，啟動檢查沒有本輪 projected growth 扣除。這是後續 recovery 必須釐清的量測契約差異；本輪未改規則或 runtime，也不據此追溯改判舊事故。

## Provider：已定位到哪一層

來源為 D 的 adapter、provider-specific report 與 guard archive。Python 依序 probe ChatGPT、Gemini；probe 本身會建 JS 暫存、選分頁並執行 JS，因此本輪完全未主動重跑。

Gemini deployed AppleScript 遍歷 **Google Chrome 的所有視窗與 tabs**，以 URL substring 選第一個符合的分頁，然後 `execute t javascript jsSource`。採 deployed 預設 URL、guard TMPDIR 及同長 mktemp 名稱靜態還原，stderr **544:573 精確對應 `execute t javascript jsSource`**（`details.json.applescript_offset`）。這把逾時定位到「已選目標 tab 後，Chrome 執行分頁 JS 的 AppleEvent 回應邊界」。不是 Python subprocess 的 timeout；`run_command` 沒設 timeout，adapter probe 也沒有顯式 AppleScript timeout。`WAIT_SECONDS=45` 用於送件後等待，不能解釋 probe 的此型錯誤。

- **可排除**：近期持續失敗並非 TMPDIR missing、tab-not-found 或 guard 容量 stop；這些都有不同的既有證據與錯誤型別。同輪 ChatGPT 成功也不支持整個 Chrome 完全不可用。
- **仍未知**：目標 renderer 忙碌、JS／DOM 執行阻塞、Chrome 自動化事件排隊、特定 session/profile 的問題。沒有 trace 可進一步切分；不把 `-1712` 當登入過期或網路故障。
- **精確 profile 未證明**：plist 無 override；adapter 只有 app＋URL substring，沒有 profile ID/window ID/tab ID receipt。相同 URL 多分頁的選擇風險存在，但沒有證據證明當時挑錯。Chrome 現在 PID=43192，start=9/13 17:40:03，不能用現在的程序證明 9/10 session。
- **ChatGPT PASS 的範圍**：JS `ok=Boolean(composer)`，Python 檢查 payload、session-expired 字樣與 composer；沒有要求 send button 存在。空白輸入時 send button 未出現與 PASS 相容，但「為何 button 不存在」未經頁面證據確認。未測 fill/send/collect，不可宣稱正式 GPT 自動問答恢復。
- **dated report 覆寫缺口**：9/8 17:40 的 BLOCKED 被 18:51 manual PASS 覆寫；guard archive 與 log 才保留兩輪差異。最早 9/1～7 的 dated files 是 runtime 既有歷史資料，只作背景，不能冒認全由 bb55fc4 部署後執行。

## Actual external-review 為何未啟用

A6 intent 明示 `SHOULD_BE_PRODUCTION`，但要求獨立 authority／storage／provider preflight／detached activation／自然驗收。Installed plist 仍是 development checkout 的 legacy direct runner，hash 與既有 activation out-of-scope snapshot 相同；不是意外失去一個原已恢復的 production service。

最小依賴順序：Daily 當日 terminal OK＋新鮮 artifacts → provider 可用且具身分證據 → exact detached runtime 與容量／rollback 驗證 → 明確 external-send authority → 單 job activation → invocation-bound 自然週期與 provider terminal outcome。Host runner 預設等待 Daily OK 最多 3600 秒；即使單獨 enable，Daily 舊 status 與 Gemini 問題仍未解決。此順序是恢復條件，並非本輪授權或已執行動作。

## Retrain monitor：成功與驗收缺口

R 的 exact argv 及 `daily_retrain.sh` 分支證明執行的是 `monitor`；`run_automation` 的 monitor 分支執行 PSI／factor／industry momentum／model health。13 次成功 guard、13 份 dated health report 與 dated log 相符；9/12 的 NO-GO 無 child，故不是 model training crash。9/22 七個 terminal steps OK，health WARN：factor warn_count=39、PSI 僅覆蓋 84/86 features、industry momentum decision=reject。Monitor exit=0 表示報告生成成功，並不等於所有監控值合格。

另有資料新鮮度限制：9/22 health 的 `ranking.latest` 是 **9/7**；monitor metadata 的 source/output/runtime 全部指向 R。至少排名輸入仍是舊的 runtime 資料，不能用新的 report timestamp 證明追蹤到最新 Daily。是否所有 feature 資料也 stale 未在本卡擴大掃描；後續先查明既有資料交接契約，不能直接安排跨 runtime sync。

自然驗收有三項既有要求，不能以本輪研究放寬：

| 證據 | 現況 | 最小下一步 |
| --- | --- | --- |
| calendar fire 與 manual kickstart 區別 | wrapper PPID=1 只代表 launchd 候選；`trigger_type=natural` 均伴隨 natural_trigger_verified=false。查 9/21 01:59:30～02:02:00 launchd unified log 得 0 rows | 下一輪前先確認既有 OS 事件是否提供可辨識的 origin；若沒有，回 Mainline 裁決可接受證据來源，不能捏造自然性 |
| 每輪 loaded identity／service continuity | 現在 plist、argv、SHA 與 activation 相符；boot=9/7、WindowServer/loginwindow 存續到今天；仍不能排除單 job unload/reload | 有 authority 後，於所需自然窗保存前後 loaded argv／plist hash／runtime SHA／service generation，並關聯 invocation |
| receipt 的外部 digest anchor | 既有 archive/latest 在同 runtime，研究時才產生 hash 無法回溯形成當時 anchor | 每輪終端即將 digest＋觀察時間存入既有 evidence 目錄，位於 runtime receipt tree 之外；不新增 ledger／簽章平台／watcher |

既有卡對同步竄改提出的 digest anchor 已是明示契約；本輪不擴大成 hostile／enterprise 防竄改模型，也不擅自移除要求。已取得成功執行證據，缺的是自然來源、當輪 identity 與獨立錨定。有限時間窗的 OS log 0 rows 代表此查詢拿不到證据，不代表從未觸發，也不是所有歷史永久不可追回。

## 文件與 Git／runtime 落差

| 來源 | 落差 | 建議文字／正確來源 |
| --- | --- | --- |
| CURRENT_OPERATIONAL_FRONTIER，9/14 更新 | 未突出 Daily 9/9 STOPPED 與仍存在的 marker，讀者易以為只剩 Fog/retrain 自然驗收 | 加列 Daily「容量 STOPPED＋persistent denial」及 preflight 最新 provider failure；本報告不直接改 canonical 文件 |
| 同文件 Retrain「runs=6／三輪成功」描述 | 數值是當時快照，現已 14 次、13 OK／1 NO-GO；不是全部成功 | 使用帶日期的查核值，保留 natural pending；以 archive 而非 runs 判斷成功數 |
| 同文件 current state 與 operational frontier 第 4 項 | 文件內 Fog 新路徑 67f2d28 與舊 c69834a 敘述並存 | 只列文件內部不一致，交原 Fog 線校正；未查 Fog runtime |
| A6 intent「目前 enabled 三個／另四個 candidates」 | 是 retrain activation 前的歷史快照 | 標為 9/8 當時狀態；retrain 已獨立啟用，其他 candidates 不隨之獲授權 |
| `artifacts/automation_status.json` | 9/8 OK 仍在；9/9 被 signal 殺掉沒有更新 terminal | 顯示 run_date/started_at 和 guard STOPPED，不能只讀 status 字串 |
| preflight 9/8 dated JSON | manual PASS 覆蓋同日 scheduled candidate 的 BLOCKED | dated latest 僅代表最後寫入；需結合 guard invocation 與 provider log |
| main `225a32b` 對照 D/R | Git 有後續整合／文件更新，但 D/R 是固定較早 SHA | source fix／文件合併不等於 production rollout；activation 必須逐 job 明示 |
| 現行容量規則對照 D source | Foundation/projected admission 與 deployed raw free 不同 | 下一個 recovery slice 先鎖定有效量測契約及版本，不直接換閾值 |

## 排序後的最小處理方案

以下是可開卡的候選 scope，**沒有實作或 production authority**。

| 優先 | measured gap／source seam | 最小處理與驗證 | 為何不更少／不更多、回退 |
| --- | --- | --- | --- |
| 1 | Daily 的 host headroom 不足＋ETL 時 swap 尖峰；D `app/storage_safety.py` sample/preflight/runtime，`config/automation.yaml` 420 日窗口 | 先鎖 raw／important-usage／projected 契約；取得有容量保護的隔離 representative ETL 權限，量測程序 RSS、全機 swap 與 project 增量。RED：事故 samples 越 reserve；工作負載 RED 需隔離重現，不改信號權重。若實測證明可由現有 resource profile／計算批量修正，才做該最小修補；保留原停損 | 只清 marker 或降低閾值無法處理尖峰；不先全面改 pipeline／清全機資料。回退 exact old runtime、policy、plist、marker；通過容量試跑／停損演練後另行 bounded recovery |
| 2 | Gemini JS execution 邊界逾時且無 profile/tab/phase 證據；D `review_gemini_chrome.sh:536`、`run_provider_preflight:510` | 下一張 bounded card 先用隔離 adapter fixture 驗證「tab lookup成功、execute timeout」能保留不同分類；經單獨授權再做 exact browser/profile 的單次無送件定位，保存選中 tab、execute 開始／結束與耗時。真正 renderer／session 原因確認後才選修法 | 單純延長 timeout／重啟 Chrome 沒有因果證据；不換 provider 平台或清登入資料。回退 adapter 與配置；恢復後要兩個自然 preflight 成功鏈 |
| 3 | 舊 OK、manual-overwrite 使狀態容易誤讀；既有 P0 A7 | 先修文件表述；若需產品補洞，限定既有 status reader／receipt：舊 run_date＋guard STOPPED 不得呈綠，同日 manual PASS 不得覆蓋排程驗收證据。fixture 使用本卡日期與 invocation 作 RED 設計 | 只說「enabled」不足；不建新監控／writer／資料庫。回退既有 reader/receipt 小改；不重放發送 |
| 4 | Retrain natural provenance 與 ranking freshness | 先確認既有資料交接契約；自然窗只採上表所需 provenance，沿用既有 evidence 目錄。需新 observer 或資料 sync 時另取 scope/authority | 單次 report OK 或目前 hash 不足；不啟用自動 retrain／promotion／新 watcher。若自然 provenance 不可取得，維持 pending |
| 5 | actual external-review 尚未 activation | 依上節依賴，先做 exact detached candidate、容量／rollback／provider 驗證，最後才取得外送與單 job activation 授權 | 不能直接 enable 舊 development checkout runner；不 bulk-enable 其他 candidates。回退原 disabled/unloaded plist |

Daily 與 preflight 恢復後，各自仍需 P0 A5 的連續兩個自然週期。其他 job 按自己既有 acceptance；本輪沒有新增較高驗收級別。

## 驗證與範圍限制

- `assertions.py` 已執行：**16/16** 既有證據斷言通過；`--require-healthy` **exit=1**，明確抓到 Daily marker、Daily STOPPED、provider BLOCKED 三項現存不健康狀態。這是檔案證據訊號，**不是重現 workload 的 RED，也不是修復 GREEN**。
- `REPRODUCTION_BLOCKED_BY_SCOPE`：研究卡明禁 workload/manual run/provider probe/fixture 實作，所以未實際重現 ETL 尖峰或瀏覽器逾時。根因底層未證明處保留 UNKNOWN，不藉 snapshot 測試升格。
- lsof 唯讀未找到 daily/retrain lock 的開啟者；兩者 lock 是空檔，無 owner metadata。未取得／釋放任何 production lock；結果只支持查核當下無可見開啟者。
- 系統 log／diskutil／ps 初次受 sandbox 限制，經純唯讀 escalation 成功取得有限範圍結果；未操作 GUI／browser。查核沒有直接讀 Fog runtime／marker／heartbeat，也未建立 automation。
- 未修改 production、未清 marker／lock／cache、未改 plist、未重跑工作、未 publish/send、未模型訓練、未 push。所有研究寫入限於本卡與本 evidence 目錄。

可重跑查詢、SHA-256 manifest、容量數值、source 行號與限制見 [evidence-index.md](evidence-index.md)。

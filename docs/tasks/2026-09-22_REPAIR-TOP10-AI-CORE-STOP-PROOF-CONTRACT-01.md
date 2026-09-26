# REPAIR-TOP10-AI-CORE-STOP-PROOF-CONTRACT-01

## Objective／Status

- 工作名稱：TOP10 × ai-core 巢狀工作放行與完整停止證明接線。
- root question：外層如何在內層工作開始前取得完整程序歸屬，並在正常完成或中斷後證明後代全數停止，才清理 owned root？
- status：ES_PATH_CLOSED_BY_OWNER／MAINLINE_REPLAN_REQUIRED；Owner 2026-09-26 重申不要擴大至 Apple 授權等級，ES-P3 取消，不再等待 Apple 帳號／profile／簽署資訊。P1 離線成果僅保留為證據，不接入產品。完整停止證明缺口未解，執行安全判定仍為 `BLOCKED_WITH_EVIDENCE`；R2-C／R2-I／R2-V 未啟動。Repair 2 既有核准不重問。
- authority：Owner 於 2026-09-22 在確認「ai-core 先做可行性、兩邊各修自己的部分、TOP10 Mainline 整合驗收、兩名獨立 Reviewer」後，明確指示「做啊開卡」。本輪據此核准同鏈 Repair 2 有界成本：可行性驗證、成立後的雙邊最小修補、必要受控 fixture 與兩名獨立驗證。沿用本卡，不新建問題或重置修復次數；不是跨 repo 代寫、Daily 試跑或上線授權。
- 關係：延續 `REPAIR-AI-CORE-NESTED-SANDBOX-TEARDOWN-01` 未完成的正常 nested 成功路徑；不是另開問題以重置 repair 次數或繞過原驗收。

### Owner 範圍更正（2026-09-26，優先於下方歷史計畫）

Owner：「我不是沒有要搞到apple的那種等級嗎」「之前不是說了？」TOP10 Mainline 接受更正：將原本的最小修復推到 Apple 特殊授權及原生監聽，屬於本 Mainline 範圍判斷失誤，不應要求 Owner 再回答帳號／entitlement 或承擔這條工程路線。

- 關閉 ES-P3／原生 adapter／Apple entitlement 申請／簽署配置／此路線的 root 或 FDA 操作與宿主監聽；不保留為等待 Owner 答覆的 active blocker。撤回此前 Apple 帳號問題。
- 已完成的 ES-P1、研究與測試紀錄保留，不刪除、不部署、不繼續擴充。下方 ES 分工、權限決策與准入計畫僅屬歷史，不能自動恢復。
- 返回 TOP10 原始故障及現有環境內的最小處理方案。Mainline 需重新區分 Daily／provider 的實際修補、隔離驗收依賴與自動清理需求；不能把未獲採用的 ES 設計當成所有後續工作的必備條件。此處沒有宣稱已有較小且驗證通過的替代方案。
- 不以取消 ES 自動放行 workload／cleanup，不將 unknown 當 PASS，不重跑已淘汰的 kqueue／ACK 候選，不新增同等規模的另一套平台或第三輪修復。production 停損、Daily 試跑／部署限制保持原授權邊界。
- TOP10 Mainline 負責本次收斂與重新裁決，直接通知 ai-core 停止 ES 路線；Owner 不必再傳話或重新核准 Repair 2 成本。

全鏈重查已於 9/26 23:54–23:57 取得新證據，見 [重新裁決報告](../evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/recheck-report-2026-09-26.md)。本卡是隔離驗證工具的缺口，不是原始 Daily 容量事故原因，也不是 Gemini／monitor 純政策核對的依賴。Apple 路線保持關閉；完整 ETL 的安全入口尚未證明，不假裝已有替代解法。ai-core 已直接確認停止並同步自身兩卡；下一步由 TOP10 Mainline 按最新容量、monitor 重型研究與 Daily 候選重新裁決，不再派平台研究。

## Evidence／接回基線

- ai-core 已實機重現舊路徑：外層退出 143，另 SID child 仍活，owned root 已消失。這是受控 fixture，不是 TOP10 歷史事故歸因。
- ai-core 新增 opt-in `--require-complete-stop-proof`：觀察到 fork 或證明不完整就保留 root、回報 unknown isolation；正常 TOP10 會 fork，因此目前仍無正常清理成功路徑。
- ai-core 已修匯出失敗仍刪原始證據、native 程序查詢錯誤判讀；交回回報 105 項相關回歸及兩名 Reviewer 複驗通過，不是本卡已完成。
- TOP10 `_spawn_verified_process_group` 已有可信 bootstrap 等待閘門，鎖定 identity 後才送出放行訊號；尚無外層確認交接接線。既有 group quiescence 不能單獨證明跨 session 後代全數停止。
- 主線已核對交回時兩個產品檔的 SHA-256；接手需再次核對 dirty tree 與版本，不照抄過時證據。

| 檔案 | 接回 SHA-256 |
|---|---|
| `<ai-core-root>/scripts/tmp_artifact_lifecycle.py` | 0a2642073f4182db2d34e6e176517c49f0ecc80ee587b78e8d8928f0968523aa |
| `<top10-root>/app/storage_safety.py` | 7a74c41b618a0113dd21195845d75c5461e397ada7f653820de79d73df51a52e |

## Scope／雙邊責任

| Owner | 本卡責任 | 不得代做 |
|---|---|---|
| TOP10 Mainline | 確認 caller 拓撲、修改 TOP10 放行前交接與停止證據接線及必要測試；整合雙邊驗收結果 | 修改 ai-core、清正式 marker、部署／補跑 |
| ai-core Mainline | 沿既有 lifecycle 接收並核驗交接／停止證據，維持不確定時保留 root；修改自身 helper 與測試 | 修改 TOP10 caller、替 TOP10 宣告已恢復 |

同一份契約，不建立兩份不相容規格；各 repo 僅自己的 Mainline 安排寫入。先完成契約對齊再實作，版本／欄位／拒絕行為有變更須兩邊同步。未取得接手確認不能把本卡當成已 dispatch。

### 原生 ES 候選：明確分工與先後順序（2026-09-22）

Owner 要求「所以到底是誰要做。你們要不要拆清楚」。本節落實責任與交付分配；不把要求拆分冒稱為實機監聽或系統權限變更核准。Repair 2 成本既有核准保持有效。

**整體交付負責人是 TOP10 Mainline（本 task）**：維護唯一契約、直接協調 ai-core、裁決交回、安排整合與獨立驗證。Owner 不負責在兩個 task 間傳話，也不負責替工程團隊查詢或設計權限方案。

| 工作 ID／負責方 | 具體交付／驗證 | 前置依賴／現在狀態 |
|---|---|---|
| ES-P1：ai-core，離線原型 | 在自身 repo 做合成事件處理與失效測試，涵蓋短命父程序、另 SID、exec 身分變更、事件缺口及尾端不明；提供可重跑命令、原始輸出、版本 digest。對應 A1／A4／A5；不得宣稱已證明實機停止 | 已實作交回並由 TOP10 驗收離線子集；20 項測試及額外 10 個獨立案例通過。沒有產品接線 |
| ES-P2：ai-core，權限與實機方案 | 明列 entitlement／簽署／root／FDA 各自取得方式、已知可用性、確切採集範圍、終止與回收方法、預期成本及不可取得時的 NO-GO；交我彙整成單一具體決策。對應 A2／A7／A8 | 決策材料已透過原 task 交回，摘要見下；有效權限仍 UNKNOWN。未申請權限、未啟動監聽 |
| ES-P3：ai-core，單次原生 ES 實機原型 | 原生 client 與安全合成 fixture，證明放行前 ready、完整 lineage、事件遺失拒絕及終端判定；交可供 TOP10 配對的接口與版本。對應 A1–A8 的平台部分 | 依賴 ES-P1、ES-P2；另須明確實機採集授權與可用權限。未啟動 |
| ES-T1：TOP10 Mainline，本案接線 | 接收 ai-core 通過的接口，修改 TOP10 bootstrap 交接及停止證據接線；核對同一 run／root／程序身分，保留 unknown 時拒絕清理。對應 A1–A8 的 caller 部分 | 依賴 ES-P3 可行證據與 R2-C 單一接口；不先寫假設平台已可用的接線。未啟動 |
| ES-V1：TOP10 Mainline 統籌，兩名獨立 Reviewer 執行 | 同一組雙邊版本完成 A1–A8 實測與兩份獨立 verdict；由我裁決是否允許 TOP10 隔離驗證 | 依賴 ES-P3、ES-T1；沿用已核准 Reviewer 成本。未啟動，不以離線 GREEN 代替整合通過 |

目前可直接完成的工作是分工、接口驗收條件及具體權限方案整理；實作狀態與責任分配分開記錄。最小原型是否進入開發，由本 Mainline 統一呈現範圍；需要 Owner 決定的是新增原型範圍與實際權限／採集，不再詢問誰負責或重問 Repair 2 費用。無新增卡片、常駐系統或第三輪修復；本次純拆分不取代既有產品路徑，退場契約不適用。

交付節點：ES-P1／ES-P2 後先判斷是否值得進 ES-P3；ES-P3 通過才進 TOP10 接線；整合候選凍結後再做 ES-V1。任一 NO-GO 由 ai-core 帶具體缺口交回我裁決，不轉回 Owner 要求代派工。

接手確認：ai-core 原 task `01a0c27e-8abe-7a93-aaf6-69987b51f1dd` 已明確確認承接 ES-P1／P2／P3，承認 TOP10 Mainline 保留整體交付與整合責任。P1／P3 尚未開始；P2 為原評估的具體整理，不是新增實測。交回重點：

- ai-core 準備 Apple 受限 entitlement 申請用途、最小範圍及簽署檢查清單；帳號持有人完成必要申請／同意。現有核准、profile 與簽署身分皆未驗證；不能由 eslogger 的權限推論自製 client 可用。
- 實機僅 collector 單次提權；合成工作保持原使用者。不將 Daily／IDE 整體提權，不裝 setuid、免密 sudo 或 LaunchDaemon。FDA 必須依實際啟動鏈確定 responsible app，由 ai-core 提供精確對象與步驟；本輪未取得同意或測試有效性，SIP 保持不變。
- 擬議採集限單 client、NOTIFY_FORK／EXEC／EXIT；為核驗序號與歸屬，可能接觸同期其他宿主程序的 metadata，不能宣稱 OS 端只看 fixture。先驗序號，再僅保存自有程序必要身分／關係／退出／缺口與 run/root；非自有程序只留必要計數及序號邊界，不保存 argv／env／路徑。
- 首次 live fixture 候選上限為 30 秒、1 MiB／64 檔；仍須 fresh 容量與既有 policy 准入，只能收窄，並非啟動許可。獨立 EOF＋alarm 回收鏈與 unrelated sentinel 先備妥；collector 不得成為唯一回收手段。掉事件、collector 死亡、解析錯誤或超限即永久維持本輪 unknown；完整停止與匯出未證明就保留 root。
- Apple 核准耗時、帳號費用與簽署成本未知，不承諾金額或時程。缺任一必要權限或 ready／事件涵蓋／身分轉換／尾端完整性證據即 NO-GO；不以 eslogger、固定等待或關閉 SIP 替代。

Owner 最新「繼續吧」已准入 ES-P1 離線原型開發；實機 ES-P3 仍需在上述權限與有限採集另行准入後才開始。決策材料由我統一整理，ai-core 不再要求 Owner 代傳話。Repair 2 成本核准未撤回且不重問。

本輪重判為 REPLAN：舊 first-child ACK／kqueue 候選保持淘汰，不重跑失敗方案。新增的必要證據是原生事件模型在合成完整序列、exec 身分轉換及缺口失效時能否維持 A1／A4／A5 的必要條件；這不解決 host 權限或 terminal completeness，不能取得清理許可。沿用原失敗計數，不新增第三輪產品修復；不得由合成 `complete`／EOF／空佇列直接簽發真實停止證明。

ES-P1 接手證據：原 ai-core task 已在本輪直接回覆「已接手 ES-P1，現在進入離線實作與 RED/GREEN」，不啟動 P3／不碰產品清理。TOP10 在交回前鎖定的收件條件與接點核對見 [es-p1-acceptance.md](../evidence/REPAIR-TOP10-AI-CORE-STOP-PROOF-CONTRACT-01/es-p1-acceptance.md)。此時未有測試通過判定。

### ES-P1 收卡（2026-09-22）

ai-core 已正式交回且 Worker 停止寫入；原 task turn `01a0c9a2-1d2c-7bb1-b36b-8681192d1e13` 已 completed。交回 `es-p1-receipt.md` 位於原 ai-core evidence 目錄，本輪實讀 digest `c285889586f5955fea695e11ff0acb50889772cc1b4ad9eee94c538cf1bf44fb`。

- 接受 ES-P1 離線交付：181 行純 Python reducer 與 20 項測試。程式 SHA `29b30384fedd93bf4ab10d5736b8aa63fee6504b72f4fda948050bb1484bd32d`、測試 SHA `98f7f7005f94c7c1db5af7fea4c5c988c27ea83e04adc84c7a5af6c3a61e65cc`。最終交回與 TOP10 重跑版本相同，未重複執行無變更測試。
- TOP10 親讀 RED（1 項正常 assertion failure）及 GREEN，重跑 20 tests OK，另自寫 public API 核對 10 案全通過；原始輸出、重跑腳本、假設及對應條件均在上述 acceptance 文件。不是以對方回報或檔案存在代替驗收，不冒稱兩名 Reviewer。
- 合成事件已能保留父先退的後代與 exec 後的歸屬；序號／綁定等失效永久 unknown。`cleanup_allowed` 固定 false；合成 ready／complete、從 1 起的序號與 opaque token 都不等於原生可信事件或尾端證明。
- 尚缺 ES-P3：Apple entitlement／簽署、root／FDA 有效性、原生 adapter、訂閱／mute ready、初始與尾端完整性實測。離線邏輯通過不解除 TOP10 正式阻擋，也不啟動 Daily、產品接線或兩名整合 Reviewer。
- 後續責任維持 ai-core 做 ES-P3、TOP10 Mainline 統一協調與整合；本輪沒有提出重核 Repair 2 成本、沒有新增第三輪。已有足夠離線證據，不再以追加同類離線測試代替實機能力缺口。

### ES-P3 準備狀態核對（2026-09-23）

ai-core 原 task 主動交接：Owner 在其對話貼出 P1 驗收及 P3 尚需權限／採集授權後指示「繼續」，該 task 已完成本機 codesigning identity 與標準 profile 目錄唯讀核對。TOP10 已親讀交回 `<ai-core-root>/docs/evaluations/REPAIR-TOP10-AI-CORE-STOP-PROOF-CONTRACT-01/es-p3-readiness.md`，SHA-256 `a382d436f6cd176832d598563e711526b584a4ec3704ad9a74cdfebee48d36a2`；未將交回核對冒稱 TOP10 再獨立執行帳號／keychain 查詢。

- 本次 `security find-identity -v -p codesigning` 回報 `0 valid identities found`；兩個標準 profile 目錄 `~/Library/MobileDevice/Provisioning Profiles`、`~/Library/Developer/Xcode/UserData/Provisioning Profiles` 不存在。僅代表本環境可見結果，不能排除其他 keychain、profile 位置或帳號既有核准。
- uid 為 501；clang 可定位，但有效 root／FDA／ES admission 尚未測試。未匯出 key／憑證、不讀 TCC、不執行 `es_new_client`。
- 現在唯一所需 Owner 資訊：是否已有核准的 Endpoint Security entitlement；若已有，提供 profile 位置與簽署所在環境即可，不需密碼、私鑰或憑證內容。若沒有，下一項是帳號持有人是否申請的決策，由 ai-core 準備用途與最小需求，TOP10 統一協調。
- 本輪停止在具體外部前置條件，不追加離線測試、不重跑 P1、不改用 eslogger／關 SIP 繞過。即使簽署配置補齊，也仍須獨立取得有限採集及確切 root／FDA 操作准入，不能自動啟動 P3。

分工不變：ai-core 交回實測準備狀態與單一必要決策，TOP10 Mainline 整合。此步不匯出私鑰、不啟動 client、不提權、不做權限申請或實機採集；不重跑 P1、不重問 Repair 2、不要求 Owner 代傳話。ES-P3 實機階段仍依原准入條件。

## Acceptance／必要行為契約

下列是驗收要求，不預先指定 transport、檔案 schema 或新的管理元件。具體接口由雙邊依既有接縫確認並記錄在本卡 handoff。

1. **綁定本輪身分**：交接與停止證據必須關聯同一 exact owned root、run identity 及可信程序 identity。PID 單獨、路徑字串單獨、過期 receipt 或 child 自述不得作為完整證明。
2. **放行前完成交接**：實際工作不得早於外層確認程序歸屬開始。建立 bootstrap、交接、確認與放行之間，任一側死亡不得留下無歸屬的已執行工作。EOF／逾時／拒絕均不能繼續放行。
3. **覆蓋後續後代**：不只登記第一個 child；須說明並證明工作開始後 fork／另 session 的歸屬完整性。存在未涵蓋後代時維持 BLOCKED，不能用一次 ps 掃描補成完整性。
4. **停止證據獨立可核驗**：正常完成、signal、guard 消失與停損都要核驗；outer exit 0、guard receipt、NOTE_FORK 未見事件、延長 grace，任一單項都不足以解除已知缺口。
5. **清理順序**：完整停止已證明 → 原始證據成功匯出 → exact owned root 清理 → 核對 root 消失與結果。任一步失敗保留必要證據，不能回 PASS 或覆蓋原始錯誤。
6. **不確定時保留**：identity 變更、觀測遺失、query 失敗、部分交接、匯出失敗或未知存活者，沿既有 unknown isolation／recovery 契約保留 root；不得猜測性 kill／delete。

## Acceptance／共同測試矩陣

| ID | 情境 | 必須可觀察的結果 |
|---|---|---|
| A1 | 正常 nested 工作，包含實際 fork／另 session | 完整歸屬與停止證明通過、匯出成功、root 消失；不是以 nonfork 替代 |
| A2 | bootstrap 建立後、交接前、確認後放行前、放行後各點 guard／outer 死亡 | 同步 fixture 精準停在邊界；未交接工作不執行，已執行工作有可核驗歸屬；無法證明停止則 root 保留 |
| A3 | child 延遲／忽略 TERM；SIGTERM、SIGINT、TTL、bytes／files 停損 | 有界收束或明確 BLOCKED；nested child 尚活時不得 cleanup；原始退出原因保留 |
| A4 | 後代再次 fork／另 SID、leader 先退出 | 不把 leader 消失或單一 group 清空當完整停止；證明不足時拒絕清理 |
| A5 | 錯 root／run、舊證據重放、identity 變更、query 失敗 | 精準拒絕，沒有猜測性 kill 或誤清理 |
| A6 | 匯出失敗、部分啟動、cleanup 失敗、重複 signal | 保留唯一原始證據與真實錯誤，符合既有 recovery 契約 |
| A7 | 所有破壞性 fixture 同時存在 unrelated sentinel | sentinel 程序與資料不受影響；fixture 本身有安全回收及無殘留證據 |
| A8 | 既有單 PGID、預設／opt-in、同 repo admission、容量邊界 | 受影響回歸通過；不得把預設 legacy 路徑的既知風險冒稱已修 |

先建立能抓到本次接線缺口的受控 RED，再做最小 GREEN。fixture 必須有自己的安全回收保證，不使用真實 Daily 驗證未證明的 teardown。兩名 Reviewer 不互讀 verdict，獨立執行關鍵成功與失敗路徑；review 必須涵蓋 trap／handler 副作用，不只讀 diff。

## Constraints／邊界

- 沿既有 bootstrap、lifecycle、isolation／recovery 接縫修補；不新增常駐 supervisor、registry、DB、通用 runner 或第二套治理流程。
- 不直接關掉 `start_new_session`、放寬容量／TTL、移除觀測或把 unknown 改成成功來通過驗收。
- 不硬編 TOP10 特例，不清 historical／foreign／ownership 不明的 tmp，不碰瀏覽器、登入資料或其他專案程序。
- 本卡不授權完整 Daily 試跑、production、清 marker、runtime/plist、排程、Gemini 實機、retrain sync、external-review、外送、commit／push／部署。
- 同一失敗鏈 Repair 1 已使用；Repair 2 成本於本輪獲 Owner 核准，不得再次以「等待第二輪核准」阻擋已授權工作。新全域介面、超出既有接縫或額外修復輪次仍須重新裁決；不以換卡名取得默示授權，沿用同類兩次無進展重判及同 blocker 第三次硬停限制。

## Repair 2 執行切片與停止條件

👉 [假設與目標確認] 目標：在原 A1–A8 契約內補齊正常 nested 成功與異常保留路徑；邊界：各 repo 原 Mainline 負責自己的寫入，先證明既有接縫可行，再接線；驗收：同一組實際候選通過 A1–A8 與兩份盲 verdict，最高只到 `SAFE_FOR_TOP10_ISOLATED_VALIDATION`。

Mainline 本輪裁決：`REPLAN`。不再只重跑舊 105 項或補第一 child ACK；下一步直接檢驗「放行後完整後代歸屬是否能在既有接縫成立」。原反例、修復計數與失敗證據全部沿用。

| 階段 | 責任 | 必要交付／通過条件 | 未通過時 |
|---|---|---|---|
| R2-F 可行性 | ai-core Mainline；TOP10 Mainline 提供 caller 拓撲及可受控邊界 | 確認現版 dirty tree／digest，使用有安全回收與 sentinel 的受控反例，提出並驗證可持續涵蓋後續 fork／另 SID／短命中間父程序的接縫；說明觀測遺失如何 fail closed。不先固定 transport/schema | 若必要能力不能在既有接縫成立，保存實測反例、最小必要擴充與 why-not-less，停止產品接線；不自動建 supervisor／registry 或繼續盲試 |
| R2-C 單一接口 | TOP10 與 ai-core Mainline | 依可行性證據確認 identity／放行 ACK／後代完整性／獨立停止核驗／匯出清理順序；候選版本配對。由 TOP10 Mainline 寫回本卡，ai-core 回覆存在自己 evidence 目錄 | 未達共識維持 BLOCKED，不讓兩份規格各自生效 |
| R2-I 最小修補 | 各 repo 自己的 Mainline 安排 | TOP10 放行前交接與停止證據接線；ai-core lifecycle 接收、核驗與清理。先受控接線 RED，再最小 GREEN，保留原始輸出及精確回退 | 禁止用正常工作 exit 0／單一 PGID 消失代替完整停止；不啟動真實 Daily |
| R2-V 配對驗收 | TOP10 Mainline 整合；兩名獨立 Reviewer | 相同實際候選、A1–A8、trap/handler 副作用、sentinel、root／export 前後與安全回收；Reviewer 不互讀 verdict，保留本輪版本 digest | 局部 GREEN 不升整卡 PASS；未解缺口保留 BLOCKED，不自動追加第三輪成本 |

不新增固定 token 或金額預算；成本授權限本表 Repair 2 範圍，不是無限重試。既有對話模型／推理設定保持原值；Reviewer 使用 native subagent，無另開側邊欄 task 的授權或必要性。

目前已知阻塞依 `<ai-core-root>/docs/evaluations/REPAIR-TOP10-AI-CORE-STOP-PROOF-CONTRACT-01/intake.md`：normal-fork leaf 與 guard 正常退出，outer 仍回 2 並保留 root；現有 NOTE_FORK 不提供 child PID，不能以 first-child 登記補成完整後代證明。這是待解能力缺口，不能據此宣稱所有 macOS 方案皆不可能。

### 派工與寫入邊界

- TOP10 Mainline：本 task `01a0c81d-41df-7210-89a2-5e7c55127817`，保留 TOP10 開發與整合責任，不轉交專案 Mainline。
- ai-core 原接手 task：`01a0c27e-8abe-7a93-aaf6-69987b51f1dd`（「拉取並整合最新版本」），只承接 ai-core 端 R2-F 與後續條件成立的自身修補；不代寫 TOP10。
- TOP10 既有未提交 Daily／Gemini candidate、tests 與 evidence 保留，不 reset、不捲入接線修補。
- 本卡由 TOP10 Mainline 單一寫入；ai-core 在自身既有 evidence 目錄交回可行性及接口建議。dispatch 工具成功只表示訊息已送達，接手與驗證結果另以實際回覆為準。
- 2026-09-22 派工紀錄：`send_message_to_thread` 已成功傳送原 task；`wait_threads` 查核為 `active`，turn=`01a0c914-4cfe-7bb0-9b37-6c7b2bd4c412`、`inProgress`。目前尚無本輪可行性 verdict，不宣稱已接通或通過；沒有新建側邊欄 task。
- 本輪卡片驗證：實體檔存在，`git diff --no-index --check /dev/null <card>` 與 `git diff --check` 均通過。未修改產品或執行 workload。

## R2-F 收卡與 Mainline 裁決（2026-09-22）

👉 [假設與目標確認] 目標：核對 ai-core 凍結交回並收斂唯一卡狀態；邊界：只讀 source digest／原始證據、更新本卡，不重跑 fixture 或接線；驗收：明確區分反例成立、產品驗收及下一個 scope 決策。

**裁決：接受 R2-F 的有界反例與能力缺口；停止原候選接線，不進 R2-C／I／V。** 已核准的 Repair 2 成本維持生效，下一個等待條件不是再次成本核准。本輪沒有產品 GREEN，也不自動追加第三輪。

交回：`<ai-core-root>/docs/evaluations/REPAIR-TOP10-AI-CORE-STOP-PROOF-CONTRACT-01/r2-decision.md`。同目錄保存 `r2-feasibility-fixture.md`、`r2-feasibility-fixture.py`、`r2-fixture-final.stdout.jsonl`、`r2-fixture-final.stderr.log`、`r2-exact-audit.jsonl`。

### TOP10 收卡核對

- 實際讀取 decision／fixture 報告／final raw／exact audit；重新算 fixture 與兩 repo 產品 digest。TOP10 `app/storage_safety.py` 與 ai-core helper 仍分別等於接回基線 `7a74c41b…`／`0a264207…`，Repair 1 成果沒有被本輪改寫。
- 7 項唯讀 JSON 斷言均通過：正負投影相同、PPID=1 的 live leaf 未列入候選、product_pass=false、兩案 root 回收且 sentinel 保留、8 個原 identities 在 audit absent／未送 signal、2 個 exact paths absent／audit 未刪除、stderr 空白。這是原始紀錄一致性核對，未重新查舊 PID、未重跑實驗，不是第二份獨立 Reviewer verdict。
- 負向 middle=48943 已 reap，leaf=48944 在 snapshot 時仍活、PGID=SID=48944、PPID=1；已知 first child 先做 native identity／armed／ACK，仍未取得完整後代列表。正負候選都只見一筆 NOTE_FORK、data=0。
- 投影比較只針對 first-child ACK＋既有 NOTE_FORK drain＋known-parent/group 瞬時查詢，且對角色／PID／start-time 正規化；當時 guard 仍活。不能擴張成所有 macOS 方法不可能，也不是最終 cleanup certificate。
- fixture 的 oracle 與 candidate 分離；leaf 經 EOF 後取得 native EXIT，回收用 fixture 自有停止證據。這不能挪為產品已有同等歸屬或清理能力。observer close 僅驗證 `require_no_forks()` 以 ValueError 拒絕，未驗 command_run／isolation 的整鏈分類。
- fresh Foundation admission、1 MiB／64 files／60 秒及 sentinel 證據在 raw；未執行現版 Daily 或雙邊配對候選。A1 未達，A2–A8 新候選整合驗收未啟動。

| 凍結來源 | SHA-256 |
|---|---|
| `r2-feasibility-fixture.py` | `ea4285289b29df2077e6757506d2a5053049b8a5b53add501fd4839ee0b0c273` |
| `r2-decision.md` | `a7f11b9bf5e1cbf1d4050142a0a15aec4e137b5d9ad5da60cad06f78862c6a6a` |
| `r2-fixture-final.stdout.jsonl` | `7faedeecbc210b5a4e00281f8d842199aad17d5fe1ec4070343c924483995277` |
| `r2-exact-audit.jsonl` | `8c1ea4332598f672fc6dbe6c537611039f4e90a37c043aa18d118b4502d0a357` |

### 後續 scope 與准入狀態

最小能力缺口：放行前建立本輪可獨立核驗、包含事件遺失辨識的完整 fork/spawn/exit lineage；或能證明所有未來 spawn 都不可繞過受控入口。TOP10 caller／依賴目前不滿足後者；只加 ACK、快 polling、grace 或 receipt 不能補足反例缺少的資訊。

| 候選方向 | 第一階段的有界範圍 | 交付／停止條件 |
|---|---|---|
| 執行拓撲可控化研究（唯讀已交回） | ai-core 回報 Owner 在該原對話確認四步唯讀方案後指示「繼續 吧。最新開發流程。節省模式」；僅准入第一方向唯讀評估，不含修補／第三輪／平台研究 | 已交付下節評估：不支持只重包入口／設定就取得完整程序控制；不進統一入口改寫 |
| 平台完整追蹤研究（本輪唯讀准入） | Owner 在停止回報後明確指示「繼續啊。不然在幹嘛」；承接唯一剩餘候選，唯讀比較完整 lineage／漏事件偵測、現成系統工具及其權限／接入成本。不安裝、不授權 entitlement/FDA、不啟動事件監聽或建立 client／常駐層 | ai-core 查平台來源與能力；TOP10 Mainline 查現有主機工具／本案需求適配，完成具體可行路徑或 NO-GO 與最小必要範圍。研究不升為 runtime PASS，不重問 Repair 2 成本 |

上述研究不是自動並行支線；本輪第二方向來自 Owner 最新明確續做指示。本卡安全判定仍為 BLOCKED，production／marker／runtime／plist／排程／Gemini／外送／commit／push／部署限制不變。

### 執行拓撲唯讀評估收卡（2026-09-22）

交回：`<ai-core-root>/docs/evaluations/REPAIR-TOP10-AI-CORE-STOP-PROOF-CONTRACT-01/topology-readonly-assessment.md`，本次實讀 SHA-256：`7b11a1721aa3d4f2870c4d160c1a0a0f048f3368ae5eef7d83f5a96301a5e185`。

- TOP10 Mainline 本輪只核對評估全文、工作樹與產品 digest，記錄交回；未派代理／Reviewer、未執行 fixture／Daily、未修改產品。ai-core 回報前輪五檔 digest 未變；本次獨立核對 helper、TOP10 storage_safety、execution.py、run_automation.py 四檔與交回值一致，未把對方五檔複核冒稱為本輪自行重驗。
- 收卡判定：現有主要命令已集中 `execute_command`；再包入口只能管已知命令，不能強制 dependency／native spawn 經同一接點。原 R2-F 的完整性缺口仍存在，不進統一入口改寫。
- 評估明確區分設定與程序控制：`JOBLIB_TEMP_FOLDER` 只管暫存位置；local_safe 的 thread 限制不套用 standard validation；joblib 多程序設定不是 OS 級限制，physical-core 探測另有 sysctl subprocess 能力。這些是來源能力判讀，沒有宣稱現版 Daily 實際執行該分支；import 或 rg 未命中也不當 runtime 證據。
- 本輪沒有新的可配對候選／runtime PASS；不降低 A1–A8、不再重試首 child ACK、不新增第三輪，不重問已成立的 Repair 2 成本。
- 該次收卡時唯一剩餘研究候選為有界平台唯讀評估，當時未准入，兩邊停止。Owner 之後最新續做指示已准入上表唯讀評估；原型、權限變更與 production 限制仍不因此解除。

### 平台唯讀評估收卡（2026-09-22）

交回：`<ai-core-root>/docs/evaluations/REPAIR-TOP10-AI-CORE-STOP-PROOF-CONTRACT-01/platform-readonly-assessment.md`；TOP10 本次實讀 SHA-256：`83bc35badf4757062f2bfd6f0e953107a5c650c5898f379544d43f5590e8768a`。本機接入核對：[platform-host-readiness.md](../evidence/REPAIR-TOP10-AI-CORE-STOP-PROOF-CONTRACT-01/platform-host-readiness.md)。以上取代前表的進行中狀態。

- 根因判定：內層正常退出不等於後代全部停止。既有觀測可以漏掉短命中間程序所生、已換 SID 並仍存活的後代；拒絕清理符合原契約。不是再延長 timeout、補 ACK 或重跑相同測試就能補回缺失的歸屬資訊。
- 現成工具判定：本機 `eslogger` 存在，但官方 man 明示其非穩定應用介面，且會抑制同 process group 事件，不能直接採為自動清理證明。DTrace 本輪亦未找到足以成立原契約的完整證據；不因此推論所有平台方案都不可能。
- 唯一保留候選：按需、單次執行的原生 Endpoint Security notify-only client。官方 API 支持應用程式形態，不必先建常駐 daemon／system extension／registry。仍須受限 entitlement、簽署、root、正確 responsible process 的 FDA；本機有效可用性為 UNKNOWN，沒有啟動 client 測試。
- 事件 API 只是必要材料：放行前完成訂閱與 mute／版本核對；fork 完整歸屬、exec 的 pidversion 轉換、exit 及序號遺失檢查皆須驗證。連續序號不證明沒有被 mute／未訂閱的事件，也不單獨證明尾端已收齊。掉事件、重啟、解析失敗或尾端不明一律保留 root，不能以 EOF／空佇列／固定等待授權清理。

最小下一步已收斂為兩段原型候選，沒有開新卡或重置修復次數：

| 階段 | 最小交付與驗收 | 邊界／停止條件 |
|---|---|---|
| 離線事件歸約與失效規則 | 用合成事件重現短命父程序、換 SID、exec 身分轉換、序號缺口、重啟、解析失敗及尾端不明；失效案例一律不得簽發清理許可 | 不需 OS 權限，不能算真實 host PASS；本輪只有方案，未實作 |
| 單次合成原生 ES fixture | 先具備並確認必要權限，再證明 ready 後放行、完整後代事件及可靠終端判定；正反案例保留原始證據、exact-owned-root 與 sentinel | 有限事件採集及權限變更須明確准入；不跑 Daily、不新增常駐管理；任一完整性條件無法證明即 NO-GO |

本輪完成的是平台可行性研究，不是產品修復。ai-core 負責平台候選；TOP10 Mainline 負責 caller 接線與整合；有可配對版本後才執行原定兩名獨立驗證。未改產品程式、未新增第三輪、未解除 production 停損。

## Handoff／接手與交回

1. 雙邊先確認最小接口：identity 綁定、歸屬完整性、放行確認、停止核驗、錯誤／中斷行為與版本配對。這是目前 blocker，不是再跑一次既有 105 項測試。
2. 各自核對 AGENTS、工作樹與 CodeGraph；保留目前未提交成果，不 reset 或覆盖對方檔案。
3. 各 repo 在既有邊界內實作與測試；整合 fixture 必須使用同一組實際候選版本，不能只證明兩邊各自 mock 通過。
4. 交回：兩邊版本／dirty diff digest、接口說明、逐項 A1–A8 verdict、RED/GREEN 原始輸出、PID／PGID／SID 與 root 前後證據、sentinel、匯出及安全回收結果、兩份獨立 review、精確回退方式。
5. 未完成正常 nested 成功與交接競態驗證，整卡維持 `BLOCKED_WITH_EVIDENCE`。全部完成才可判 `SAFE_FOR_TOP10_ISOLATED_VALIDATION`，只解除隔離入口安全 blocker，不代表 TOP10 恢復或取得試跑／上線授權。

候選分歧：若現有接縫無法提供完整後代證明，交回已測反例、最小必要擴充與為何更小方案不足；保持阻擋，不以「先跑再觀察」替代。

## Evidence refs／必讀

- `<ai-core-root>/docs/evaluations/REPAIR-AI-CORE-NESTED-SANDBOX-TEARDOWN-01/handoff.md`（以此最終交回為準；舊 result 不代表最終批准）
- 同目錄 `repair-1.md`、`repair-1-sha256.txt`、`review-a-rereview.md`、`review-b-rereview.md`。
- `<top10-root>/docs/tasks/2026-09-22_REPAIR-AI-CORE-NESTED-SANDBOX-TEARDOWN-01.md`
- `<top10-root>/docs/tasks/2026-09-22_REPAIR-TOP10-DAILY-PROVIDER-01.md`
- `<top10-root>/docs/evidence/REPAIR-TOP10-DAILY-PROVIDER-01/report.md`

TOP10 後續仍需 fresh Foundation admission、有效容量預算、兩輪完整隔離 ETL 及原有恢復條件。現有 Daily／Gemini local candidate、未解整組測試非穩定結果與 production 停損狀態均不被本卡覆蓋。

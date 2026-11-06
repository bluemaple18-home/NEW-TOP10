# RECOVER-TOP10-PRODUCTION-DATA-BACKFILL-30（2026-11-03）

> **狀態：11/03真Daily已來源停損；正式仍10/02；原22:00單次已依追加條款PAUSED待Owner覆核；Production NO_GO。** 約983秒後TPEX reset＋TWSE/TPEX timeout累計3次觸發原連線上限，程序群靜止、三表/快照/全部保護檔身份不變；FinMind data0、user_info1。不是容量守衛；未進重計算，不冒稱記憶體或管線PASS。未重跑、未加額度、未新開輪次，已撤回memory NO_GO未恢復。詳原收據最新立即11/03節。


卡片類型｜派工對象：Recover（正式資料回補）／Worker（strict）

## Owner 授權（2026-11-03 互動對話明示）

**只解資料層：** 授權把正式 runtime（bbd32b4）資料庫從 2026-09-30 補到最新交易日，
**寫正式資料**。發布、送件、旗標、排程**全部維持凍結**。此授權僅限資料寫入，
不含任何對外動作或上線。

### 第 3 輪記憶體修補例外授權（2026-11-03 Owner 互動對話明示）

model-role-routing 的修補絕對上限為 2，前兩輪已用罄；Owner 明示**核准第 3 輪例外**，
僅限以下範圍：

- 僅套用單檔候選 patch `r30-20261103-evidence/memory-repair/round2/indicator-lifetime.proposed.patch`
  （`app/pipeline/indicator_stage.py`）：提前把 `tech_missing` 取成純數值、`del` 舊計算器與中間表、
  不再把整張 `tech_ind`／`vol_ind` 存入 context。**不改任何指標公式、不改守衛、不放寬 RSS 上限。**
- CC 已獨立複核：全專案 `app/`／`scripts/` 無任何下游讀 `context['tech_ind']`／`['vol_ind']`，
  移除為純釋放死記憶體、非行為改變。
- 核准**最多一次**全量離線複測（拼接既有 10/02＋11/02 隔離資料，零新增 API，大輸出至 /dev/null）。
- 複測＋獨立 Review 通過後，才沿**已核准的 400 次上限**一次補到 11/02；不新增額度、不改凍結設定。
- 任一環節失敗即停、不自動重試、不再加輪次；旗標／標記／lock／launchctl 維持 NO_GO 凍結。

## Objective

正式 runtime 資料停在 **2026-09-30**；今天 2026-11-03。把 `data/clean/` 的
features／events／universe 從 9/30 的次一交易日補到最新有效交易日，使正式資料接回最新。

- 目標路徑：`/Volumes/VibeCode/Development/TOP10-Runtimes/TOP10-runtime-automation-bbd32b4/data/`
- 交易日曆以 TWSE `exchangeReport/FMTQIK` 為準；不自行猜非交易日。

## Scope

- 只跑 **ETL／資料階段**（`app.pipeline_cli run`，`--data-dir` 指向上述正式 data 目錄），
  **不跑發布鏈**、不產生 Clawd 訊息、不送任何封包。
- 逐交易日回補，依 FinMind 600／滾動小時額度節流：每日 400 data 呼叫、預檢 401；
  HTTP 402 即停並回報。沿用卡 09 的滾動等待節奏。
- 每日寫逐日收據：開跑前額度、容量（28 GB 線）、guard preflight、覆蓋率、exit code。
- 子程序 stdout／stderr 落檔且非空；每日必寫 finished 記錄（含 exit code）；
  控制器例外也要落檔、附 traceback。

## 停手鐵律（任一命中即停、回報、不重試）

- 任一日覆蓋率、來源、容量或保護檔檢查失敗。
- FinMind 402／額度不足／連線失敗滿 3 次。
- 容量 guard triggered（跨 28 GB 線或 RSS 守衛）→ 乾淨停跑。

## 禁止（維持 NO_GO 姿態）

- **不發布、不送件**：Discord、ops channel、Chrome ChatGPT／Gemini reviewer 一律 0 次（含測試）。
- **不翻旗標**：`MIGRATION-NO-GO.json` 維持 `production=NO_GO`、`workload_allowed=false`。
- **不碰停跑標記**：正式與候選 `logs/storage_safety/restart_denied/*.json` 全部不新增、不改、不清
  （daily 等維持 75 停住）。
- 不碰 `logs/daily_publish.lock`；不 `launchctl load/unload/reload/kickstart`；不切換載入設定；
  不 commit／push／部署。
- FinMind token 絕不落日誌／收據／git／對話，只報 has-token 布林與長度。
- 只允許 FinMind／TWSE／TPEX／TAIFEX 唯讀取得；允許清單外入口即停。

## Acceptance

- 正式 `features/events/universe` 最新日 = 最新有效交易日；逐日覆蓋率齊備、FinMind 覆蓋 complete。
- 每日容量 guard reasons 為空（或乾淨停跑並明確回報）。
- 旗標、停跑標記、lock 的開工前後 SHA／大小／mtime 全數不變（附對照）。
- 對外送出 0 次；`git diff --check` 通過。
- 若中途停手：明寫停在哪一天、原因、已補到哪一天，不宣稱整段完成。

## Evidence

`<repo-root>/docs/evidence/TOP10-DAILY-RESEARCH-RECOVERY-20261027/ACCEPTANCE-RECOVER-TOP10-PRODUCTION-DATA-BACKFILL-30.md`

## 2026-11-03 記憶體修補續行（Owner 互動授權）

- Owner 原話：「先查清楚記憶體為什麼超限，把問題修好再補到 11/02，不要放寬守衛，發布跟旗標繼續凍結，結果寫回原收據」。這是已知失敗後的新修補與資料續行授權，不是盲重試。
- 目標：定位並消除 ETL 不必要的中間資料持有／複製，保留所有數值、訊號、過濾規則及輸出 schema；不做文案或新功能。先以已有資料離線重現、量測峰值，驗輸出等價及守衛內完成，再續補明確截止日 2026-11-02。
- strict／共享 checkout sequential single writer。Worker 實作時 Mainline 不寫檔；Review 與實作責任分離。此 runtime 無規則建議的 GPT-5.5 override，沿 runtime 預設繼承目前模型，不自行降級。
- 實作可寫：`app/pipeline/indicator_stage.py`、`app/risk_filter.py` 及直接必要的 pipeline 階段／記憶體回歸測試；僅限證實的資料持有／複製缺陷。其他既存 dirty 內容不得動。先提交可驗證根因與最小修補，Mainline 核實 diff 後執行正式資料續行。
- 離線只讀既有失敗／已接受資料，不讀 .env、不打 API、不跑發布、送件或任何 launchctl 命令。輸出限定 `r30-20261103-evidence/memory-repair/`；保留原始失敗。RSS 超限即終止本次自有程序；不為製造 RED 施壓主機。
- 回補全部保護檔沿原 baseline；FinMind 400／每輪、600／滾動小時與失敗停損不變。正式資料續行前重新記錄受測 SHA／容量／額度／驗收；每個目標交易日均須覆蓋與來源證據，不把單一命令成功當全段 PASS。
- Evidence：沿原收據，追加本次根因、測試、受測版本、真實回補及 Mainline 接受結論；不另建功能線或 AI Core 施工卡。

## 額外一輪明示核准（2026-11-03）

Owner答覆：**「核准額外修補、一次複測及通過後一次補完」**；授權綁定`memory-repair/continuation-proposal.json`的具體內容，見`memory-repair/round2/owner-approval.json`。

- 已核准Repair generation 2、最多一次576,608列目標全量離線複測；小型數值、事件、排序、index與輸入隔離精確等價先通過。先前第三次RSS停損仍保留為失敗，這是新明示例外，不自行重置計數。
- 此輪產品修補只限`app/event_detector.py`建構資料工作表及相應回歸測試；不改事件公式、篩選或guard/policy。共享checkout仍sequential single writer，原生Worker及獨立Review分離；不另開task/worktree。
- 全量離線與獨立Review通過後，原逐日重複ETL改為**一次區間ETL補到2026-11-02、最多新增400次FinMind data**；保留2025-08-06歷史，按官方20交易日逐日驗覆蓋／雙市場及籌碼來源。600／滾動小時、401預檢、402／三連線失敗／資料／容量／保護檔不符即停，不自動重試。
- 正式features/events歷史交易鍵須保留。Universe依原目標日門檻重算，股票池可合法變動；以既有演算法等價及逐日覆蓋驗證，不以股票池一定逐日增加作錯誤閘門。
- 發布、Gemini／Discord／ops／Chrome reviewer（含測試）、旗標、所有停跑標記、lock、launchctl、排程、commit/push/deploy全部凍結。
- 全部版本、測試、資源實測、實際補完結果與Mainline結論繼續寫回原收據。

## 2026-11-03 復工優先：改為「只往前接」（Owner 互動授權）

Owner 明示目標：**趕快讓專案可以復工；其他歷史資料是訓練用途，可以之後再補。**
因此放棄「整段 2025-08-06 重建」路線（`ONE_CONTIGUOUS_RANGE`），改為增量往前接。

- **起點＝已接受的 10/01 基線**（features／events／universe 現狀，已驗證、含乾淨的 9/15），
  只抓 **2026-10-02 → 最新有效交易日** 逐日 append，**不重抓、不重建任何 10/01 以前的歷史**。
- 9/15 TWSE non-json 掉 1071 鍵的問題**不在本任務處理範圍**：那是重抓歷史才會踩到的，
  只往前接就完全不碰它。此類歷史來源缺口列為**獨立、非阻斷的訓練資料補洞**，日後另開小卡，
  不得因此擋住復工。
- 記憶體第 3 輪 `indicator-lifetime` patch 已 **ACCEPTED**，作為本次 ETL 的運行版本。
- 其餘凍結邊界完全不變：資料層 only、`production=NO_GO`、不發布／送件／翻旗標／碰停跑標記／
  lock／launchctl／commit／push／deploy。FinMind 只讀、600／滾動小時節流、token 不落檔。

### 本輪 Acceptance（取代「補到 11/02 才算完成」的全有全無判準）

- `features/events/universe` 最新日 = 最新有效交易日；**10/01 以前歷史逐檔身份不變**（append 不改歷史）。
- 10/02→最新每日覆蓋與來源證據齊備；任一日覆蓋／來源／容量／保護檔失敗即停、明寫停在哪天。
- 旗標、停跑標記、lock 開工前後 SHA／大小／mtime 全不變；對外送出 0 次；`git diff --check` 通過。
- 若上游某一「新」交易日也回 non-json：該日停、保全、回報；不自動重試、不追加額度、不碰凍結。

## 2026-11-03 Owner續行：合法融資N/A不得阻斷整批

- Owner本輪明示先查清7610合法N/A或缺資料，修好後自主接到最新交易日；取代上輪來源拒收後不得續行的等待狀態。不是既有記憶體第4輪，不重試原失敗版本。
- 以TWSE同日TWT93U明確Y（未取得信用交易資格）及同日非空完整MI_MARGN無該股作EOD日報資格證據；未知、錯日、空報表不豁免。合法N/A明標並保留NaN/False與股票，不填0，不把借券當融資。
- 指標公式、容量4GiB／boot raw28GB／project6GiB與600 rolling hour不動；修補後一次新窗口最多400次data。新日行情沿上輪已鎖定20檔快照，不重抓舊行情。金融回應留存，以免失敗丟掉來源證據。
- 11/03官方信用與融資日報尚未發布時標WAIT_SOURCE_PUBLICATION，不當成N/A；由本任務自動等來源發布，完成新證據驗真再續行，無需Owner再次推進。發布與所有控制設定持續NO_GO凍結，結果沿原收據。

## 2026-11-04 Mainline 裁決：停止第二套管線，回到卡 09 既有逐日 loop（CC 唯讀核對後裁定）

**裁決：第 4 輪 REJECTED。放棄 `app/pipeline/append_forward.py` 路線。**

CC 唯讀核對確認：

- `app/pipeline/append_forward.py`（618 行）為**本輪新造模組**，不在原始碼 manifest；並已改動
  `app/pipeline_cli.py` 接入它。這是 RULESET 明文禁止的「第二套 writer／runtime」，且非 measured minimum。
- **卡 09 六天逐日回補完全沒有用它**，用的是既有入口 `scripts/run_automation.py`
  ＋環境變數 `TOP10_BACKFILL=1`、`TOP10_RUN_DATE=<該日>`，一天一輪，六天全乾淨。
- 該機制現仍在原始碼且接真入口（`run_automation.py:266 / 1921`、`market_context_fetcher.py:808`）。

因此記憶體第 1–3 輪 RSS 天花板、9/15 重抓、以及「接完一天不能續」的 bug，都是**新管線特有**的；
卡 09 的逐日 loop 各日獨立調用，天生可續、不做全段重建、不踩那些問題。

**本任務改以下列既有機制執行，不寫任何新碼：**

- 以 `run_automation.py`＋`TOP10_BACKFILL=1 TOP10_RUN_DATE=<該日>`，對 **2026-10-02 → 最新有效交易日**
  逐日各跑一輪，寫入正式 `bbd32b4/data/`。沿卡 09 的逐日驗收、容量看守與 FinMind 600／滾動小時節流。
- **還原本輪新增的產品碼變更**：`app/pipeline/append_forward.py` 與 `app/pipeline_cli.py` 對它的接入，
  均未 commit，一併丟棄（保留在 round3/round4 證據目錄供存查，不留在產品碼）。
- 記憶體第 3 輪 `indicator-lifetime` patch **非逐日路徑所需**（逐日不做全段重建、不觸 RSS 天花板）；
  可留作安全餘裕，但不是完成本任務的前提。
- 9/15 等歷史來源缺口維持「不處理、日後另開訓練資料補洞小卡」。逐日 append 不重抓歷史，本就不碰。
- 凍結邊界一字不改：資料層 only、`production=NO_GO`、不發布／送件／翻旗標／碰停跑標記／lock／launchctl／
  commit／push／deploy；FinMind 只讀、token 不落檔。

**Acceptance 不變**（見「只往前接」段）：最新日 = 最新交易日；10/01 以前歷史逐檔身份不變；
每日覆蓋與來源證據齊備；旗標／標記／lock SHA 不變；對外 0 次；`git diff --check` 通過。
任一「新」交易日來源 non-json：該日停、保全、回報，不自動重試、不追加額度、不碰凍結。

## 2026-11-04 Worker執行結果：退場完成；原入口與歷史契約有實證衝突

- 已依上節裁決封存移除append模組、CLI接入及兩個專用測試；保留既有Daily必需的FinMind統計接點與既有記憶體安全修補。封存及受測SHA見原收據本日節。
- 既有backfill回歸22 passed；獨立Review：退場PASS、正式原入口BLOCKED。
- **不能執行上節所稱「逐日append」：** 原入口10/02實際仍抓2025/08/08～2026/10/02，含9/15；Event/Filter直接覆寫三份parquet，兩列fixture確認舊列消失。正式現有08/06起，features/events各3,761列、universe1,942列早於窗口，直接跑會刪除歷史。縮成只抓單日也會覆寫；延長窗口則重抓歷史。上節對「原逐日loop不重抓、不重建」的敘述與source不符，卡09候選6/6不證明正式歷史保留。
- 本輪不再造writer、不啟動第4輪、不降低守衛；因「不寫新碼」及歷史不變條款，停在正式寫入之前。60保護檔/5 plist/6 artifact roots/9 runtime inputs與正式三份身份皆不變，新增API/正式寫入/外送/launchctl均0，正式仍10/02。
- Mainline **PARTIAL ACCEPT（退場及回歸）／BLOCKED_EXISTING_ENTRY_CONTRACT（資料續接）／Production NO_GO**。下一步須先解除既有ETL整檔覆寫與歷史不變的契約矛盾，未自行擴大本卡施工範圍。版本、測試、Review、結論寫在同一原收據，未另開功能卡。

## 2026-11-04 Mainline 最終裁決：復工優先，接受歷史裁切，歷史洞另開研究卡（Owner 互動授權）

**CC 複核 Worker 本輪診斷為正確：**

- `config/automation.yaml:18`：`pipeline_lookback_days: 420` 是 daily ETL 的固定滾動窗口。
- `app/automation/pipeline_policy.py:60`：`start_date = end_date - 420 days`。
- `app/pipeline/event_stage.py:22,32`、`filter_stage.py:27`、`event_detector.py:269`：
  features／events／universe 全部以 `to_parquet(path, index=False)` 整檔覆寫；pipeline 內部無「讀既有
  parquet 再 merge 歷史」邏輯。
- 結論：任何對正式資料的 Daily 入口執行，都會把 `(run_date - 420)` 之前的歷史從 parquet 中削除。
  卡 09 六天通過只因寫到空的 isolated runtime；不構成「正式歷史保留」證據。前述「2026-11-04 Mainline 裁決」
  一節對既有 Daily 入口的描述錯誤，本節為最新裁決。

**Owner 原則明示（2026-11-04 互動對話）：**
> 先讓原本功能運行,研究後續打通;歷史資料是訓練用途,可以之後補上。

**裁決：採選項 D。不寫新碼、不改 config、不改守衛。**

- 用 `scripts/run_automation.py`＋`TOP10_BACKFILL=1 TOP10_RUN_DATE=2026-11-04` 跑**單日** Daily
  一次，寫入正式 `bbd32b4/data/`。這是卡 09 已實測可跑的既有入口。
- **跑之前先強制備份**：把正式 `bbd32b4/data/clean/{features,events,universe}.parquet` 的當前身份
  （含完整 2025-08-06 → 2026-10-01 歷史）另存一份不可覆寫的快照到
  `docs/evidence/.../r30-20261103-evidence/pre-daily-run-20261104-snapshot/`，附 SHA-256／bytes／mtime 證據。
  這份快照是後續歷史補洞工作的唯一來源,不能動。
- **接受的代價（事先明寫、不事後找理由）：**
  1. parquet 檔案內容會變成 `2025-09-10 → 2026-11-04` 的 420 天滾動窗口；
     **2025-08-06 → 2025-09-09 約 35 天歷史會從 parquet 掉出**（由上段備份快照保全）。
  2. **2026-10-02 → 2026-11-03 共 19 個交易日**在本卡**不處理**，parquet 中會缺這段。
  3. 以上共約 54 日歷史缺口，歸入另開的訓練資料補洞研究卡（非阻斷復工）。
- 9/15 TWSE non-json 若再發生：該日停、保全、回報；維持停手鐵律。
- FinMind 預估 400 次／單日 Daily；與 600／滾動小時額度不衝突，歷史補洞工作日後另排時段跑。
- 凍結邊界完全不變：`production=NO_GO`、`workload_allowed=false`；不發布、不送件、Discord／ops／Chrome
  reviewer／Gemini 含測試 **0**；不翻旗標、不碰 restart_denied markers、不碰 `logs/daily_publish.lock`、
  不 `launchctl load/unload/reload/kickstart`、不切換載入設定、不 commit／push／deploy。
  `TOP10_BACKFILL=1` 在 `scripts/send_clawd_publish_message.py:34` 與 `scripts/send_top10_ops_report.py:59`
  確認會關掉實際送件；旁證再加卡的禁止條款作雙保險。
- Daily 入口由 launchctl 排程者仍帶 restart_denied marker（exit 75）；本輪由 Worker 以 CLI
  手動呼叫 `run_automation.py`，不走 launchctl、不清任何 marker。

### 本輪 Acceptance（取代先前所有 Acceptance 段）

- `features/events/universe` 最新日 = **2026-11-04**；每日覆蓋／來源證據齊備；單日 exit 0。
- 容量 guard reasons 為空（或乾淨停跑並明確回報）。
- `MIGRATION-NO-GO.json`、所有 `logs/storage_safety/restart_denied/*.json`、`logs/daily_publish.lock`、
  launchctl plist、6 roots artifacts、60 保護檔、5 plist 開工前後 SHA／bytes／mtime **全數不變**（附對照）。
- `pre-daily-run-20261104-snapshot/` 已寫入並通過 SHA 複核；三檔身份與開工前正式 parquet 完全一致。
- 對外送出 **0 次**（Discord／ops／Chrome reviewer／Gemini 含測試）；`git diff --check` 通過。
- 若 11/04 來源 non-json：該日停、保全、回報；不自動重試、不追加額度、不碰凍結。

### 本輪**不做**（明列）

- 不補 2026-10-02 → 2026-11-03 的 19 日資料。
- 不補 2025-08-06 → 2025-09-09 的 35 日歷史。
- 不寫任何新 writer／merger／helper。
- 不改任何 config。
- 不翻 `production` 旗標；不清 restart_denied；不碰 launchctl。

歷史補洞（54 日）另開 `BACKFILL-TRAINING-DATA-HISTORY-GAP` 研究卡處理，與本卡解耦。

## 2026-11-04 Worker：最終裁決D準備完成，22:00本聊天單次續工

- 舊歷史保留blocker已隨Owner接受裁切而解除，不再用其阻斷本輪；沒有重啟append管線/第4輪修補。
- 指定pre-daily-run-20261104-snapshot三份現況備份已PASS，實際含至10/02；SHA/bytes/mtime一致，0444＋UF_IMMUTABLE不可改，manifest亦封存。
- 原容量前檢reasons空、boot raw38,928,867,328 B；原4GiB與28GB線不變，晚間必須重驗。
- 沿卡09的實體source副本準備原CLI，756檔與現版SHA全符，data連正式、artifacts留證據，不改code/config/helper。真實唯讀載入與獨立限域Review PASS；不冒稱完整Daily/容量PASS。
- 11/04 10:42官方TWSE只回71B JSON/沒有符合資料；來源未ready，Daily0、FinMind0，唯一完整輪未耗。
- Owner明示核准今晚22:00本聊天單次續工；原生COUNT1已建立，id=30-11-04-22-00-daily。只重驗來源/快照/守衛後跑既有Daily一次；未發布/non-json就停、保全、不重試、不追加額度。這是本聊天接續，不動TOP10 launchctl/排程/markers/旗標。
- 正式三份仍10/02，60保護檔/5plist/9 inputs及6原artifact roots均不變；另已補齊6 roots全56,611檔的pre-Daily身份基線供晚間逐檔比較。版本、Review、測試/量測與Mainline PARTIAL ACCEPT（準備）／WAIT_SOURCE_PUBLICATION（實跑待驗）／Production NO_GO皆在原收據。卡30整體尚未完成。

## 2026-11-04 Owner加驗：現有資料零API跑現版Daily——限界PASS

- Owner要求不要等晚上才發現主流程問題；已另用既有11/02全420天、533,273列取數後28欄，原Runner與全部原enabled Daily步驟實跑一次，不裁切config、不改產品碼/guard、正式區唯讀。
- ETL計算、資料驗證、排名與後續報告/草稿真實執行，66.02秒exit0。features/events各533,273列、universe282,132列均與同日基準值/型別/順序exact，Top10順序與final_score exact，9份必要產物確為本次生成。
- Fetch只重放已標準化資料；T86/market_context只重用成品，producer/parser/即時額度未驗。FinMind400/400/0是歷史邏輯覆蓋，本次物理API0、quota欄null，狀態OFFLINE_CACHE_REPLAY。原可選overlay缺history的FAILED/WARN不計PASS；preview未測，營收只驗missing-source。
- 原4GiB RSS守衛未觸發，treepeak4,086,005,760B、self HWM4,041,244,672B，僅餘約199MiB；不能替代晚間含SDK/真取數的容量驗收。原生隔離封網路及正式寫入，kernel探針/14子程序hook/程序群靜止證據完整。
- 6 roots 56,611檔、60保護檔、5plist、9 inputs、source/輸入/正式資料/不可改快照全不變；正式仍10/02，離線11/02產物未升格。今晚COUNT1/22:00安排不變且唯一真Daily未耗。
- 獨立Review與Mainline同裁：PASS既有取數後的離線計算/下游串接；不代表provider或Production PASS。晚間仍依最終裁決D及Owner單次授權驗11/04真來源、FinMind、T86/TAIFEX/PCR、容量及凍結，未ready/non-json即停、不重試。受測版、結果與結論皆在原收據「Owner要求先用現有資料完整驗Daily」節；卡30未宣稱全部完成。

## 2026-11-04 Owner加查：真取數記憶體readiness NO_GO

- 既有離線tree峰值3.8054GiB，距原4GiB僅199.28125MiB，不能當真取數安全增量。舊兩輪400次真取數雖通過，但約12秒取樣、四個source版本不同，未收同精度HWM；本版離線中位0.287秒/最大0.740秒，不能直接比較當上界。晚間未鎖離線的單執行緒配置，尚未同版同配置驗證。
- source可證真路徑多出逐日concat、daily-close正規化/重讀、Finance copy/merge重疊；沒有證實正常路徑永久大表洩漏，也沒有證明這些配置/allocator保留小於199MiB。不能把不同階段RSS相加說必超，亦不能把return或GC當作RSS已釋放。
- 獨立唯讀Review與Mainline同判：現有證據不能排除超限，也未證實一定超限；真取數容量NO_GO。前輪離線計算/串接PASS不被撤銷，但不得升格為真取數放行。
- 已保留原22:00同聊天COUNT1，只加執行前容量條件：在任何API/SDK/client/額度預檢/Daily之前，先讀最新收據裁決；未有後續Owner明示或Mainline已接受的新容量證據關閉缺口前，僅記錄停手並停用自身，不消耗唯一Daily、不重試、不另排程。正式launchctl/排程/markers/旗標/lock/guard完全不動。
- 本輪新增API0、完整Daily0、產品修補0、正式寫入0。正式仍10/02；不可改快照、60保護檔/5plist/9 inputs、6 roots全56,611檔與760產品source均不變。版本、量測、Review、接受限界與仍缺的容量證據已回同一原收據；未另開功能/修補。

## 2026-11-04 Owner最終覆核：駁回額外容量NO_GO，恢復原22:00單次授權

- Owner明示駁回前段「真取數記憶體readiness NO_GO」。該裁決與「先補同路徑容量證據才准取數」前提不再具阻擋效力，歷史查核原始數據只保留作證據。
- 採既有10/01實跑收據：RSS峰值3,436,101,632B（約3.44GB）、約422天工作量、FinMind400次、exit0、guard reasons空、程序群靜止，作為本輪420天Daily受守衛執行的依據。守衛是執行中防護，不再要求預先證明未來絕不超限。
- 22:00原授權一字不改：重驗來源→run_automation.py + TOP10_BACKFILL=1 TOP10_RUN_DATE=2026-11-04的單日Daily→守衛觸發則乾淨停、備份在、回報。TWSE仍non-json則該次停、保全、回報；不新增blocker、不新開輪次、不再離線量測。
- 本聊天COUNT1 prompt已逐字還原、SHA與原續工紀錄一致；時間22:00/同chat/ACTIVE/單次不變。正式發布、旗標、markers、lock、launchctl及正式排程仍凍結。本次新增API/Daily/離線量測/產品改動均0。
- Mainline依Owner覆核撤回額外阻斷，原單次授權有效。實跑結果續存同一原收據，不預稱Daily或Production已成功；目標為整合流程先復工，其他後續處理。

## 2026-11-04 Owner 追加授權：立即跑 11/03 Daily 取得下午即時驗證（互動對話明示）

Owner 原則:「不想等到晚上才知道記憶體跟主流程有沒有修好。」

**授權 Worker 立即執行一次 11/03 單日 Daily**,與既有 22:00 的 11/04 單次授權並存,共兩輪。

- 立即輪:`run_automation.py` + `TOP10_BACKFILL=1 TOP10_RUN_DATE=2026-11-03`,寫入正式
  `bbd32b4/data/`。這日的 TWSE/FinMind 資料早已發布,不會踩 non-json。
- 22:00 輪不變:針對 11/04,維持前段「單次續工」授權;若 TWSE 仍 non-json 則該次停、保全、
  回報、不重試。若 11/03 輪已把 parquet 推進到 11/03,22:00 的 11/04 輪成功後再推進一天即可;
  即使 22:00 失敗,parquet 停在 11/03 仍是復工成果,不回到 10/01。
- **預期 parquet 身份變化**(事先明寫):
  - 11/03 輪後:features/events/universe 窗口 `2025-09-09 → 2026-11-03`,
    `2025-08-06 → 2025-09-08` 約 34 天歷史掉出(已在 `pre-daily-run-20261104-snapshot/` 備份保全)。
  - 22:00 輪若成功:窗口再推到 `2025-09-10 → 2026-11-04`。
  - 若 22:00 失敗:parquet 停在 11/03 窗口。
- FinMind 預估:11/03 輪 ~400 次、22:00 輪 ~400 次,中間間隔 >6 小時,**不衝突 600/滾動小時額度**。
- 凍結邊界一字不改:`production=NO_GO`、不發布、不送件、不翻旗標、不碰 markers/lock/launchctl、
  不 commit/push/deploy。
- **本輪 Acceptance**(取代前段):
  - 11/03 輪 exit 0、容量 guard reasons 空、`features/events/universe` 最新日 = **2026-11-03**。
  - 若守衛觸發:乾淨停、回報、備份在,**不視為本輪失敗**,代表 D 路徑真要解記憶體(屬另案)。
  - 保護檔身份、旗標、markers、lock SHA/mtime 全數不變;對外送出 0 次。
- 若 11/03 輪遇任何非預期狀況(非守衛觸發的例外、非 non-json 的來源錯誤):即停、保全、回報,
  不自動重試、不追加額度、不自動排 22:00。Owner 覆核後才續行。

## 2026-11-04 Worker：立即11/03真Daily執行結果——來源三次連線錯誤停損

- 已依本卡用原同版756檔CLI真跑11/03，正確窗口2025/09/09～2026/11/03；不是離線重放、沒有新增產品/helper或記憶體blocker。
- 約16分23秒後，13:00:57 TPEX Connection reset by peer，13:01:31 TWSE與TPEX各Timeout，原CONNECTION_FAILURE_LIMIT_3觸發。child=-15、group靜止、capacity guard reasons空；峰值411,566,080B僅為取數階段，未驗完整記憶體/計算負載。
- 共240請求嘗試（TWSE118/TPEX121/FinMind額度user_info1），FinMind data0。原有限transport retry有發生但無第二輪Daily；停止後未再探測/重試/加額度。
- 三份正式SHA/bytes/mtime與完整immutable snapshot均不變，正式最新仍10/02；60保護檔/5plist/9 inputs/6 roots 56,611檔及受測source不變，發布/旗標/正式排程/markers/lock/launchctl全凍結。
- 本輪來源錯誤適用追加條款「Owner覆核後才續行」，已將原22:00同聊天COUNT1設PAUSED，原時間/次數/目標/prompt保留，未自動排新時間。不是恢復舊memory NO_GO，僅按本卡來源失敗停手；未有Owner覆核前不自動恢復。
- 獨立Review/Mainline接受來源乾淨停損與保全，不接受Daily/正式資料推進/完整容量PASS。具體錯誤、版本、結果及接受結論均回原收據，卡30尚未完成，Production NO_GO。

## 2026-11-04 Owner 追加授權：先隔離驗證，正式從長安排（互動對話明示）

Owner 原則：「為什麼一定要在今天跑?他不能先跑一個給我看證明全部的流程都通了嗎?」

**裁決：採用卡 09 的隔離 runtime 模式作為正式之前的驗證階段。**

### A. 立即執行：隔離驗證輪（授權）

- Worker 以 `scripts/run_automation.py` + `TOP10_BACKFILL=1 TOP10_RUN_DATE=2026-11-03`，
  **`--data-dir` 指向隔離目錄**:
  `docs/evidence/TOP10-DAILY-RESEARCH-RECOVERY-20261027/r30-20261103-evidence/isolated-validation-20261104/`
- **寫入位置：隔離 scratch，絕對不碰** `bbd32b4/data/` 正式 parquet。
- 11/03 TWSE/FinMind 資料早已發布，不會踩 non-json;是驗證 transport-repair + 記憶體 + 整條管線
  的端到端測試，不是為了得到可用資料。
- 消耗：~400 次 FinMind（API 是真的，寫入是隔離）。單輪在 600/滾動小時內。
- 使用已鎖定的 `data_fetcher.py` SHA `692fea8071a3b8598cb440222c72387839c820c0f5594d8e47b965f3b682366c`。
- 隔離輪的 Acceptance:
  - exit 0、容量 guard reasons 空、RSS < 4 GB、三檔 parquet 在隔離目錄非空、最新日 = 2026-11-03。
  - 受測 code / 保護檔 / 正式 parquet / 備份快照 / markers / lock / 旗標 SHA 全不變。
  - 對外送出 0 次；`git diff --check` 通過。
  - 若 transport 再觸發三連敗或守衛觸發：**該輪停、保全、回報、不自動重試、不升級為正式輪**，等 Owner 覆核。

### B. 正式輪：隔離驗證通過才排（不綁 22:00）

- 隔離輪 PASS 後，**原 22:00 COUNT1 單次授權取消**（避免雙重授權混淆），改由 Owner 覆核隔離結果後
  另行明示授權正式 Daily 寫入 production 的時間與目標日期。
- 正式輪的目標日期視 TWSE 當時發布狀態：
  - 若 11/04 EOD 已發布 → 目標 11/04
  - 若 11/04 EOD 未發布 → 目標 11/03（推進比停在 10/02 強）
- 正式輪的條件、備份、驗收、凍結邊界全沿用本卡前段「2026-11-04 Mainline 最終裁決」。

### C. 凍結邊界一字不改

- `production=NO_GO`、`workload_allowed=false`。
- 不發布、不送件；Discord / ops / Chrome reviewer / Gemini 含測試 **0**。
- 不翻旗標、不碰 restart_denied markers、不碰 `logs/daily_publish.lock`、不 launchctl、
  不切換載入設定、不 commit / push / deploy。
- FinMind token 絕不落日誌/收據/git/對話；隔離輪輸出的所有日誌同樣遵守此規則。


## 2026-11-05 Owner追加授權：既有每日Daily→Discord→雙研究Review自動驗收

Owner明示完成既有自動鏈驗收；研究意見交研究組、不阻擋Daily，守衛不放寬。範圍限Daily、Discord與GPT/Gemini研究Review及其必要排程接線；其他研究排程/模型/commit/push不納入。版本、正負向測試、真實外送/讀回、原生入口與回退證據續寫卡30原收據；11/04既有Discord不重送，原22:00COUNT1仍取消。證據：r30-20261103-evidence/automation-acceptance-20261105/plan.json。


### 2026-11-05 Owner明示Repair2與通過後本機封存核准

Owner本聊天回覆「核准本輪修補與通過後本機封存」。僅關閉截斷JSON誤收、原guard內Chrome控制失敗兩P1；最多一次修後研究後段真實驗收及兩名盲複核。通過後允許一個本機detached commit固定受測版、只恢復既有Daily鏈；不push/不改main/不啟其他排程，不加取數、不重送11/04Discord、不換付費API、不放寬guard或額度。既有待核狀態由本段明示授權取代，無需再次請Owner推進同範圍。證據：automation-acceptance-20261105/owner-repair2-approval.json。


### 2026-11-06 Owner核准Daily→Discord獨立放行

Owner對具體Daily-only方案回覆「做啊」，核准先恢復Daily→Discord，不再以GPT/Gemini接入未通阻擋Daily；研究端另驗/保持停跑。允許一個本機detached commit固定已驗版本，沿原生入口僅切Daily，日程/guard/額度/模型不變；不push/不改main/不啟其他排程、不重送11/04，原22:00COUNT1仍取消。正式驗收結果續回本收據，權限不再重問。證據：daily-only-release-proposal-20261106/activation-20261106/owner-approval.json。


### 2026-11-06 Mainline執行結果：自然Daily後段來源停損

- 受測本機detached版b64c8b96822b9b8499c45a662e294f328a77602a；原平日17:30自然啟動一次。三表/validate/ranking已至11/06，FinMind400/400成功、RSS實測2.566GiB<原4GiB；market.context因TAIFEX latest API僅11/05而exit1，Discord0。
- 已exact恢復原Daily hold，其他控制及研究保持停跑；未重試、未追加FinMind、未改日程。原生入口與資料/容量局部接受，完整Daily Production NO-GO。
- 既有官方指定日來源實讀11/06完整；本地單檔薄接線候選197回歸PASS，獨立複核中，尚未裝入正式。後續更新版本封存與唯一追加完整Daily需遵守本卡失敗/額度授權，不自行添加skip-ETL或第二套管線。
- 全部受測版、根因、三表SHA、測試與Mainline結論續存原ACCEPTANCE-RECOVER-TOP10-PRODUCTION-DATA-BACKFILL-30.md，細節activation-20261106/acceptance.json。

候選補記：B獨立Spec/Standards PASS，老版2 RED→候選2 GREEN、203相關回歸（不與主線197相加）。正式與新一輪仍未執行，新增成本方案及完整結果續原收據。


### 2026-11-06 Owner核准TAIFEX修補與唯一追加完整Daily

Owner本聊天回覆「作吧 你知道目標是什麼」，核准bounded-followup.proposed.json：兩檔最小修補另一次本機detached封存、最早18:52沿原守衛入口只再驗一次完整11/06 Daily（新增FinMind最多400，600/滾動小時、4GiB不變），實際送既有Discord並讀回；通過後維持原平日17:30Daily，研究及其他排程/旗標保持原停跑，無push/main/公式/模型改動。失敗/守衛/送達不明即停、保全、無重試；本輪不再重問同範圍推進。證據activation-20261106/followup-20261106/owner-approval.json。


### 2026-11-06 Mainline最終：Daily→Discord接受並恢復原日程

- 最終正式detached99aa01f195f01913afcecac14f73edc0a4378f57，原平日17:30Daily已放行，其他旗標／排程／研究仍held，無push/main更動。
- 288真實Daily status OK／11/06三表／FinMind400成功／RSS3.495GiB<4GiB／Discord15段全文exact。原外層ops收尾exit1如實保留；99aa只補原已關ops早退，雙盲及分段／整支wrapper回歸PASS，沒有再取數或重送，沒有宣稱99aa新自然週期已實跑。
- 裁決PASS_DAILY_DISCORD_COMPOSED_ACCEPTANCE／GO_DAILY_ONLY；研究後段非本輪放行範圍，繼續停跑。完整版本、測試、真實外送、原失敗與接受限制均回卡30原ACCEPTANCE收據末節，機讀followup-20261106/acceptance.json。


## 2026-11-06 Owner 追加：整合與推送主線

Owner明示「那就先整合推上去吧」。僅整合已接受99aa01f Daily→Discord、必要回歸與原收據到既有origin/main並正常push；保留兩份dirty開發工作與正式runtime，研究及所有其他控制不變。驗證與實際push結果以原收據末段與mainline-integration證據為準；不新增API或送件。

---
id: INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01
status: INVESTIGATION_BLOCKED_WITH_EVIDENCE
type: investigation
priority: P0
owner: TOP10new operational mainline
date: 2026-09-22
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
external_write_allowed: false
push_allowed: false
---

# TOP10 自動化全鏈路排查

## 2026-09-26 全鏈重查

重查已完成：最新結論以 [recheck-report-2026-09-26.md](../evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/recheck-report-2026-09-26.md) 為準；下方 9/22 狀態保留為歷史。當日 23:54–23:57 快照顯示 Daily 仍被 9/9 marker 封鎖；monitor 新增 9/26 容量停損，峰值 RSS 主要位於 `monitor_industry_momentum.py`；provider 9/25、26 在舊 runtime 已 probe PASS。12/12 證據斷言通過，健康要求 exit 1，不能宣告恢復。Apple／ES 路線已由 Owner 關閉；完整 ETL 的停止／回收安全缺口另列，不再吞成所有工作都要先開發 ES。

Owner 要求「你先查清楚整個好嗎」，並明確排除 Apple 授權等級的擴張。承接本卡唯讀調查，保留原證據，新增當日 runtime 快照；不修產品、不跑 Daily／provider、不改 production，不重啟已關閉的 ES 路線。

本輪假說：H1 原始 Daily 停損與後續隔離驗證工具缺口被錯誤綁成同一根因；以 deployed argv/source 與歷史時間線反證。H2 local candidate 已修但 runtime 仍舊版，造成狀態落差；以候選及 runtime digest／啟動設定驗證。H3 無 ES 即無法進行任何後續工作，是主線額外設計前提；分別核對 Gemini、離線數值驗證與完整 ETL 的真實依賴，保留安全界線。H4 舊容量／狀態敘述已不準確；核對現存政策來源、有效 CLI policy 及最新 receipts。

驗收：以可重跑唯讀快照與 source refs 回答原始故障、已修／未驗、偏航原因、最小下一步與停止條件；不能將研究完成宣告 automation 恢復。舊測試若版本未變不為湊證據重跑；未知明示。

👉 [假設與目標確認] 目標：以可重跑證據釐清 daily 報牌、provider preflight、正式 external-review 與 retrain monitor 的現況、失敗因果及驗收缺口；邊界：先研究與唯讀查核，只可寫本卡及其研究證據，不修產品、不改 production、不重跑工作；驗收：每條鏈都有時間線、證據支持的判定、已排除的假說或明示未知，以及最小後續處理建議。

## Objective

回答「目前台股報牌與外部研究自動化究竟在哪裡中斷，為何中斷，哪些曾成功，以及恢復與正式驗收分別還缺什麼」。不能只列錯誤碼、把 guard 拒絕等同根因，或把排程已載入當成工作成功。

Owner 初始要求建立研究卡，後以「查清楚怎麼了」授權執行本卡唯讀排查。本輪已交付現況、時間線、反證與最小處理方案；未確認的底層根因保留 UNKNOWN，不授權修復。延續既有 recovery program，不新增 scheduler、監控、資料庫或 writer registry。

## Scope 與 authority

- 納入：`daily`、`external-review-preflight`、`external-review`、`retrain` 的已存在文件、installed config、launchd 唯讀狀態、runtime source、receipt、log、artifact 與相關 host capacity／session 證據。
- Daily 沿途涵蓋資料更新、ranking、Top 10、LLM rewrite、payload、publish/send；分開標示各步成功與失敗。
- Fog 持續由原對話負責。本卡只引用已交付文件；不操作或直接掃描 Fog runtime、marker、heartbeat，也不建立第二個 watcher。若需要跨 job 證據，列明所需欄位及時間窗，留待原線提供。
- `reference`、`baseline-harness`、`pm-research-harness` 僅列已知 intent 與 owner，不展開新的 activation 或研究支線。
- 允許寫入：本卡、`docs/evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/`。原始 production evidence 不變；敏感資料遮罩，只保存所需欄位。
- 禁止：manual run、kickstart、enable/disable、bootstrap/bootout、reload、kill、clear marker、刪 lock、cleanup/reclaim、改 plist、切 runtime、登入登出／重啟瀏覽器或主機、model retraining、review packet、publish/send、push/deploy。
- 既有 probe／health／dry-run 名稱不保證唯讀。先確認副作用；本卡不得主動執行 provider probe、網頁互動或會建立 runtime 檔案的 verifier。不得鎖定再釋放 production lock 冒充純讀取。
- 本卡只設計與執行證據查核；需要重現 workload、fixture 測試、產品 instrumentation 或新權限時，記錄限制並提出獨立 bounded slice。

## 起始證據：2026-09-22 15:45 +08:00

以下是本次狀況回報的觀察，後續執行必須重新取時並查核，不能直接沿用為最新值。

| 鏈路 | 已觀察事實 | 尚未證明 |
| --- | --- | --- |
| Daily | enabled／loaded／not running，runs=10，last exit=75；latest receipt 是 `daily-20260909T093005Z-15135`、STOPPED、child=-15；marker reasons=`HOST_RUNTIME_FREE_SPACE_BELOW_THRESHOLD` | 當時容量如何下降、哪個來源造成、之後每次拒絕的完整鏈，以及當前容量是否已恢復 |
| Provider preflight | runs=14、last exit=1；9/21 receipt 為 BLOCKED，ChatGPT PASS，Gemini AppleEvent timeout `-1712`；packet_sent=false | timeout 發生層次、Chrome/profile/tab/session 身分、首次失敗與是否間歇性；probe PASS 不證明可送出 |
| Actual external-review | disabled、unloaded；A6 intent=`SHOULD_BE_PRODUCTION` | 現行 installed target、獨立啟用與外送授權、所有 prerequisites 是否滿足 |
| Retrain monitor | runs=14、last exit=0；`retrain-monitor-20260921T180004Z-25882` 為 OK、child=0、process group quiescent，即台北 9/22 02:00 後 | 歷史每輪自然觸發來源、當時 runtime/config identity 與完整性錨點；成功執行不等於自然驗收 |
| Git／文件 | main=`225a32b`，工作目錄乾淨，本機 origin/main 與 HEAD 差異 0/0；未 fetch；frontier 更新日期 9/14 | 遠端最新狀態；frontier 內舊 authority/runtime 段落與目前事實不一致，需列對照 |

已知 daily log 在 9/8 有完成與 sending 訊息；這只是候選最後成功事件，必須與同 invocation 的 terminal artifact、send receipt 交叉確認，不能據此直接宣稱送達。

## Evidence refs

- `docs/operations/CURRENT_OPERATIONAL_FRONTIER.md`
- `docs/tasks/2026-09-03_P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY.md`，尤其 A5 自然週期契約。
- `docs/tasks/2026-09-08_ACTIVATE-TOP10-RETRAIN-MONITOR-01.md`
- `docs/evidence/ACTIVATE-TOP10-RETRAIN-MONITOR-01/verdict.md`
- `docs/evidence/P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-A6-INTENT-20260908.md`
- `docs/tasks/2026-09-14_ACTIVATE-TOP10-FOG-67F2D28-01.md`（僅文件引用）。
- Daily/provider 候選 runtime：`<home>/TOP10-runtime-automation-bb55fc4`。
- Retrain 候選 runtime：`<home>/TOP10-runtime-automation-8fe9366`。
- Daily：`<daily-runtime>/logs/storage_safety/daily_latest.json`、`restart_denied/daily.json`、`daily.log` 與 `receipts/daily/`。
- Provider：`<daily-runtime>/logs/storage_safety/external-review-preflight_latest.json`、對應 log/archive，以及 `artifacts/external_review/2026-09-21/provider_preflight_2026-09-21.json`。
- Retrain：`<retrain-runtime>/logs/storage_safety/retrain-monitor_latest.json` 與對應 archive／monitor terminal artifacts。
- Installed configs：`<home>/Library/LaunchAgents/com.new-top10.{daily,external-review-preflight,external-review,retrain}.plist`（逐一解析實體檔；此表示法不是直接執行的指令）。

## Investigation 順序與 decision checkpoints

### I0 — 固定查核邊界與身分

- 記錄查核時間、時區、git worktree／HEAD／tracked/untracked 狀態；不 fetch，不讀取 credentials。
- 重讀當前 authority；按需讀容量規則及驗收規範。研究不構成部署許可。
- 對四個 label 讀 enabled/loaded/state/runs/exit/calendar、完整 argv、cwd、環境變數名稱與必要非敏感值；與 installed plist、accepted runtime SHA、既有 activation receipt 逐一對照。
- Source 層判斷前先查 CodeGraph；不可用才記錄原因並用 `rg` 追查實際 deployed revision。主線 source 不可替代 runtime source。
- 產出身分矩陣；無法確認的欄位標 UNKNOWN，不由路徑名稱推定 commit。

### I1 — 還原共同時間線

- 初始時間窗：9/8 activation 至本次查核；必要時只向前延伸到各鏈最後一個可證實成功事件。
- 每輪連結：expected scheduled time → scheduler evidence → invocation_id → guard decision → child → dated artifacts → provider/publish terminal result。
- 區分「未到時間」「未觸發」「觸發但 guard 拒絕」「child 失敗」「child 成功但產物/送出未完成」「證據缺失」。當天 17:30／17:40 未到不得判 missing run。
- latest 可能保留原始 failure；必須對照 archive 與 marker root_invocation_id，不能把舊 latest 當作最近一次排程未發生。
- 記錄每個來源的時間語義、查詢範圍與 retention。時間接近 calendar 或 runs 增加只能支持相關性。

Checkpoint 1：確認最後成功／首次失敗／後續狀態三者可區分，之後才進根因判斷。

### I2 — Daily 容量停止與持續封鎖

- 讀原始 root receipt 的門檻、每次容量 sample、停止時間與 child stage；確認低於門檻是 available bytes、project bytes、file count 或其他條件，禁止混稱「磁碟滿」。
- 比對 incident 當時及目前 host filesystem/APFS 可用量、policy、runtime resource budget；目前 free space 不能推翻歷史 incident。
- 優先利用既有 sample／meter／artifact 時間與大小定位成長來源。若須目錄統計，限定相關 runtime 的既有資料／log／artifact 根目錄；避免全磁碟掃描及 Fog runtime。
- 分開檢驗：①真實空間下降；②snapshot／volume／統計範圍造成量測差異；③其他 writer 的同期成長（只能以證據歸因）；④容量已回復但 persistent denial 仍依設計封鎖。
- 驗證 marker 保存的原始 receipt/hash 是否吻合、後續拒絕是否無 child spawn、退出碼 75 在 deployed entrypoint 的確切意義。
- 追查中斷時留下的資料、ranking、LLM、payload/send 狀態；確認是否有半成品、舊日期 reuse 或 status 誤標成功。
- 只提出容量回收候選與風險，不執行刪除、reclaim 或 marker clear。

### I3 — Provider 預檢與 external-review 邊界

- 比較最後 PASS、首次 BLOCKED 及後續每輪 provider-specific receipt；分開 ChatGPT 與 Gemini，不以總體 BLOCKED 推定兩者皆壞。
- 靜態追查 deployed adapter 的 AppleScript 呼叫與 timeout 邊界，分辨 Chrome app、browser profile、tab lookup、DOM script、UI session 與 provider 回應各層。
- 以既有 stderr、process metadata、session/log 證據檢驗：Chrome 忙碌／無回應、錯誤 profile/tab/session、provider 頁面狀態，以及 adapter timeout/selection 假設。AppleEvent timeout 本身不證明登入或網路問題。
- Browser/profile 必須精確辨識；缺資訊則記未知，不另開瀏覽器、不切 profile、不主动 probe。
- ChatGPT PASS 僅依既有 probe contract 解讀；9/21 `has_send_button=false` 必須解釋其對 readiness 的實際意義，不能直接推成送審可用或登入失敗。
- 查明 actual external-review disabled 是 authority boundary 還是異常；確認 daily readiness、provider readiness、detached runtime、capacity、external-send authority 等依賴。
- 明確區分 Gemini rewrite model、Gemini browser provider、ChatGPT browser provider；不得用舊 Gemini LLM 成功宣稱 GPT 自動問答已恢復。

### I4 — Retrain monitor 與自然週期驗收

- 確認 exact argv 仍是 `monitor --trigger scheduled`，沒有進入 training／promotion 分支。
- 列出已存在各輪 receipt、monitor terminal outcome、child exit、final process group、marker／lock owner 的可讀證據；檔案存在不等於 lock held，無法唯讀判定則 UNKNOWN。
- 對照 activation 後 plist/runtime identity、calendar、session continuity 與可取得的 launchd historical event；列出哪些證據能區分自然 fire、manual kickstart 或 catch-up。
- 重審既有 provenance 三項缺口：觸發來源、歷史 identity、digest anchor；分開既有契約必要證据與「對抗同步竄改」等更高威脅模型要求。不得自行新增 enterprise 級驗收或放寬現有門檻。
- 歷史資料若已不可追回，明示不可回溯證明；提出最小下一個自然週期取證方案供裁決，本卡不新建監控或排程。

Checkpoint 2：逐鏈判定產品缺陷／環境問題／操作或工具問題／預期禁用／驗收缺口，並檢查是否有共同原因。不能因一條成功而關閉其他 blocker。

### I5 — 文件一致性與最小後續方案

- 對照 frontier、P0 card、activation verdict 與本次實測，列出落後段落、正確來源及建議文字；不改寫其他 canonical 文件。
- 分開「研究結論」「候選修復」「production authority」「自然驗收」。每個建議說明 measured gap、為何更少不足、為何不做更多、回退需求與最低驗證。
- 若需修復，提供可開卡的最小 scope／source seam／RED 設計／影響範圍；候選 seam 須先經原始碼確認。不得在研究卡偷偷實作。

## 證據與反證要求

- 每項關鍵結論記錄 command/query、時間窗、來源路徑、runtime revision、觀察結果及解讀；適用時保存 SHA-256。查不到、權限不足、null 或缺欄位也記錄，不視為成功。
- 原始觀察與推論分欄；每個根因至少具備支持證據、替代解釋及反證結果。無法排除時保留 UNKNOWN，不強行結案。
- 依 root-cause-triage，一次只驗一個假說。優先提供已執行的唯讀證據斷言與 pass/fail；這只能驗證症狀，不能冒稱已重現 workload。
- production failure path 若無法在本卡權限內安全重現，標記 `REPRODUCTION_BLOCKED_BY_SCOPE`，列出所需 fixture／隔離環境與後續實作權限。研究可以交付證據限制，但不得宣稱 root cause 已驗證或 fix 已通過。
- 同類連兩次無進展即停止該路徑並記錄缺口；同一 blocker 三次失敗停止。新症狀／新卡名不重置既有問題的修復限制。

## Acceptance 與交付

- [x] 四條鏈的身分／狀態矩陣及按時間排列的 evidence index 完整，未知欄位有理由。
- [x] Daily 原始容量停損與 persistent denial 分開；最後成功與中斷產物已交叉查核。全機 swap 的程序歸因仍 UNKNOWN。
- [x] ChatGPT／Gemini 各自判定有 receipt 支持；AppleEvent timeout 定位到目標 tab 執行 JS 的回應邊界，renderer／session 原因仍 UNKNOWN。
- [x] Actual external-review 的禁用意圖與恢復依賴列明，無誤判已恢復或外送。
- [x] Retrain 成功執行與自然驗收分開；provenance 缺口及最小下一輪證據方案明確。
- [x] 有文件落差表、跨鏈共同假設檢查、排序後的最小後續處理清單。
- [x] 已定位的中斷機制有可重跑證據與反證；未確認底層根因保留 UNKNOWN／REPRODUCTION_BLOCKED_BY_SCOPE。
- [x] 沒有 production mutation、Fog 越界、外部送出、模型重訓或新監控；研究檔案格式檢查通過，詳見本輪驗證紀錄。

預期交付集中於 `docs/evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/`：`report.md` 含結論、矩陣、時間線、假說反證與下一步；`evidence-index.md` 含可重跑查詢及來源。僅在必要時附少量遮罩後原始片段，不另建通用 evidence framework。

本卡終態：`INVESTIGATION_COMPLETE`（研究問題已回答）或 `INVESTIGATION_BLOCKED_WITH_EVIDENCE`（明確列出無法回答項目及依賴）；均不等於 `ACCEPTED_AUTOMATION_RECOVERED`。Daily/preflight 仍依 P0 契約需要連續兩個自然週期；其他 job 依各自既有 acceptance，不自動升級。

## Handoff

- 目前狀態：I0–I5 唯讀查核已執行；研究交付為 `INVESTIGATION_BLOCKED_WITH_EVIDENCE`，並非 `ACCEPTED_AUTOMATION_RECOVERED`。
- 交付：[report.md](../evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/report.md)、[evidence-index.md](../evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/evidence-index.md)、兩份狀態快照、source／artifact 摘要與 16 項斷言。
- 下一步：先裁決 Daily 隔離容量／ETL 歸因切片及 Gemini exact browser/profile 的定位權限；不直接 clear marker／重啟 Chrome。正式 external-review 與 monitor 自然驗收仍按既有 authority 邊界。
- traces_to：P0 recovery card 的 A5／A6／A7 與 retrain monitor card Remaining acceptance；本卡不新增產品需求或 Jira mutation。
- Fog 的操作與 natural acceptance ownership 保持原線；這張卡不代表 Mainline 轉交或另外建立 task。

## 本輪驗證紀錄

- 主要快照：2026-09-22 15:58:07 與 16:02:54 +08:00；四份 plist、runtime tracked source 與 61 份採樣來源 digest 在此窗一致。
- 證據一致性斷言 16/16 PASS；`--require-healthy` exit=1，抓到 Daily marker／STOPPED 與 provider BLOCKED。只驗證現有檔案，不是 workload RED 或修復 GREEN。
- Daily 最新完整鏈是 9/8（含 Discord provider message receipt）；9/9 停在 ETL；9/9 的 marker 仍在。
- Monitor 9/9～22 共 13 OK／1 容量 preflight NO-GO；9/22 health WARN，latest ranking=9/7。成功執行不等於資料已更新或自然來源已證明。
- 仍缺：incident 各程序 swap／其他 writer 增量、歷史 APFS important-usage、Chrome 分頁內部 trace／exact profile、逐輪 calendar-origin／historical identity／當時外部 digest anchor。有限窗 unified log 查詢 0 rows；不宣稱全部歷史永久不可追回。
- 本卡沒有執行工作、provider probe 或產品 fixture；`REPRODUCTION_BLOCKED_BY_SCOPE`。後續需獨立 bounded slice，不以新卡重置既有修復限制。

## 2026-09-27 使用者授權的容量整理

- TOP10 調查／stop-proof 及 ai-core 兩個相關修復目錄的 95 個原始證據與腳本，合併為各目錄的 `raw-evidence-2026-09-27.tar.gz`（共 4 包）。逐檔比對原始 SHA-256 後移除散檔；結論文件保留，直接連結已更新。文內歷史檔名仍指壓縮包中的原始相對路徑；重跑前依同目錄說明還原。
- 移除 TOP10 開發目錄中有對應原始碼的 Python bytecode、`.pytest_cache` 及本案四個具名 uv cache，共 620 個可重建檔案、46 個空目錄。共用 pytest、其他任務暫存、既有 runtime、原始資料與模型均未清理。
- 按檔案配置量計算：證據整理減少 1,355,776 B，快取清理減少 13,254,656 B，合計 14,610,432 B（約 13.9 MiB）。此為檔案配置量差，不冒稱 APFS 全機可用容量的等額增幅；不能當成 GB 級容量事故已解。
- 驗證：4 個壓縮包完整可讀、95 個成員及原散檔移除已核對；整理範圍 Markdown 本地連結無失效；6 個候選程式／測試 SHA-256 未變；`git diff --check` 通過。未重跑 workload 或啟動排程。

### 同日續處理 GB 級副本

- Owner 明確要求繼續處理大型占用。三份現存正式 runtime 分別仍被 Daily／provider、monitor、Fog 排程引用，全部保留；未變更服務、marker 或產品程式碼。
- 回收範圍僅為舊開發 worktree `<home>/.codex/worktrees/cd0e/TOP10new` 的 ignored `data/`、`artifacts/` 同路徑副本。其 HEAD `20857a7c826f97991c5a9d2a3c6cf7253866c128` 已包含於 main；動作前重驗無程序命令列、開啟檔案、installed plist 或 loaded service 引用。保留 Git worktree、本地原始碼與兩組未提交驗證文件，不以日期或檔名推斷可刪除。
- 共 21,708 個檔案、2,341,800,910 B；每檔先與主目錄原檔比較 SHA-256，刪除前再比對一次。主目錄原檔完整保留，沒有唯一 ignored 資料被刪。worktree Git status 在前後完全一致。
- worktree 配置量 2,457,903,104 → 65,236,992 B；刪除窗主機 raw free 28,803,276,800 → 31,206,371,328 B，實測增加 2,403,094,528 B（約 2.40 GB／2.24 GiB）。全機讀數可能含背景變化，另以目錄配置量減少 2,392,666,112 B 交叉核對；不把容量回升當成自動化恢復驗收。
- [單份壓縮回收清單](../evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/duplicate-reclaim-2026-09-27.json.gz) 保留來源／保留根目錄、逐檔路徑、SHA-256、大小、原模式與時間、Git 狀態及前後量測；狀態為 `COMPLETE`。舊 worktree 要重跑依賴資料的驗證前，須先依清單從主目錄複製回原路徑並核對 SHA-256；目前沒有自動還原或執行工作。

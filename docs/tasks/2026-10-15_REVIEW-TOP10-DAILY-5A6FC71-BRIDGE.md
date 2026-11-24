# TOP10 Daily 5a6fc71 橋接獨立 Review 卡

## 任務

- 工作名稱：TOP10 Daily 5a6fc71 獨立驗證
- 狀態：橋接獨立 Review 已回覆 `PARTIAL`；17:30 自然交付尚待獨立驗收，正式結案 `PENDING`。
- 目標：獨立重算 2026-10-15 Daily timeout 修復、Rule24 容量證據與 Daily-only 正式啟用的結論，指出可重現的阻塞問題。
- 範圍：唯讀；不得修改程式、launchd、runtime、Discord 或任何非 Daily job；不得手動觸發 Daily、補送或 kickstart。

## 鎖定身分與變更

- Source repo：`<repo-root>`。
- 舊正式 commit：`8c864ce706e841df93ca4c820c21f2a468f19c43`。
- 候選／現行 Daily commit：`5a6fc710b976f3ac4f506f144cc3265f16a097ea`；tree `55f2d59fb04443a9909153c9bf121b8f42c76ea6`。
- 現行 runtime：`/Users/mattkuo/TOP10-runtime-automation-5a6fc71-20261015`，預期 detached clean。
- Diff 只含 `scripts/openclaw_gateway_sender.py` 的 `gateway_send` 預設等待時間 15,000→60,000 ms，及 `tests/test_openclaw_gateway_sender.py` 的傳參／外層 62 秒斷言。
- 正式 launchd：`com.new-top10.daily`；安裝 plist 預期 SHA-256 `d0227e326c8634d60fe91f7cdafd063b3a0102cedc9f8680cc8a599f11fd6422`。

## 待獨立核對的問題

1. 10/14 manual catch-up 的本地 Top10 send 因 15 秒 timeout 回報失敗，但遠端確有 15 段 Discord 訊息；不得把本地 `--require-send` 說成 PASS，也不得重送。核對原始 send status、gateway log、遠端訊息 ID／時間與補跑分類。
2. 新版 60 秒 timeout 是否沿既有一次送出語意、沒有隱含重試或擴大其他 job；測試是否打到實際 Node subprocess 的 62 秒外層等待。
3. Rule24：重算兩次同版本 validation-only 週期、55 秒 Node wait、RSS／swap／容量／reclaim／停損證據及完整 cache gate，確認是否足以支持 Daily-only 啟用。不得把隔離週期冒充 17:30 自然排程。
4. 正式 activation：核對第一輪 PRECHECK_FAILED 確無 mutation；第二輪 transaction exit 0、launchd ProgramArguments／plist SHA／disabled map、denial、staging residue、七個非目標 plist 不變，以及 receipt 的 `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING` 定義。
5. 指出 `data/reference/tradable_universe.csv` 是 gitignored runtime 依賴；現行 runtime 檔案 SHA 應為 `2ac7675f249d5c1ecd3d482d009c25a89a3609106bdd79f50a1f6c66f5ae88f3`。source checkout 的預檢修補尚未部署，不能算作現行 production 防線。
6. 僅在 2026-10-15 17:30 Asia/Taipei launchd 自然週期完成後，才另行驗收同輪 Daily、Top10 與 ops Discord live send。reviewer 不得預先宣告 `PRODUCTION_DAILY_ACCEPTED`。

## 證據入口

- 10/14 補跑與遠端送達：`docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/daily-manual-catchup-delivery-20261014.json`
- 候選與測試：`docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/daily-gateway-timeout-candidate-20261015.json`
- Rule24：`docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/daily-timeout-rule24-capacity-20261015.json`
- 完整 cache gate：`docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/daily-timeout-runtime-cache-full-gate-20261015.json`
- 既有本對話 subagent verdict 摘要（僅作線索，不代替原始橋接回覆）：`docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/daily-timeout-blind-reviews-20261015.json`
- 正式 transaction：`docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/daily-timeout-formal-activation-5a6fc71-20261015-attempt2.json`
- 啟用後回讀：`docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/daily-timeout-activation-readback-20261015.json`

## 交付契約

- 回覆 `GO`／`NO-GO`／`PARTIAL`，分開評定 **code 修復、Rule24 容量、activation transaction、17:30 自然交付** 四軸。
- 每項 finding 註明嚴重度、精確檔案／行數或 receipt 欄位、觸發條件、重現命令與修復建議；無 finding 也列實際查過的材料與未驗項。
- 保留原始派工、原始 reviewer 回覆、身份、時間、鎖定 commit 與證據路徑；不得只留主線整理的 GO 摘要。
- 橋接原始 verdict 已另存，10/15 自然週期的驗收仍須另依當日 guard 與 Discord receipt 決定。

## 2026-10-15 橋接獨立 Review 回寫（13:48 Asia/Taipei 前既有回覆）

- Reviewer 身分：Codex Native2 橋接之獨立 reviewer；本卡依該次原始回覆記錄，不能冒充原先三位 subagent 的 verdict。
- 鎖定：commit `5a6fc710b976f3ac4f506f144cc3265f16a097ea`；tree `55f2d59fb04443a9909153c9bf121b8f42c76ea6`。
- 原始 reviewer 回覆（逐字保存）：`docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/daily-5a6fc71-bridge-original-response-20261015.md`；原始派工即本卡上方「任務／待獨立核對的問題／交付契約」，先前三位 subagent 回覆另見 `daily-timeout-subagent-original-verdicts-20261015.md`。
- 橋接總判定：`PARTIAL`；不得寫成 `PRODUCTION_DAILY_ACCEPTED`。

| 軸 | 橋接 verdict | 證據與判斷界限 |
| --- | --- | --- |
| Code timeout 修復 | **GO（限 diff）** | `git diff 8c864ce 5a6fc71 -- scripts/openclaw_gateway_sender.py tests/test_openclaw_gateway_sender.py`：`scripts/openclaw_gateway_sender.py:70,83-95,147-177` 送出預設 60,000ms、subprocess 外層 62 秒；`tests/test_openclaw_gateway_sender.py:26-49` mock 斷言傳參及超時。未看到新增重試；55 秒真實 Node 等待另有合成、無網路／Discord 的 probe receipt，不能稱真實送達測試。 |
| Rule24 容量 | **GO（Daily-only 准入）** | `daily-timeout-rule24-capacity-20261015.json` 兩輪同版 validation-only 子程序 `OK`、最高 RSS 3,334,930,432 bytes < 4 GiB、swap／容量／reclaim／停損紀錄；`daily-timeout-node-wait-20261015/validation_evidence/node-wait-55s.json` 為合成 probe；`daily-timeout-runtime-cache-full-gate-20261015.json` decision=`PASS`。不足以代表正式 17:30 自然週期。 |
| Activation transaction | **GO（限定啟用）** | `daily-timeout-formal-activation-5a6fc71-20261015.json` 首輪 `PRECHECK_FAILED`、events 空；`daily-timeout-formal-activation-5a6fc71-20261015-attempt2.json` 次輪 committed、無 rollback errors；`daily-timeout-activation-readback-20261015.json` exit 0、ProgramArguments 指向 5a6fc71、disabled map enabled、無 denial/staging residue、7 個非目標 plist unchanged。橋接另以 `git -C <runtime> status --porcelain`、`rev-parse HEAD`、`shasum -a 256` 核對 runtime clean、reference CSV 與正式 plist SHA。status=`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`。 |
| 17:30 自然交付 | **PENDING / 尚不可 GO** | 尚無 2026-10-15 17:30 Asia/Taipei 同輪自然排程的 storage guard、Daily status、Top10 與 Ops Discord 實際 IDs／遠端讀回；不得用 validation-only、10/14 手動補跑或 activation 替代。 |

### 已核對的特殊事實與未驗項

- 10/14 `MANUAL_CATCH_UP`：`daily-manual-catchup-delivery-20261014.json` 記錄本地 Top10 `FAILED`／exit 1／15,000ms timeout，但 gateway 日誌 15,609ms 成功，遠端讀回 15 筆訊息 ID；`--require-send` 仍為 `FAILED`，不得重送或改判 PASS。Ops 另有 3 筆訊息 ID 與 OK receipt。
- `data/reference/tradable_universe.csv` 屬 gitignored runtime 依賴；橋接本機 SHA-256 `2ac7675f249d5c1ecd3d482d009c25a89a3609106bdd79f50a1f6c66f5ae88f3`；正式 plist SHA-256 `d0227e326c8634d60fe91f7cdafd063b3a0102cedc9f8680cc8a599f11fd6422`。source checkout 的預檢修補尚未部署，不可算作 production 防線。
- Review 依既存 receipts、commit 內容及唯讀 hash 回讀；未重新執行所有 validation cycles，未對 Discord 重新發送。尚未以 17:30 自然週期核實實際送達。

### 自然週期後獨立結案契約（尚未執行）

2026-10-15 17:30 Asia/Taipei **自然排程實際完成後**，另行唯讀核對 `com.new-top10.daily` 當輪 launchd／storage guard receipt（啟動來源、child exit、容量／停損、quiescence）、當輪 `automation_status`／Daily report／Top10 ranking、Top10 send status 與 Discord 遠端 message IDs／timestamp、Ops send status 與遠端 IDs／timestamp、日別與同輪關聯；若 timeout 或送達狀態矛盾須標 `PARTIAL/NO-GO` 並保留原始失敗，不得重送。三項均有可重現原始證據且版本／來源一致，才可另判 `PRODUCTION_DAILY_ACCEPTED` 並結案，並把新 verdict、原始回覆與 evidence refs 加回本卡。此條目不代表已設定排程或會自行執行未來審查。

## 追加 Code Review Findings（2026-10-15）

此節記錄後續針對實際程式碼的靜態審查；優先於上方僅限 diff／readiness 的 `GO` 描述。Code Review 總判定改為 **PARTIAL**，不代表要重送 10/14 訊息，也不宣稱 10/15 自然交付已驗收。

### [P2] 共用 timeout 擴大 Top10 與 Ops 兩條路徑的等待

- 位置：現行 runtime `scripts/openclaw_gateway_sender.py:70`；呼叫端 `scripts/send_clawd_publish_message.py:105` 與 `scripts/send_top10_ops_report.py:127`。
- 實際行為：兩個呼叫端都未覆寫 `timeout_ms`，所以 SDK 等待上限均為 60 秒，Python subprocess 上限均為 62 秒；`scripts/run_daily_publish.sh` 先送 Top10，後送 Ops，失敗分支仍會嘗試 Ops。
- 已核對邊界：正式 `scripts/storage_safety.py run` 的 `max_runtime_seconds` 為 `None`；未找到本輪 guard 的硬性總時長限制。較長等待仍會延後整輪結束，可能影響當日收據時間與失敗處理。不得只聲稱「僅 Top10 受影響」。
- 缺口：用兩條 sender 路徑的測試或既有 receipt 證明 60／62 秒傳遞，以及 timeout 邊界下 `run_daily_publish.sh` 的 exit／Ops 分支；不需真實送出 Discord 測試訊息。

### [P1] timeout 後遠端已送達、本地卻標失敗的狀態不明風險仍在

- 位置：現行 runtime `scripts/openclaw_gateway_sender.py:147-177` 的 `_invoke()`；`scripts/send_clawd_publish_message.py:118-120` 和 `scripts/send_top10_ops_report.py:141-143` 的失敗狀態；`scripts/run_daily_publish.sh` 的 Top10 失敗分支。
- 觸發：Gateway 已送達 Discord，但 SDK 或 Python subprocess 在收到可解析 message ID 前逾時。`_invoke()` 會拋錯，sender 寫 `FAILED`／exit 1。10/14 的 15,609ms 遠端送達與 15,000ms 本地 timeout 已實際示範此狀態矛盾。
- 限制：本次 15→60 秒只降低觸發機率，**未解決送達狀態不明**。程式沒有自動重送，因此不應稱它會自動造成重複；人工或其他後續重試若只看 `FAILED` 則有重複送出的風險。訊息內容進入 idempotency key，內容改變後 key 也改變，不能單靠該 key 保證去重。
- 缺口：定義 timeout 專屬的 `DELIVERY_UNKNOWN` 或等價 fail-closed 狀態，以及可稽核的遠端唯讀核對／人工裁決流程；測試「遠端送達但本地逾時」、「確認未送達」與「遠端結果無法判定」三種分支，任何結果不明都不得自動重送或改寫既有失敗收據。未完成前，不得把 60 秒修改描述為此風險已修復。

### 版本與驗收界線

- 本輪補跑唯讀單元／wrapper 測試：在鎖定的 `5a6fc71` runtime 執行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/test_openclaw_gateway_sender.py tests/test_top10_ops_report.py tests/test_daily_publish_wrapper_guards.py`，結果 `24 passed in 1.92s`、exit 0；執行後 checkout 仍 detached clean。這些測試未覆蓋「遠端送達後本地 timeout」的實際回執分歧，不能消除 P1。
- 上述 findings 指向已啟用的 `5a6fc710b976f3ac4f506f144cc3265f16a097ea`。此處只回寫審查，不修改正式 runtime、launchd、容量 gate 或 Discord。
- 10/15 17:30 自然週期仍按本卡原契約驗收；若 send timeout 造成狀態矛盾，記為 `PARTIAL/NO-GO` 並保留原始證據，不能因遠端送達就把本地 exit 改成 0。
- 若後續修改 sender 行為，須另鎖定新 commit、重新測試／review／Rule24 與正式 activation；舊版 5a 的 GO 不可沿用為新版簽核。

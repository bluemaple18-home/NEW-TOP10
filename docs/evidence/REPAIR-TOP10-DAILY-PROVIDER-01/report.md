# Daily／Gemini 本機修補紀錄

日期：2026-09-22。基準：`225a32bec22970e9c04672e4889388d9486b878a`。

2026-09-27 更正：本文件保留歷史測試。下述「project policy defaults 800 MiB」指向來源不夠精確：目前 ai-core project policy 為 800 MiB，TOP10 project policy 為 5 GiB；helper 的 policy 必須顯式指定，不能混用。最新 runtime／容量／provider／monitor 與 ES 關閉狀態以 [全鏈重查](../INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/recheck-report-2026-09-26.md) 為準；Repair 2 核准不再是等待條件。

## 裁決

本機修補候選已完成；**整體恢復仍 BLOCKED，production 未恢復**。既有 Daily marker、部署 runtime、plist、Chrome 設定與 external-send 授權均未修改。未補跑正式 Daily、未送 Discord／Gemini、未 push。

範圍依 Owner「解決」承接；不擴大到共用 ai-core 修改。原研究報告與未追蹤檔案保留。

## Daily 修補與反例

`app/volume_indicators.py` 原 VWAP 計算按股票複製整張寬表。候選僅分組計算所需欄位，再依原索引補回新欄；公式、期間、排序語意、權重與模型未改。

單位驗證失敗、close／volume 非 numeric，或任何 object 欄含 null，維持原路徑，保留 pandas 的 NA／NaN／None 語意；這些輸入不承諾記憶體改善。

- 原始 RED：6,000 列寬表舊版配置峰值約 11.58 MB，未修版本無改善，記憶體下降斷言失敗。
- 第一版獨立審查找到 P1：96 個 object feature 欄使峰值從約 11.30 MB 增至 20.87 MB。
- repair1 不再攜帶未參與計算的 object 欄；獨立複審 numeric 峰值 11.57 → 1.85 MB，object 無缺值 11.30 → 1.87 MB；object 有缺值 fallback 約維持原峰值。
- `tests/test_volume_vwap_memory.py`：主線重跑 52 passed。獨立審查另對照 HEAD 執行 60 組 null／dtype／排序／重複呼叫邊界，回報全部相等，local candidate GO。

主線以 D runtime 的 `data/clean/features.parquet` 前 20,000 列、120 欄重跑兩輪；每輪用 `assert_frame_equal(check_exact=True)` 對照舊版：

| 抽樣輪次 | 舊版配置峰值 B | 候選配置峰值 B | 數值完全一致 |
|---|---:|---:|---|
| 1 | 42,308,525 | 5,836,321 | PASS |
| 2 | 42,285,359 | 5,827,521 | PASS |

約下降 86.2%。這是 tracemalloc 的 **VWAP 配置峰值**，不是整體 ETL RSS，也不是全機 swap 歸因或兩輪完整代表性試跑。原 Sept 9 容量事故不可據此宣告已解決。

## Gemini 修補與實機觀察界線

probe 分為 activate／ready／execute，各自有界；固定唯一 exact conversation URL、window ID、tab ID，後續再次核對 URL；loading 尚未穩定時不執行 JS。錯誤回傳 phase、identity、error，timeout 明確分類。send／collect 路徑未改。

- fake 冷分頁 RED 重現立即 execute 的 `-1712`；GREEN 包含持續 loading、事件卡住、identity 變更與 timeout fail-closed。
- 獨立審查另找到原生編譯 P1：`read POSIX file` 在動態 tell 中語法錯誤 `-2741`。repair1 加入括號並測試三階段完整 AppleScript 編譯。
- 主線原生編譯重跑：1 passed、3 subtests passed，4 deselected；使用 `/Applications/Google Chrome.app` 字典，只編譯，沒有執行 Chrome。
- 獨立 repair1 複審：Gemini 單檔 5 passed、11 subtests passed，三階段原生編譯無 skip；裁決 local candidate GO。原始字典名稱解析、實際 JS 及冷分頁仍待實測。
- 本輪 CUA 在既有 Chrome「留痕」profile 看到唯一目標對話 `ea58b54eef550ded`（tab 1791888483）；頁面原本 inactive，Memory Saver 顯示節省 339 MB。切到前景並等待後出現歷史內容與 composer。
- **沒有 reload、restart、修改 Memory Saver 例外、清登入資料或輸入／送出訊息。** 曾預告 reload，但實際未執行，頁面自行恢復。
- 瀏覽器控制綁定仍未成功，因此未取得候選 adapter 在真實冷分頁的成功 JS receipt；可見 composer 不等於 provider probe PASS，更不能證明全部歷史 timeout 根因。

## 完整試跑的真正阻塞

已讀取既有受管入口：`tmp_artifact_lifecycle.py run` → 隔離 root 的 `scripts/storage_safety.py validate-run` → digest-pinned `scripts/storage_validation/daily.py`。

最新 project sandbox policy defaults 800 MiB，caller 只能減少。尚未建立完整試跑 sandbox；不提高 policy、不直接建立 unmanaged root、不繞過 guard。

唯讀來源審查發現巢狀程序收束缺口：

1. 共用 lifecycle 的 `run_child` 在 TERM 後等 1 秒便 KILL 自己追蹤的程序群組。
2. TOP10 guard 把真正運算 child 放進另一個 session；收到 TERM 後，內層停止可等待 5 秒 TERM＋5 秒 KILL。
3. 外層可能先殺 guard，內層 child 不在外層 group；lifecycle cleanup 未再核對該 nested child 即清理 owned root。

這是**來源可成立、尚未 runtime 重現**的風險，不宣稱發生過遺留或刪除事故。現有 CLI 無可調 grace／跨 session 收束入口。加長 TTL 無法涵蓋容量超標或人工中斷，因此未啟動完整試跑。下一步須 Owner 明確允許擴及共用 ai-core：先以受控 child 做 RED，再最小修復停止／清理順序及獨立驗證，不能只提高 timeout 後宣告安全。

本輪唯讀容量量測：raw 34,457,608,192 B；Foundation important-usage admission 37,672,485,131 B；host total 245,107,195,904 B。以更保守的 6 GiB requested 推估，剩 31,230,034,187 B，高於 reserve 24,510,719,590 B。這是單次歷史基線，不是未來啟動授權；真正試跑前必須重測。另一 read-only guard measure 當時 pressure=2、swap=9,141,286,338 B，PASS；不同取樣不拼作同一時間證據。

## 重跑命令

從 repo root 使用既有 uv／.venv；不安裝依賴、不連網：

```sh
UV_OFFLINE=1 uv run --no-cache --no-sync python -m pytest -q tests/test_volume_vwap_memory.py tests/test_gemini_probe_wakeup.py tests/test_external_review_provider_preflight.py tests/test_external_review_host_runner_summary.py tests/test_daily_storage_validation.py tests/test_storage_safety.py tests/test_daily_automation_orchestrator.py
bash -n scripts/review_gemini_chrome.sh
git diff --check
```

主線先前分組結果：Daily 52 passed；Gemini 原 4 passed＋8 subtests；affected preflight／runner／validation 22 passed；storage guard／orchestrator 105 passed＋39 subtests。

最終整組：**1 failed、183 passed、50 subtests passed，69.25 秒；不可宣告整組全綠**。失敗為既有 `test_late_normal_return_after_sample_deadline_fails_closed`：預期 samples 為 `[preflight, live]`，實際為 `[preflight, live, live]`；exit 70、STOPPED、`LIVE_SAMPLE_CADENCE_EXCEEDED`、restart denial 均符合預期。`app/storage_safety.py` 與該測試檔對 HEAD 無 diff。單獨重跑同一測試 1 passed，2.21 秒；屬目前觀察到的非穩定結果，未定位確切競態，也未用重跑通過覆蓋首次失敗。此項保留在後續驗證缺口，不擴修本輪未改的 guard。

主線 `bash -n` 與 `git diff --check` 通過。兩個 worker 的寫入循序進行，independent reviewer 全程唯讀；Daily 與 Gemini 各一次 repair1 後 local review GO。

## 候選 SHA-256

| 檔案 | SHA-256 |
|---|---|
| app/volume_indicators.py | 62a2c886d61a4dcd0c6a252564e32b8c896f45d1d12136b94e6b566ac9249aee |
| scripts/review_gemini_chrome.sh | 249a2521d5a024facc95670a43dd3883b51a69476bf81c213b8fb81ecfa1494f |
| scripts/run_external_review_host_runner.py | de07ca0c79b0a94814e600166100d7f9a6fb635d862649c7f49e434be13e2716 |
| scripts/preflight_external_review_providers.py | 3147cd4b9c995917fce251e8d8dc5bb532032da50b8f3b29dd2e4d04b84a661a |
| tests/test_volume_vwap_memory.py | 9491fbccbf56a9047feeba4a08772eb64c86a3cc3d713942bad2980aa1806031 |
| tests/test_gemini_probe_wakeup.py | 3f1004d11a1d006557aac83492ef01925f2ecf525ab200de2a407c292d2a2249 |

阻塞來源版本：ai-core `scripts/tmp_artifact_lifecycle.py` SHA-256 `d465b6be34d0dbc28c532da6c00774e2fdc81de6f59abc969a947bc35fabc2c4`；TOP10 `app/storage_safety.py` `7a74c41b618a0113dd21195845d75c5461e397ada7f653820de79d73df51a52e`，兩者本輪均未修改。

## 待完成，不得隱去

- 安全試跑入口修復及兩輪完整 ETL、容量／程序 RSS／swap／回收／停損證據。
- Gemini 候選 exact browser/profile 實機無送件 probe，以及所需自然週期。
- 每個 job 的明確 rollout authority、固定 runtime、marker 恢復條件及自然驗收。
- Retrain stale ranking 的既有資料交接契約與自然 provenance；未擅自跨 runtime sync。
- Actual external-review activation 與 external-send authority；目前仍 disabled。

回退：本輪僅工作樹候選與新增測試／文件，無 commit／push／部署。需要回退時只撤銷上述精確檔案的本輪 diff，保留原研究檔；禁止全工作樹 reset。

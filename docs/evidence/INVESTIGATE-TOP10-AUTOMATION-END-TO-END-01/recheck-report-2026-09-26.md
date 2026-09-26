# 全鏈重新裁決：回到 TOP10 故障與最小範圍

> 2026-09-27 容量整理：本目錄原始輸出與重現腳本已逐檔 SHA-256 核對後合併為 [證據壓縮包](raw-evidence-2026-09-27.tar.gz)。文中原始檔名為包內路徑；需重跑時先在本目錄執行 `tar -xzf raw-evidence-2026-09-27.tar.gz`，再依原說明操作。歷史驗證結果不變。

查核窗口：2026-09-26 23:54–23:57（Asia/Taipei），文件於跨日後收斂。延續原排查卡，沒有啟動 workload、瀏覽器 probe、原生 ES、提權 collector、清理、排程變更或部署。Foundation 容量感測曾在 sandbox 內回傳無效值；經允許在 sandbox 外重跑同一唯讀感測成功，沒有其他系統變更。

## 判定

真正的 operational blocker 是 **Daily 與 retrain-monitor 的容量停損及恢復驗證缺口**。Apple ES 不在目前 production 啟動鏈，也不是 9/9 或 9/26 事故的原因。它是為解決額外隔離試跑 harness 的巢狀停止／清理問題而選出的開發分支，Owner 已關閉。

既有 Daily／Gemini 本地修補仍在工作樹，六個交付檔 digest 與 9/22 記錄相同；沒有部署到固定 runtime。不能把「本地測試通過」「文件寫已完成」「launchd enabled」等同工作恢復。

## 現在四條鏈各自怎樣

| 鏈 | 現存部署／最新證據 | 判定 |
|---|---|---|
| Daily | `bb55fc4`，tracked clean；9/9 guard STOPPED 與 persistent marker 相符；launchd enabled，但 last exit 75。最後 daily OK/status/send 成功證據仍是 9/8 | 停損後持續拒絕重啟。排程設定存在，不代表仍在產生報牌 |
| provider preflight | 同 `bb55fc4`，未套本地 Gemini 修補；9/22、23、25、26 guard OK／兩 provider probe PASS。9/24 在 spawn 前因容量不足 NO-GO | 現在可 probe；9/21 的 Chrome -1712 仍是歷史故障，尚未有因果證據把它全部歸為冷頁面。PASS 不代表能送件／收到回答，也不等於自然驗收完成 |
| retrain-monitor | `8fe9366`，tracked clean，installed profile=`host_full`；9/24、25 啟動容量拒絕；9/26 02:02 guard STOPPED，新增 persistent marker。launchd last exit 70 | 已不再是前報告的「monitor 持續成功」。本次停止在產業研究程序；沒有執行模型 retrain 的證據 |
| actual external-review | disabled、未載入；installed 路徑仍指向 `<repo-root>` 開發 checkout | 尚未啟用的鏈，不是 provider PASS 就會自動執行。仍缺固定候選 runtime、依賴與外送／activation 准入 |

三個 enabled job 的 loaded argv 與 installed plist 一致。`natural_trigger_verified=false` 及 `NATURAL_ACCEPTANCE_PENDING` 仍存在；時刻符合排程與多次 OK 不自行補成自然來源證明。

## 容量事故：已確認與未確認

### Daily，9/9

原 guard 明確因 `HOST_RUNTIME_FREE_SPACE_BELOW_THRESHOLD` 停止，並留下不自動清除的 marker。跨門檻前後約 57 秒，raw free 約減 3.223 GB、全機 swap 約增 3.264 GB，而專案檔案只增約 32 KB；停止時仍在 ETL 量能指標計算，尚未到當日 ranking／payload／送出。

這支持記憶體／swap 壓力是重要來源，排除「當日已成功送出只是 status 過期」及「主要由本輪專案新檔寫爆」的解釋。但歷史紀錄沒有各程序 swap 分配，不能證明全機 swap 全由 Daily 造成。

本地 VWAP 候選已修正按股票複製寬表的配置浪費；前輪 20,000 列實際資料抽樣兩次數值完全一致，配置峰值約減 86.2%。它尚未經兩輪完整代表性 ETL 驗證，不能把局部配置改善等同整機容量事故已解。

### Retrain monitor，9/26 新事件

本次直接讀取原始 receipt 的 `process_rss_attribution`，不只看總 RSS：

- 02:01 的 `scripts/monitor_industry_momentum.py` RSS 為 **2,390,556,672 B**。
- 02:02 同一程序 RSS 為 **3,408,248,832 B**；被追蹤群組總 RSS 為 3,422,814,208 B。
- live 開始至停損 sample：raw free 26,951,438,336 → 23,667,089,408 B；swap 8,986,820,608 → 11,557,603,901 B；專案 bytes 3,242,043,952 → 3,242,044,711，僅增 **759 B**。
- 保留線為 24,510,719,590 B，確實被穿越。主機 swap 的完整程序歸因仍未取得。

來源鏈為 `daily_retrain.sh monitor` → `AutomationRunner._run_monitor()` → `monitor_industry_momentum.main()` → `research_industry_momentum_walkforward.main()`。這個 monitor 會重做整份 feature frame 的研究：讀 parquet、排序複製、計算 leave-one-out 因子、label 與逐日評分，並非只有讀健康狀態。高 RSS 已定位到具體子程序；精確哪一個配置造成峰值仍需有界重現，這輪沒有執行重型研究。

現存 `evaluate_resource_profile()` 的純政策已實際核對：`host_full` 不跳過 heavy monitor；`local_safe` 在未設 allow-heavy 時跳過它。這提供小範圍操作候選，但會停做產業研究部分，且 PSI／factor monitor 仍有自身成本；不能直接推論切換後全鏈必定安全。

### 目前主機餘裕

23:57 Foundation 唯讀量測：raw 約 **24.024 GB**，important-usage admission 約 **27.391 GB**；保留線約 **24.511 GB**。

- deployed guard 使用的 raw 口徑當下低於保留線約 **487 MB**。
- Foundation admission 的剩餘預算約 **2.880 GB**；若直接預留 TOP10 policy 預設 5 GiB，projected margin 是 **-2.488 GB**，不能准入。
- 這不是「任何小測試都不能做」，也不是允許靠縮小宣告預算啟動完整 ETL。實際 requested bytes 仍須由代表性工作與有效 policy 決定；該瞬間讀數不能挪作稍後啟動授權。

## 為何會偏到 Apple

1. 原始目標是找出 Daily、provider、external-review、monitor 的故障並做最小處理。
2. 本地 Daily／Gemini 候選完成後，為完整隔離試跑選用 ai-core tmp lifecycle 包 TOP10 guard。
3. 外層只追一個 process group，內層另開 session；外層先終止 guard 並清 root、內層後代仍活的反例確實成立。這是所選驗證組合的安全缺口，不能略過。
4. 接著工作改成跨 session 完整後代追蹤；kqueue／first-child ACK 反例未能排除，於是研究 native ES，再做離線原型，最後卡到 Apple 特殊權限。
5. **Mainline 的錯誤在於未先重算最小範圍，把所選 harness 的阻塞升格為整個 TOP10 修復必須先解的前提。** Gemini probe、既有記憶體數值檢查、monitor 資源政策與 runtime 狀態核對並不依賴 native ES。我也沒有在提出 Apple 路線前守住 Owner 不要平台等級擴張的界線。

原生 ES 從未進 production；離線 20+10 案只驗證合成事件邏輯，沒有解決任何當前 production 容量阻塞。保留成果但關閉路線，不把 Apple 帳號資訊繼續列為等待條件。

完整 ETL 的安全執行／收束仍是真缺口。**目前沒有已驗證、可以立即取代該 nested harness 的小方案**；不宣稱移除 wrapper、延長等待或取消 cleanup 就能安全。若原驗收在既有能力內不能完成，應明確列出這個限制造成的停止點，而不是再默默建平台。

## 文件與實際狀態落差

| 舊敘述 | 本次核對 |
|---|---|
| Gemini 持續 BLOCKED | 9/25、26 未修舊 runtime 已 probe PASS；不能把成功歸功於尚未部署的修補 |
| Monitor 成功，僅待自然驗收 | 9/26 已實際容量停損並留下 marker；最新 child status 的 OK 是 9/23 舊結果 |
| project sandbox defaults 800 MiB | **ai-core** 的 project policy default 是 800 MiB；**TOP10** 的 `config/project_sandbox_policy.json` default/hard 均是 5 GiB。helper 的 `--policy` 為必填，不會因 repo 名稱自動選檔；先前混稱不精確，下一次必須 pin 實際 policy 路徑及 digest。兩個設定本輪均未改 |
| Daily／Gemini 已修 | 僅 local candidate；六個交付檔 digest 未變，固定 runtime 未部署。既有整組測試仍保留 183 passed／1 failed 的紀錄，失敗單測重跑通過不抹除原未定位競態 |
| 舊 nested intake 卡 READY、等待 ai-core 授權 | 已被後續修復／反例／ES 關閉取代；Repair 2 成本早已核准，不再重問 |
| status JSON 顯示 OK | Daily 的 OK 是 9/8，monitor 的 OK 是 9/23；當前應同看 run_date 與 guard STOPPED／marker。原 guard 已提供停止證據，不能僅憑 stale 子程序 status 顯示健康 |

monitor 最新健康報告是 9/23 WARN，評估用 ranking 最新仍 9/7；報告成功不等於資料已更新。沒有擅自跨 runtime 同步資料。

## 最小後續處理順序

| 次序／責任 | 小範圍處理 | 必須保留的驗證與界線 |
|---|---|---|
| 1／TOP10 Mainline | 先以已定位的 Daily、monitor 記憶體及 raw／admission 預算重新鎖定恢復範圍。monitor 優先評估現成 local_safe 跳過重型研究，或只縮減該研究的欄位／複製成本；不新增監聽平台 | 不直接改 installed profile／清 marker；若跳過研究，明示減少的輸出與健康報告含義。原容量停損保留，不用降低閾值掩蓋問題 |
| 2／TOP10 Mainline | 保留已驗過的 VWAP 候選，先處理既有取樣測試的非穩定假說與完整 ETL 驗證計畫；每一步使用確定的版本、policy、輸入與預算 | 實際 ETL 的安全停止／回收未證明前不跑；不為繞過限制使用 legacy unsafe cleanup 或未管理 root。若需要改驗收方式，先以具體差異裁決，不冒稱原 A1–A8 已過 |
| 3／TOP10 Mainline | Gemini 暫以最新 probe 證據調整優先級；保留 cold-tab 修補候選，分開做 exact browser/profile 的有限無送件驗證 | 不因當前 PASS 就認定歷史 timeout 已解，也不把 ES 作為 browser probe 依賴；本輪不操作瀏覽器 |
| 4／TOP10 Mainline | 上述代表性容量與停損條件完成後，才提出逐 job 的固定 runtime 恢復；最後才處理 actual external-review | marker、部署、排程與外送保持原明確授權邊界；自然週期與 provenance 按既有條件，不另加平台級要求 |

ai-core 本次已確認停止 ES，只保留既有 lifecycle 缺口及歷史證據；沒有要求它新建另一套 runtime。所有協調與重新裁決由 TOP10 Mainline 承擔，不由 Owner 傳話。

## 可重跑證據與限制

- [當日快照](raw-evidence-2026-09-27.tar.gz)：75 個來源檔 identity、四 job installed／loaded argv、receipts、markers、provider 結果；只保留允許欄位與遮罩後 log。
- [分析／來源 digest](raw-evidence-2026-09-27.tar.gz)：monitor 原始 samples 與 RSS 歸屬、版本比較、純政策結果、12 項一致性斷言。
- [Foundation 有效讀數](raw-evidence-2026-09-27.tar.gz)；[sandbox 內失敗紀錄](raw-evidence-2026-09-27.tar.gz)。失敗沒有被當成容量零或 workload RED。
- `collect.py --output recheck-2026-09-26.json` 收集成功；`recheck_analysis.py` **12/12 通過**；`recheck_analysis.py --require-healthy` **exit 1**，Daily=false、monitor=false、provider_probe=true。這是可重跑的檔案健康拒絕訊號，**不是工作負載重現或恢復 GREEN**。
- 本輪沒有重跑不變的 20+10 離線原型或既有重型測試。9/9 全機 swap 來源、9/26 精確 allocation 熱點、Chrome 歷史 timeout 底層原因、完整 ETL 安全入口與自然來源驗收仍有明示未知。

從 TOP10 repo 使用既有 `.venv` 重跑分析：

```sh
UV_CACHE_DIR=/private/tmp/top10-investigate-uv-cache uv run --offline --no-sync python -B docs/evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/recheck_analysis.py
UV_CACHE_DIR=/private/tmp/top10-investigate-uv-cache uv run --offline --no-sync python -B docs/evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/recheck_analysis.py --require-healthy
```

本報告完成的是全鏈重新定位與主線更正；未宣告 TOP10 恢復。

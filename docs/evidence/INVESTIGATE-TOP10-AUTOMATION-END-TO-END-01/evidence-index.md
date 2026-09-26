# 證據索引與重跑方式

> 2026-09-27 容量整理：本目錄原始輸出與重現腳本已逐檔 SHA-256 核對後合併為 [證據壓縮包](raw-evidence-2026-09-27.tar.gz)。文中原始檔名為包內路徑；需重跑時先在本目錄執行 `tar -xzf raw-evidence-2026-09-27.tar.gz`，再依原說明操作。歷史驗證結果不變。

本研究於 2026-09-22（Asia/Taipei）執行。主快照為 15:58:07 UTC+8 與 16:02:54 UTC+8；不覆蓋當日尚未到來的 17:30/17:40。`observed_at_utc` 是收集開始時間，檔案依序讀取，不是原子 runtime snapshot。

## 已保存檔案

| ID | 檔案／JSON 欄位 | 用途 |
| --- | --- | --- |
| E01 | `snapshot.json.jobs`、`closing-snapshot.json.jobs` | 四份 installed plist、digest、完整 argv、loaded state、enabled mask、HEAD／branch／tracked 狀態；closing 另保留 loaded argv。external-review 無 loaded argv 是未載入，不是 argv drift |
| E02 | `snapshot.json.receipts.daily`、`markers.daily` | 9/8～9/9 guard、root marker、所有容量 sample；last sample 不代表最初 crossing sample，後者在 details |
| E03 | `details.json.incident_last_samples`、`incident_calculation` | crossing 前後程序 RSS／command、free／swap／project 增量；算法可重跑 |
| E04 | `details.json.daily_last_success`、`payload`、`rewrite`、`clawd_send_status_2026-09-08.json` | 同日 terminal steps、Top10 數量、Gemini API 改寫、Discord provider receipt；平台 ID 改保存 hash／存在與否 |
| E05 | `details.json.log_excerpts`、`september9_absence`、`stale_automation_status` | Daily 9/9 停止層、缺失產物、舊 OK 拒絕、preflight 同日覆寫 |
| E06 | `snapshot.json.provider_reports`、`receipts.external-review-preflight` | 18 個 dated provider reports、15 份 guard archives；9/8 有 manual；9/11/12 guard 沒 spawn，故無該日 provider report |
| E07 | `details.json.applescript_offset`、`source_seams` | source 文字還原 AppleScript 544:573；完全沒有呼叫 osascript／browser |
| E08 | `snapshot.json.receipts.retrain-monitor`、`details.json.monitor_*` | 14 guard archives、13 dated health reports、當下 monitor terminal artifact 與舊 ranking 日期 |
| E09 | 各 JSON `source_manifest` | 原始檔完整路徑、讀取內容 SHA-256、size、mtime_ns；snapshot 61 項、details 42 項，部分來源重疊，不應相加當唯一檔數 |
| E10 | `assertions.json` | 16 項一致性／反證斷言；3 項健康觀測均 false。只驗證檔案證据 |
| E11 | 下方系統唯讀查詢記錄 | OS log 無事件、APFS 統計、程序／session、lock 的可取得範圍與限制 |

日誌只保存需要的末段；provider 對話 URL、平台 channel/message ID 遮罩，不讀 credentials。`guard_log_tail` 只針對 daily/preflight/retrain-monitor，沒有保存 Fog log。原始 production 檔案未改動。

## 重跑指令

從 `<repo-root>` 執行；使用既有 uv＋.venv、不同步依賴。只讀既有 runtime／launchd，唯一寫入為本研究目錄（uv cache 指向 `/private/tmp/top10-investigate-uv-cache`）。再次收集會更新指定快照，因此若需保留歷史版本，先用既有 Git 或另存研究檔案，不覆蓋原始 production evidence。

```sh
UV_CACHE_DIR=/private/tmp/top10-investigate-uv-cache uv run --no-sync python docs/evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/collect.py --output closing-snapshot.json
UV_CACHE_DIR=/private/tmp/top10-investigate-uv-cache uv run --no-sync python docs/evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/details.py
UV_CACHE_DIR=/private/tmp/top10-investigate-uv-cache uv run --no-sync python docs/evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/assertions.py
UV_CACHE_DIR=/private/tmp/top10-investigate-uv-cache uv run --no-sync python docs/evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/assertions.py --require-healthy
```

本次 exit：collector=0、details=0、assertions=0（16/16）；require-healthy=1，因 marker 未清、Daily STOPPED、provider BLOCKED。`assertions.py` 是對本事故窗口的研究斷言；未來成功數或來源 hash 改變時，事故斷言可能合理轉 false，不是通用健康服務。只有更新快照才會反映新 runtime 狀態。

這些不是產品 regression suite，也未 import 產品模組。事故的 workload RED 未跑，標記 `REPRODUCTION_BLOCKED_BY_SCOPE`；需另一張卡取得隔離 ETL／adapter fixture 與必要 browser 定位權限。不得把檔案 RED/綠視為已驗證修復。

## 系統唯讀查詢與結果

```sh
date -Iseconds
git status --short
git worktree list
launchctl print-disabled gui/$(id -u)
launchctl print gui/$(id -u)/com.new-top10.daily
launchctl print gui/$(id -u)/com.new-top10.external-review-preflight
launchctl print gui/$(id -u)/com.new-top10.external-review
launchctl print gui/$(id -u)/com.new-top10.retrain
df -k <home>/TOP10-runtime-automation-bb55fc4
/usr/sbin/diskutil info /System/Volumes/Data
/usr/bin/log show --style compact --start '2026-09-21 01:59:30' --end '2026-09-21 02:02:00' --predicate 'process == "launchd" AND eventMessage CONTAINS "com.new-top10.retrain"' --info --debug
ps -axo pid,lstart,comm | rg 'Google Chrome$|WindowServer|loginwindow'
sysctl kern.boottime
/usr/sbin/lsof -n -P <home>/TOP10-runtime-automation-bb55fc4/logs/storage_safety/daily.lock <home>/TOP10-runtime-automation-8fe9366/logs/storage_safety/retrain-monitor.lock
```

- launchctl：三 enabled job 可讀，external-review exit=113／service not found；`print-disabled` 顯示 disabled。完整 plist 與命令結果摘要由 collector 保存，沒有存 inherited secrets。
- 15:56:42 `df`：Data volume `/dev/disk3s5`，總量 239,362,496 KiB、available 33,693,392 KiB。
- diskutil：APFS Data volume，container total **245,107,195,904 bytes**，container free **34,497,511,424 bytes**；volume used=177,840,787,456 bytes。Volume used 與 container free 的統計範圍不同，不能兩者相減歸因特定 writer。不是 Foundation important-usage 歷史值。
- Unified log：解除 sandbox 只讀限制後 exit=0，只有 header `Timestamp Ty Process[PID:TID]`，**0 matching rows**。範圍只有上述 150 秒、process=launchd、特定 label；不能據此推論無排程或所有保留歷史均已消失。
- ps：WindowServer PID=167、loginwindow PID=170，均 start `Mon Sep 7 09:32:33 2026`；Google Chrome PID=43192、start `Sun Sep 13 17:40:03 2026`。只有 comm，未讀瀏覽器內容或 profile 私密檔案。
- sysctl：boot `1788744738`，`Mon Sep 7 09:32:18 2026`。主機未重開不代表 job 沒 reload。
- lsof：無 stdout、exit=1，未見兩個 lock 的開啟者；不是透過 flock 證明，也沒有取得 lock。lock 檔存在本身不是 held。
- log／diskutil／ps／sysctl 的初次 sandbox 讀取受限，隨後使用 `require_escalated` 執行同一類唯讀查核；自動核准未拒絕。沒有控制面或 runtime mutation。

## Source 與 provenance 限制

查 CodeGraph 在 D、R 均回覆「no .codegraph」；依工具要求不再呼叫這兩個 project，改用 rg／原始碼。W 的 graph 查詢有結果，但不得拿 W 的 Python source 替代 D/R；本報告的 source seam 取自實際 D/R。W 只用於未啟用 external-review 所指向的 entrypoint。`details.json.source_seams` 保存行號與對应來源 digest。

`config/devflow_context_map.tsv` 在本 repo 不存在；已讀 `<home>/ai-core/config/devflow_context_map.tsv`、`compiled_lite.md`、root-cause-triage skill 與容量規則。卡片明示唯讀權限高於 skill 的重現／修復通用流程，因此本輪留存反證與限制，不冒稱 workload 已重現。

Receipt retention policy：archives 30 天、最多 256 檔、保護 newest 2；一般 log 14 天且容量輪替。這是配置，不代表所有較舊檔案已刪除。Daily archive 本次只見 9/8、9/9；source 明確保留 root receipt 並於 denial return 75，故缺後續 archive 不足以判 scheduler 沒觸發。D 的 9/1～7 provider artifacts 屬歷史資料，未建立其 deployment identity。

所有 snapshot digest 都於研究時才建立，僅用於後續重跑／比對；不宣稱它們是 incident 當時或自然週期當時已存在的獨立 digest anchor。

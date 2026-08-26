# TOP10-STORAGE-RUNAWAY-01 根因證據

取樣日期：2026-08-03；基線 commit：`e51c83d0f5e768768ed3d441e647d5fd72f9d537`。

## 已確認根因

主要根因是 fog research 的同日 quota 封存採用秒級時間戳，造成內容相同或高度重複的
JSON／Markdown 每一批都新增檔案：

1. `com.new-top10.fog-research-worker.plist` 的 `StartInterval` 為 900 秒。
2. `scripts/run_fog_research_worker.sh` 每次最多六批，呼叫
   `scripts/run_top10_fog_map_handoff.py`。
3. `run_top10_fog_map_handoff.py:235` 呼叫 `scripts/run_daily_research_quota.sh`。
4. 舊版 `run_daily_research_quota.sh` 以
   `autonomous_research_daily_quota_<date>_<HHMMSS>` 命名，再無條件 `cp` JSON／MD 到
   `artifacts/autonomous_research/run_outputs/`。
5. 當日主 artifact 本來就是固定檔名，秒級 archive stem 卻把每次同日執行變成永久新檔；
   當時沒有 retention mutation 或硬上限。

事故封存 `artifacts/archive/top10_stopped_runtime_20260801.tar.zst` 的唯讀統計：

- 全封存：14,295 個 regular files，898,100,293 bytes（未壓縮大小）。
- `artifacts/autonomous_research/run_outputs/`：3,084 檔、773,059,980 bytes，占未壓縮
  bytes 約 86.1%。
- `artifacts/harness_status/`：11,211 檔、125,040,313 bytes，是確認的次要放大來源。

修正後同一交易日只使用
`autonomous_research_daily_quota_<date>.json/.md`，後續週期原子層級雖仍為 copy，
但目標固定而覆寫，不再每 15 分鐘新增兩個永久 snapshot。跨日資料交由明列 retention
回收。

## 可證偽假說

| 假說 | 判定 | 證據 |
|---|---|---|
| H1：timestamped quota archive 是主要單向增長源 | confirmed | 事故封存 run_outputs 773,059,980 bytes／3,084 檔；舊碼每次產生新秒級 stem；bounded test 修正前兩週期留下 4 檔，修正後只留 2 檔 |
| H2：harness／replay 每 run-id 產物是次要放大源 | confirmed-secondary | 事故封存 harness_status 125,040,313 bytes／11,211 檔；現況 `artifacts/weekend_training/` 5,415 檔、約 205 MiB，已登記回收規則 |
| H3：launchd stdout／stderr log 是主要容量來源 | falsified-primary | 現況 `logs/` 約 16 MiB；最大可見 launchd fog log 約 1.4 MiB，遠小於事故 archive；仍改成 bounded guard log 消除未來風險 |
| H4：八條 active schedule 互相重疊是主要事故根因 | falsified-observed-primary | 原始碼已有 daily／fog／PM／external-review locks；2026-08-03 八條均 disabled，`pgrep` 無 TOP10 排程程序；新 guard 再加 per-job non-blocking lock |
| H5：可由停止後 swap 回落單獨證明記憶體 leak | falsified | 歷史 RSS/process-tree samples 不存在；目前 swap 只證明現況，不足以反推事故根因，因此 RSS／swap 防線已實作但 live 兩週期仍 NO-GO |

## bounded RED／GREEN

測試：
`tests.test_storage_safety.StorageSafetyRegressionTest.test_research_quota_archive_respects_hard_file_limit_across_cycles`

- RED：舊碼兩個 temp fixture 週期得到 4 個 archive files，斷言 `<= 2` 失敗。
- GREEN：固定同日 stem 後兩週期只留下 JSON＋MD 共 2 檔。
- harness 只使用 temp directory、fake Python 與兩次小檔寫入，沒有填磁碟或製造 swap。

## CodeGraph 與限域追查

isolated worktree 先同步 CodeGraph 至基線 SHA；index 為 734 files／14,898 nodes。
context query 沒有提供足夠精確 call chain，因此依規則改用限域 `rg`／原始碼逐段確認
八個 plist、wrapper、handoff、quota、replay、lock 與 output paths。根因結論建立在上述
source call chain、事故 archive 統計與 RED／GREEN harness 三者交叉證據，不依單次 `du`。

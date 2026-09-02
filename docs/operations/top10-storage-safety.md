# TOP10 排程容量安全操作手冊

## 目前結論

`docs/operations/top10-storage-policy.json` 目前將 `daily`、`external-review-preflight` 與
`fog-research-worker` 設為 `launch_verified=true`。其中 Fog 依 2026-09-02 至 2026-09-03
R18 外接 clean-room 兩個完整代表性週期、hard ceiling、零 unknown writes、process group
quiescence 與 lifecycle cleanup exit `0` 驗證；門檻未放寬。

其餘五個排程仍維持 `launch_verified=false`。這是刻意的 fail-closed 狀態：尚未完成
各 job 的兩個代表性完整週期，因此 repo 中的數字對這五個 job 仍只是 provisional ceiling，
不是 live 核准預算。

`launch_verified=true` 只解除各 job storage policy 的 pre-child fail-closed 原因；實際
載入、啟用、kickstart 或手動執行 live launchd 仍是外部控制面動作，必須另有 operator
授權。對仍為 `launch_verified=false` 的 job：

- 不得載入、啟用或手動執行 live TOP10 排程。
- guard 會在 child 啟動前以 `POLICY_NOT_LIVE_VERIFIED` 拒絕，exit code 為 78。
- 不得把 bounded fixture 的結果當成代表性 live 週期。
- 不得自動清除 `logs/storage_safety/restart_denied/<job>.json`。

## 排程入口契約

八份 repo plist 都先進入：

```text
/bin/bash scripts/run_with_storage_guard.sh <job> /bin/bash <原入口> [args...]
```

guard 會：

1. 取得單一 job 的 non-blocking lock，阻止重疊週期。
2. 檢查 persistent restart-denied marker。
3. 在 child 啟動前量測政策 scope、主機空間與 swap。
4. 先以可信 bootstrap leader 建成獨立 process group，鎖定 PGID、session 與 leader start
   token 後才啟動 child；週期內量測專案 bytes／檔案數、主機空間、process-tree RSS、
   swap、增長率與未登記寫入。
5. 正常結束與停損都驗證 target group 已 quiescent。leader 先退出但仍有 descendant 時會
   停止已驗證 group 並拒絕重啟；identity 不符時 fail closed，不會盲目對重用 PGID 送 signal。
6. 將 stdout／stderr 寫到最多 8 MiB、三份備份的 guard log；launchd 本身寫 `/dev/null`。
7. 停損後寫入 persistent marker，後續排程即使被外部喚起也只會 exit 75。
8. guard 內部量測／log 例外或 guard 收到 TERM／INT 時，同樣先停止尚在執行的隔離
   process group，再留下 marker；`.venv/bin/python` 不存在時直接 exit 69，不接受環境變數繞過。

## Validation-only 入口

代表性驗證使用 `scripts/storage_safety.py validate-run`，但它不屬於 production wrapper，
也不會修改 `launch_verified`。它只接受無 `.git` 的隔離 sandbox、root/job 相符且
`manual_only=true` 的 marker、sandbox 內非 symlink 的 input/output root、存在且 lexical path
任一 component 都不是 symlink 的 source input root，以及每次必填的 hard runtime。main
checkout、Codex worktree 或缺 marker 的呼叫都 fail closed。

`validate-run` 不再接受 `-- <任意 command>`。每次執行必須提供
`--entrypoint-contract <sandbox 內 JSON>`；manual marker 的
`trusted_entrypoints.<job>` 必須以 sandbox-relative path 與 SHA-256 登記該 contract。contract
schema 為 `top10-storage-validation-entrypoint.v1`，固定 `interpreter=python-isolated`，並 pin：

- 單一 sandbox 內、非 symlink 的 `.py` entrypoint 及其 SHA-256。
- 完整 argv；contract 自身的 digest 因此也固定所有動態輸入。
- 相符 job；未登記 entrypoint、digest／scope／job 不符一律 fail closed。

guard 只會組出固定的 `python -I <reviewed entrypoint> <pinned argv>`。raw shell、`-c`、eval
或呼叫端動態 command 沒有 submission seam，也不做可繞過的 substring／黑名單掃描。
contract 與 entrypoint digest 在 spawn 前再次驗證；verified entrypoint bytes 會 materialize 到
child 無法寫入的短命 execution copy，避免檢查與執行間被替換。

validation child 在 spawn 前必須通過 macOS `sandbox-exec` capability probe；Seatbelt policy
允許讀取 source／系統檔，但只允許寫入本次 sandbox。capability 不存在、probe 不能同時證明
sandbox write 成功與 scope 外 write 被拒絕，或 source 位於可寫 sandbox 內時，一律不啟動
真實 child。source root 另有最多 50,000 檔的 bounded 前後快照；若仍偵測到 mutation，會
寫入 persistent restart denial，receipt 不得為 `OK`。

相容性邊界：舊式 `validate-run ... -- /bin/sh -c ...`、`python -c` 或任意 argv remainder
現在會在 spawn 前拒絕。既有人工驗證若要重跑，必須先把 reviewed harness 實體化為 `.py`、
建立 digest-pinned contract，並由 manual marker 登記；不得為相容性恢復 raw-command bypass。

validation receipt 會保留 `validation_only=true`、production `launch_verified` 原值、resolved
roots、runtime/cache roots、hard runtime、全部 samples 與其 `preflight`／`live`／`final`
phase、容量／檔數／host-free／RSS／swap delta、observed growth、unknown writes 與 reclaim。
此入口不得接到 plist、日常 wrapper 或任何自動排程。

child 的 `TMPDIR`、uv／XDG／Matplotlib cache 與 joblib temp 都被收斂到
`logs/storage_safety/runtime/<job>/`。wrapper 不改寫 `HOME`，也不把下載型 cache
散落到其他專案。

## 門檻與停損

- 啟動前主機保留：`max(30 GiB, 15%)`。
- 執行中主機保留：`max(20 GiB, 10%)`。
- swap 指標讀不到即 fail closed。
- 任一 `live` sample 的 process-tree RSS 或必要 swap 指標讀不到即停損；`preflight`／`final`
  的空值不誤判，也不能補成 live evidence。
- 成功 receipt 至少要有一筆 child 在取樣前後都存活、RSS 與必要 swap 都有效的 `live`
  sample；快速 child 沒有這項證據時 fail closed。
- process-tree RSS 超過逐 job `max_process_tree_rss_bytes` 即停損。
- 相對本週期 preflight 的 swap 增量超過逐 job `max_swap_growth_bytes` 即停損。
- bytes／檔案數超額、未登記寫入、連續兩段增長率超過預估兩倍且將突破保留線、
  超過穩定時間仍單向增長、RSS 與 swap 同升，任一成立即停損。

每個 job 的 provisional `max_bytes`、`max_file_count`、每小時增長、尖峰、穩定、
回收與保留值，以 policy JSON 為唯一機器可讀來源。缺少兩週期實測時不得把
`launch_verified` 改為 true。

## 寫入面盤點

| 類型 | repo 內實際／受控路徑 | 契約 |
|---|---|---|
| 排名、狀態、報告 | `artifacts/`、`artifacts/harness_status/` | 納入每個相關 job 的 meter；已知可重建子路徑才可回收 |
| 研究輸出與封存 | `artifacts/autonomous_research/`、`run_outputs/`、`research_map/`、`research_reviews/`、`pm_review_cards/`、`research_decisions/` | 同日 quota snapshot 覆寫；14 天 retention／硬檔數與 bytes 上限 |
| replay／baseline／回測 | `artifacts/weekend_training/`、`artifacts/backtest/` | replay 7 天，其他已登記項目 14 天；未知檔不刪 |
| external review | `artifacts/external_review/` | 30 天；只限該目錄的明列規則 |
| 原始與清理資料 | `data/raw/`、`data/clean/`、`data/reference/`、`data/fundamentals/`、`data/fundamental_xbrl/` | 量測但不在本卡自動刪除 allowlist |
| 模型、checkpoint | `models/`、`artifacts/model_experiments/`、`artifacts/shadow/` | 量測但不在本卡自動刪除 allowlist |
| 日誌 | `logs/*.log`、`logs/*.err`、`logs/storage_safety/` | launchd 不再直接累積；guard log 8 MiB × 現行檔加三份備份 |
| cache／tmp／下載暫存 | `logs/storage_safety/runtime/<job>/cache/`、`tmp/` | 每 job 隔離、納入 meter，24 小時／2 GiB／20,000 檔上限 |
| build artifact | 排程 call chain 未發現獨立 build 目錄 | 未登記路徑一出現即停損；不能默認忽略 |
| database／WAL | 八個排程 call chain 未發現正式 DB／WAL writer | `.codegraph/` 不屬 live 排程；若 child 新增 DB／WAL 路徑必須先登記與實測 |
| screenshot／瀏覽器資料 | external-review 可能連接 provider，但本卡禁止操作瀏覽器 | 不在 cleanup allowlist；本卡沒有讀寫 cookie／profile／screenshot |
| open-deleted file | 無固定路徑；以 host `lsof +L1` 稽核 | 驗收時須確認沒有 TOP10 匹配；不得跨專案清理 |

`baseline_outputs` 只匹配 `baseline_harness_medium_window_replay_*`。unlock policy、review 與
verification control artifacts 不得被 replay reclaim 規則刪除；這項邊界有 regression test。

## 唯讀檢查

在 `<repo-root>` 執行：

```bash
.venv/bin/python scripts/storage_safety.py measure --job fog-research-worker
.venv/bin/python scripts/storage_safety.py reclaim --job fog-research-worker
```

第一個命令目前應回 `NO-GO`；第二個命令預設為 dry-run。不要在未核准情況加入
`--execute`。policy 驗證可用：

```bash
.venv/bin/python -W error::ResourceWarning -m unittest tests.test_storage_safety
bash -n scripts/run_with_storage_guard.sh scripts/run_daily_research_quota.sh
```

## 停損後處置

1. 保持八個 launchd job disabled，不 load、不 kickstart。
2. 保存 `logs/storage_safety/<job>_latest.json`、guard log 與
   `restart_denied/<job>.json`。
3. 查明 marker 中原因，確認主機保留線、專案 inventory、RSS／swap 與清理 allowlist。
4. 另開有審查證據的修復卡。marker 只能在根因修復、兩週期驗證、人工核准後由明確
   維運動作移除；本工具不提供自動 clear。
5. 重新啟用屬外部控制面變更，必須另取得明確授權並重跑 storage capacity gate。

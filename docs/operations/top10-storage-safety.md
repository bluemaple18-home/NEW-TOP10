# TOP10 排程容量安全操作手冊

> **2026-11-18：FOG 外接驗證接線已通過小型原生流程及兩名獨立審查。**
> 驗收涵蓋兩輪成功、child17 失敗、逾時、中斷、寬鬆外層／假 marker 拒絕，
> 並核對來源指紋、process-group quiescence、證據匯出與本輪暫存回收。
> 這解除本次隔離接線阻塞，不代表正式研究輸入已閉合或 production 已獲准；未啟用排程。
> 交付證據位於外接檢查目錄 `TOP10-STORAGE-LIFECYCLE-20261118/resume-fog/receipt.md`。
> 先前一次測試暫存回收未經標準 recovery gate，偏離紀錄仍保留，不由本次驗收追認。

### FOG exact-root 接線

舊 external-only 外層下重複 `sandbox_apply` 曾回 EPERM；新 opt-in 接線只在首次套用精確限制，
不跳過實際隔離證明，也不代表正式研究資料或 production 已放行。FOG launcher 必須使用
`--external-only --owned-root-writes-only`；未宣告者只留 admission 失敗摘要，
不建立 workload fixture。daily 與其他模式維持原入口，沒有全域改用 exact 模式。

首次 Seatbelt apply 只允許 owned root 與 `/dev/null` 寫入。既有外接 owner marker
保存真實 parent admission receipt、root／nonce／device／profile digest／expiry、
parent start identity 與 control-directory inode。child 原生重驗卷 UUID／mount、
parent ancestry 與既有 directory flock 的 Busy 狀態；不再次呼叫 APFS container sample。
容量仍由未受限 lifecycle parent 的原 admission、resource_check 與停損負責，沒有新 lease 或 heartbeat。
guard 另由實際繼承的 child 驗 owned 可寫、source／sibling／marker 拒寫；假 marker 不足以略過隔離。
guard 使用既有 libproc 接縫量測 identity／RSS／group，避免 strict 內無法 exec 的 setuid `/bin/ps`。

entrypoint 以不超過 64 KiB 的已核對 bytes 經固定 `python -I -B -c` 內部 bootstrap 執行，
argv 總量上限 128 KiB；CLI 仍不接受外部 raw `-c` 或 shell 作為 validation entrypoint。
child 只寫 root 內 `validation_evidence`（512 entries／8 MiB），由原 lifecycle 在 child 退出後
以 `--preserve validation_evidence` 匯出至 marker 綁定目的地，沒有手動 copy fallback。

```bash
source "$HOME/ai-core/config/toolchain_paths.sh"
export CHECK_OWNER=/Volumes/VibeCode/Development/TOP10-Checks/TOP10-STORAGE-LIFECYCLE-20261118
export TOP10_EVIDENCE_DESTINATION="$CHECK_OWNER/evidence/<唯一-FOG-receipt>"
export TOP10_EXTERNAL_VOLUME_ROOT=/Volumes/VibeCode
"$AI_CORE_DIR/.venv/bin/python" -B "$AI_CORE_DIR/scripts/tmp_artifact_lifecycle.py" run \
  --external-only --owned-root-writes-only --repo-root "$CHECK_OWNER" \
  --policy "$AI_CORE_DIR/config/project_sandbox_symlink_fixture_policy.json" \
  --purpose top10-fog-exact --max-bytes 268435456 --max-file-count 12000 --ttl-seconds 180 \
  --evidence-dir "$TOP10_EVIDENCE_DESTINATION" --preserve validation_evidence -- \
  /Users/mattkuo/TOP10new/.venv/bin/python -B \
  /Users/mattkuo/TOP10new/scripts/run_external_fog_revalidation.py
```

這是有限額驗證入口，不是正式 workload 容量建議。重現本輪小型 fixture 請從未受限 parent 執行
`resume-fog/native-runner.py success-1 <唯一標籤>`；同一 runner 支援 `success-2`、`failure`、
`timeout`、`interrupt` 與 `wide` 假 marker 負例，每輪先用 `sandbox-exec /usr/bin/true` 唯讀預檢 profile。
不可把 native runner 放進 pytest 的既有 sandbox 再 nested apply。
單元測試沿既有 `run-tests.sh` 分批；symlink fixture 不超過原 policy 的 8 個，不提高 quota。
所有失敗 acceptance 都保留。parser-failure 曾有一次直接 helper recovery 的偏離紀錄，
不得稱為標準 recovery PASS，也不得重用其腳本；後續保留／恢復由主線沿既有 CLI 裁決。

## 外接驗證與 runtime prepare（2026-11-18）

新檢查的資料、tmp/cache 與證據必須外接。source 可以唯讀留在內建；
`tmp_artifact_lifecycle --external-only` 的 `--repo-root` 是既有外接 Git owner，
其 Git common dir 也須外接，不能拿內建 source 的 linked worktree 假裝符合。
這是原有 lifecycle 的 ownership 要求，不要求複製 dirty source、搬 `.git` 或另建環境。
沒有合法 owner 時停止，改用既有合法外接 source／owner；禁止內建或 `/tmp` fallback。

以下是可長期使用的檢查命令；自行指定既有外接 owner、唯讀 source 與唯一 receipt。
`READ_SOURCE` 是要驗證的程式碼，`CHECK_OWNER` 只承擔檢查 ownership。
使用已有 Python，不執行 `uv sync`。含 symlink fixture 的測試須使用 `tmp_path`
（`owned/pytest`），遵守既有 policy 的數量與容量限制。

```bash
source "$HOME/ai-core/config/toolchain_paths.sh"
export READ_SOURCE=<唯讀-source-絕對路徑>
export CHECK_OWNER=<既有外接-Git-owner-絕對路徑>
export CHECK_RECEIPT=<唯一檢查名稱>
export PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
unset PYTEST_ADDOPTS PYTEST_PLUGINS
"$AI_CORE_DIR/.venv/bin/python" -B "$AI_CORE_DIR/scripts/tmp_artifact_lifecycle.py" run \
  --external-only --repo-root "$CHECK_OWNER" \
  --policy "$AI_CORE_DIR/config/project_sandbox_symlink_fixture_policy.json" \
  --purpose top10-check --max-bytes 838860800 --max-file-count 50000 --ttl-seconds 300 \
  --evidence-dir "$CHECK_OWNER/evidence/$CHECK_RECEIPT" --preserve evidence -- \
  /bin/bash -ec '
    mkdir "$TMP_ARTIFACT_ROOT/evidence"
    cd "$READ_SOURCE"
    .venv/bin/python -B -m pytest -q -p no:cacheprovider \
      --basetemp "$TMP_ARTIFACT_ROOT/pytest" "$@" \
      >"$TMP_ARTIFACT_ROOT/evidence/pytest.log" 2>&1
  ' top10-check tests/test_storage_lifecycle_boundaries.py
```

daily 手動 CLI 可直接委派同一 helper；source/snapshot 只讀，payload 放在受管 root。
`--evidence-dir` 須為 owner 內的新路徑。已在 lifecycle 內的 runner 可明示
`--output-root`／`--runtime-root`，但都須位於本輪 owned sandbox，runtime 在 output 內。
library 首次寫入也驗相同邊界；library 不清 caller 的 output，清理由外層 lifecycle 負責。

```bash
.venv/bin/python -B scripts/storage_validation/daily.py \
  --source-root "$READ_SOURCE" --snapshot-input <source內快照> \
  --run-date <YYYY-MM-DD> --cycle-id <唯一cycle> \
  --lifecycle-owner "$CHECK_OWNER" --evidence-dir "$CHECK_OWNER/evidence/<唯一receipt>"
```

daily 保留輸入／輸出指紋、有限大小 receipt 與 log tail，不保留完整 data 或 `.venv`。
delegated CLI 的 `receipt_path`／`receipt_sha256` 指向最終匯出位置，須等外層 exit 0
再讀取驗證；已受管但未指定匯出位置時回傳 owned/evidence 路徑，交外層保留。
receipt 數量超過 8 或單檔超過 1 MiB 會失敗，不能省略匯出後仍回 OK。
訊號中斷可能只留 `STARTED` 摘要；這不是成功證據，須連同 lifecycle exit／cleanup 結果判讀。
FOG 的 shared-source、原生隔離與證據路由已通過上述小型流程驗收，必須使用 exact-root 入口。
`TOP10_EVIDENCE_DESTINATION` 須為既有外接父目錄下的新目錄，
同一 owner 下的 `--preserve validation_evidence` 可在失敗或訊號後保存其小型證據。
`storage_safety validate-run` 在 runtime/log/probe mkdir 前拒絕內建或非 owned 路徑，
正式 `run` 不受本次修改影響。

新 runtime 必須走 prepare，明示可重用的既有外接環境：

```bash
.venv/bin/python -B scripts/prepare_runtime_checkout.py \
  --source-root "$READ_SOURCE" --runtime-root <全新外接runtime> \
  --accepted-commit <完整40字元SHA> --environment-root <既有外接checkout>/.venv
```

prepare 使用 sparse detached worktree，只 checkout 程式碼；不複製 data、models、artifacts、
archive 或 `.venv`。環境以連結重用，其所屬 checkout 的 `uv.lock`／`pyproject.toml`
必須乾淨且等於 accepted commit；這個檔案契約不取代原環境安裝來源與套件驗收證據。
同 commit、同環境且乾淨才重用。不同 lock、內建路徑、未知目錄、dirty／ignored 工作均拒絕。
失敗僅撤回本輪建立、inode 未變且無 unique 工作的 worktree；其餘報 `KEEP_UNIQUE` 保留。
SIGTERM 在 add 後與環境連結後同樣走此撤回；尚未 checkout 且只有 `.git` 的本輪空殼，
核對 Git 身分且確認 index／index.lock 均不存在，才允許 `worktree remove --force`。
未知 index 可能含唯一 staged 工作，必須 `KEEP_UNIQUE`；不能只靠工作目錄沒有檔案判斷。
每個 Git writer、環境連結與清理前，均重新驗證外接 lexical path 與本輪原 device/inode；
發現 symlink 或 inode 替換即停止，不繼續 sparse-checkout／checkout。
此步不建立環境、不啟用服務，也不代表 production canary 已通過。

`setup_launchd.sh` 另外要求 `TOP10_RUNTIME_ENV`，並由 validate CLI 重驗 prepare 契約。
啟用服務仍須獨立授權及既有容量／canary 驗收；本入口不能攔截任意 raw shell。
既有 `scripts/test_with_shared_runtime.sh` 的三個 allowlist 節點不擴張，其他檢查用上述原生 lifecycle 命令。

## 歷史 policy 狀態（不代表 production 已重新核准）

`docs/operations/top10-storage-policy.json` 目前將 `daily`、`external-review-preflight` 與
`fog-research-worker` 設為 `launch_verified=true`。此欄位不能擴張本頁頂端的驗收範圍或取代部署授權。
其中 Fog 的歷史依據為 2026-09-02 至 2026-09-03
R18 外接 clean-room 兩個完整代表性週期、hard ceiling、零 unknown writes、process group
quiescence 與 lifecycle cleanup exit `0` 驗證；逐 job 預算與 runtime 停損未放寬，啟動主機
基線則依現行全域 Rule 24 校正為 `10%`。

Fog 的 `meter_paths` 另明示 `artifacts/external_review/`：這是與
`external-review-preflight` 同一 checkout 重疊執行時的共用容量 scope，不代表 Fog 是該檔案
writer，也不擴成整個 `artifacts/`。既有 unknown-write gate、hard ceilings、cleanup allowlist
與逐 job `launch_verified` 均維持不變。

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

- 啟動前主機保留：主機總容量的 `10%`；不得另設較高固定 GiB 下限。
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
.venv/bin/python -B scripts/storage_safety.py measure --job fog-research-worker
.venv/bin/python -B scripts/storage_safety.py reclaim --job fog-research-worker
```

第一個命令目前應回 `NO-GO`；第二個命令預設為 dry-run。不要在未核准情況加入
`--execute`。policy 驗證可用：

```bash
# 測試請用本頁「外接驗證與 runtime prepare」的 lifecycle 命令，
# 將最後的 pytest target 改成 tests/test_storage_safety.py；不再裸跑 unittest。
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


## FOG 外接正式排程：2026-11-19 驗收更新

本節更新 FOG 的舊停用／固定 NO-GO 記錄；其他 job 的設定及狀態維持原狀。FOG 已恢復既有每 3600 秒的 LaunchAgent，`RunAtLoad=false`。兩輪驗證均為人工 `kickstart` 經原正式入口，不當作兩次自然週期，`cadence_verified=false`。

- **Launch**：既有 `com.new-top10.fog-research-worker`，WorkingDirectory 與 wrapper／worker 都指向外接 `TOP10-runtime-automation-ec08e84`。FOG＋directory 只讀無 mkdir 的環境層並驗完整 cache contract，直接交原 guard 持鎖後做容量准入／materialize；其他模式仍走原 toolchain。缺現有 `.venv` 即拒絕，不建立替代環境。
- **Doctor**：在既有外接 runtime 根目錄使用本頁 `measure`／dry-run `reclaim`；判斷實際運行另需讀當次 guard、terminal、map、quota 收據。若再遇 `EXTERNAL_CACHE_MANAGED_ADMISSION_DENIED`，讀 `internal_error.causes` 的型別／錯誤碼／白名單來源位置；不保存例外原文或環境值。
- **Drive**：runtime、data、`.venv`、輸出、cache、TMP 與驗證證據均在已核對 UUID 的外接卷，缺卷／身分漂移拒絕，沒有 `/tmp` 或內建 payload fallback。來源碼可在內建唯讀使用。此 legacy worktree 的來源 Git 登記／common-dir 仍屬內建主 repo，production child 無此寫入 grant；真正 lifecycle owner 的 common-dir 在外接。不得把 legacy runtime 當作 `--external-only` 驗證 owner，也不為此搬動主 repo。指定內建離線回復原件保留。
- **Evidence**：外接 `TOP10-Checks/FOG-LIVE-REPAIR-20261119/activation8/` 與 `repeat-normal-1/`。原入口 invocation 為 `fog-research-worker-20261119T094107Z-63648`、`fog-research-worker-20261119T095351Z-70193`，兩者 child exit 0、群組 quiescent、terminal valid、full map 46 項通過、有效 live samples 各 4／5 筆，unknown／unmetered writes 均空。觀測峰值 RSS 128827392／130252800 bytes，swap delta -25165824／-16777216 bytes，登記輸出各增加 98021 bytes；業務結果為真實 `PARTIAL_NO_MORE_WORK`／`queue_empty`，不算重型計算。
- **Cleanup**：驗證臨時根由原 lifecycle 回收，保留小型 `validation_evidence`、receipt／hash／log。備份、回復原件、共用封存、正式必要資料及未提交修改保留；未知根與 dirty root 不回收。本入口邊界不宣稱攔截任意 raw shell。

原停損的實測原因是 Seatbelt child 無法執行 `ps` 確認鎖身分，導致 worker 退出且沒有有效 live 樣本；已重用既有 libproc 身分接點，未知 owner 仍保留。後續針對實際鏈的 native projection／map bootstrap、ledger parent literal create、原錯誤碼傳遞及唯讀 JSON heredoc temp 問題有各自回歸證據。FOG 已使用既有 native ledger，`data/research/research_ledger.duckdb`、其 WAL 與 `.research-ledger-rebuild` 均已登記及計量；只補父目錄必要 create，不授予整個 research 目錄寫入。

共用 cache 仍維持 2 GiB／50000 檔；FOG 登記輸出 2 GiB／30000 檔，RSS／swap 原 hard ceilings 與原生量測期限均未放寬。計算版 `546901c1b432619cf34aaa34dff98c9ee7ec50f3d4b726f78110d61eeb105c8d` 的兩次代表性計算、中途 INT 及同根兩 poll 保留原版本主張；後續控制／讀取／診斷差異由 focused tests 與以上兩輪實際入口補驗，不把舊重型證據宣稱成新 hash 重跑。

已知限制：OP7 曾在 live 期間因共用 cache 准入拒絕停損，當時舊收據未保留內層原因；前景／背景純讀取及後續兩輪正式入口均未重現。此次新增有界 cause metadata 供再次發生時追查，並保留原拒絕／停止機制，不宣稱該瞬時根因已閉合。CC 單次 packet-only Opus/xhigh 審查逾時，沒有有效 verdict，未列為驗收通過；本次採兩名獨立原生 reviewer 與實際收據裁決。

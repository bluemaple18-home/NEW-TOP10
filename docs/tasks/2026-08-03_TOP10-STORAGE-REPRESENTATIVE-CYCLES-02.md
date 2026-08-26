---
id: TOP10-STORAGE-REPRESENTATIVE-CYCLES-02
chain_id: TOP10-STORAGE-RUNAWAY
parent_card: docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md
parent_candidate: ad7eea3dd2756875c8143f6caf2c71e6e41bb9be
status: ready_for_review
blocker: REPRESENTATIVE_CYCLES_INCOMPLETE
blocker_detail: 八個 job 未全部完成兩個代表性完整週期；global 維持 NO-GO、launch_verified=false、launchd disabled。逐 job 原因與 machine receipts 見本卡 evidence path。
type: acceptance-implementation
priority: P0
owner: Codex visible isolated worktree
role: implementation
cycle: 2
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 代表性 workload 會接觸八條排程入口、真實資料與主機容量／RSS／swap；錯誤執行可能再次耗盡主機資源，因此必須以最高隔離、逐 job 停損與 fail-closed 證據施工。
allowlist:
  - app/storage_safety.py
  - scripts/run_with_storage_guard.sh
  - scripts/storage_safety.py
  - scripts/verify_*.py
  - tests/test_storage_safety.py
  - tests/**storage**
  - docs/operations/top10-storage-policy.json
  - docs/operations/top10-storage-safety.md
  - docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/**
  - docs/tasks/2026-08-03_TOP10-STORAGE-REPRESENTATIVE-CYCLES-02.md
forbidden_scope:
  - artifacts/**
  - data/**
  - models/**
  - main checkout 的未提交檔案
  - 瀏覽器、cookie、登入憑證與外部 provider 控制面
  - 其他專案、使用者文件與歸屬不明檔案
  - launchd load、enable、kickstart、restart 或重新載入
  - merge、push、deploy、發布報牌或傳送外部訊息
evidence_path: docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/
verification:
  - 每個可安全執行 job 的兩個代表性完整週期 receipt
  - 專案 bytes／檔案數、主機 free space、process-tree RSS 與 swap 前後差值
  - 一小時、一天與保留期峰值推估
  - 實際回收與隔離停損演練
  - affected tests
  - full pytest or explicit environment gap
  - git diff --check
---

# TOP10-STORAGE-REPRESENTATIVE-CYCLES-02｜八 job 代表性兩週期與解除 NO-GO 證據

## Root question

在所有 live launchd job 持續停用、主 checkout 與外部控制面完全不受影響的條件下，能否以隔離、可停止、可回收的方式，為 TOP10new 八個 job 補齊兩個代表性完整週期，讓容量預算由 provisional 轉成有實測依據的逐 job `PASS`／`NO-GO`？

## 起始狀態與授權邊界

- 從 parent candidate `ad7eea3dd2756875c8143f6caf2c71e6e41bb9be` 接手；先確認本卡與 parent evidence 可讀，且目前 worktree 為獨立、乾淨的新 worktree。
- 使用者已授權本卡繼續執行「排程保持 disabled 下的 guarded manual representative cycles」。這不包含啟用 launchd、部署、發布、外部 provider 寫入、瀏覽器操作或跨專案清理。
- 八個 production policy 目前必須是 `launch_verified=false`；不得用 bounded fixture、單次成功或主機目前空間充足取代兩個代表性完整週期。
- parent 已完成根因修正、bounded RED／GREEN、隔離停損、fixture 回收與 12 個 storage tests；本卡只補代表性執行與由其發現的最小必要修正，不重做已封存的根因調查。
- live launchd 全程保持 disabled。若任何 job 不是 disabled、已有 TOP10new workload 在跑，或無法證明隔離，立即停止並判 `NO-GO`。

## 任務目標

1. 建立不依賴 production `launch_verified=true` 的明確 validation-only 入口，讓代表性週期只能由人工命令、獨立 worktree、單一 job 串行啟動；不得讓此入口能被 launchd 或日常 wrapper 誤用。
2. 對每個可在既定邊界內安全執行的 job 跑兩個完整代表性週期，保留原始 samples 與 receipt，不得並行。
3. 以實測修訂逐 job 的 bytes、file count、每小時增長、尖峰視窗、穩定／回收時間與保留期預算；未知值不得填猜測數字。
4. 實際觸發一次 allowlisted 回收與一次隔離停損，證明其他專案、主 checkout、瀏覽器和獨立程序不受影響。
5. 產出逐 job 與全域判定。只有全部必要證據齊全才可提出解除 `NO-GO`；本卡不得啟用任何排程。

## 八個 job

- `daily`
- `retrain`
- `reference`
- `fog-research-worker`
- `pm-research-harness`
- `external-review`
- `external-review-preflight`
- `baseline-harness`

實際 job key 以 `docs/operations/top10-storage-policy.json` 為準。若名稱或集合不同，先留下差異證據並停在 `NO-GO`，不得自行增刪 production job 來迎合卡片。

## 強制執行順序

### Checkpoint 0｜Preflight 與隔離設計

1. 先查 CodeGraph，再由 source 確認 storage guard、八個入口、policy loader、receipt 與 reclaim seam；CodeGraph 無結果才限域 `rg`。
2. 確認新 worktree 乾淨、parent SHA 正確、沒有 `index.lock`；不得在 main checkout 施工或提交其既存 dirty files。
3. 重新量測主機 free space、TOP10new project bytes／file count、swap、現有 TOP10new PID tree，以及八個 launchd disabled 狀態。
4. free space 低於 `max(30 GiB, 15%)`、swap 不可讀、存在不明 TOP10new 程序、任一排程非 disabled、或 stop-loss marker 狀態不明時，禁止啟動任何週期。
5. 真實 input 只能唯讀使用；所有 output、cache、tmp、log、receipt 必須收斂到本卡 worktree 或本卡專屬 temp root。不得 symlink 或重導寫入 main checkout 的 `data/`、`artifacts/`、`models/`。
6. 若現有程式無法把真實 input 與隔離 output 分開，先做最小 validation harness／path injection 與測試；若無法在 allowlist 內安全完成，停在 `BLOCKED / REPRESENTATIVE_ISOLATION_UNAVAILABLE`。

### Checkpoint 1｜逐 job 兩週期

每次只允許一個 job；每個週期都必須：

- 經 storage guard 啟動，具有 hard runtime、bytes、file count、RSS、swap、host reserve 與 growth-rate 上限。
- 啟動前、第一次寫入後、最長每五分鐘、週期結束與回收後取樣。
- 保存命令、resolved input/output roots、exit code、elapsed time、project delta、file-count delta、host-free delta、PID tree peak RSS、swap delta 與未登記寫入檢查。
- 第一週期未通過時不得跑第二週期；先保留 evidence，判斷是本卡內最小修正或獨立 fork。
- 任一停損條件成立立即停止該 TOP10new process group、留下 persistent restart denial，且不得自動 retry。
- 每個 job 兩週期後才可做一小時、一天與保留期峰值推估；推估後須保留至少 `max(20 GiB, 10%)` 主機空間。

### Checkpoint 2｜外部相依 job

- `external-review`、`external-review-preflight` 或其他會碰 browser、登入、付費 API、傳訊／寫入外部服務的入口，只可使用既有 offline、dry-run 或 provider-disabled 模式。
- 如果該模式不具代表性，該 job 必須維持 `NO-GO / EXTERNAL_AUTHORITY_REQUIRED`，不得登入、安裝 connector、讀 cookie、開瀏覽器或自行擴權。
- 不得為追求八 job 全綠而把 provider failure 吞掉、偽造 receipt 或把 fixture 當代表性 workload。

### Checkpoint 3｜回收、停損與政策提案

1. 在本卡專屬 output root 實際觸發一次 allowlisted reclaim；確認 bytes 與 file count 下降，scope 外 protected hashes 不變。
2. 以隔離 child process 演練一次容量或 RSS／swap stop-loss；確認只停止目標 process group，獨立程序與其他專案存活，後續重啟被拒絕。
3. 依兩週期 evidence 修訂預算。沒有兩週期的 job 仍須 `launch_verified=false`。
4. 即使八個 job 都有證據，本卡也只提交 candidate 與 `READY_FOR_REVIEW`；不得 load／enable／kickstart launchd。是否啟用排程是後續獨立外部控制面授權。

## 立即停手條件

- 主機 free space 跌破 `max(20 GiB, 10%)`。
- 實際 bytes／file count 超出 hard ceiling。
- 連續兩個取樣點的增長率超過預估 2 倍，且會在回收前越界。
- 超過穩定／回收時間仍單向增長。
- PID tree RSS 持續上升且 swap 同步異常增加。
- 發現未登記寫入、open-deleted growth、跨 worktree 寫入或 scope 外 mutation。
- 無法只停止肇因 TOP10new process group。
- 同一 blocker 連續三次。

觸發後保留證據，不得猜測性刪除或以重跑掩蓋；最終只能 `NO-GO` 或明確 `BLOCKED`。

## 驗收條件

### AC-1｜Validation-only 隔離

Given production policy 全部 `launch_verified=false` 且 launchd disabled
When 人工啟動 validation cycle
Then 只有本卡專屬 output root 可寫、production wrapper 不會繞過 gate、主 checkout 與其他專案 hash／狀態不變。

### AC-2｜兩個代表性週期

Given 單一 job 的代表性唯讀 input 與核准上限
When 依序完成兩個完整週期
Then 兩份 receipt 均含完整容量、檔數、free space、RSS、swap、growth、stability 與未登記寫入證據，且第二週期不出現無界累積。

### AC-3｜預算與峰值

Given 兩週期實測
When 估算一小時、一天與保留期最壞峰值
Then policy ceiling 有可追溯計算，回收前仍保留 `max(20 GiB, 10%)`；缺值或超限即該 job `NO-GO`。

### AC-4｜回收與隔離停損

Given 本卡專屬產物與隔離 target process group
When 觸發 reclaim 與 stop-loss
Then 可回收容量確實下降、只停止 target、restart 被拒絕，scope 外 protected state 不變。

### AC-5｜逐 job 與全域判定

Given 八個 job 的 evidence matrix
When 收卡
Then 每個 job 都有 `PASS` 或具原因碼的 `NO-GO`；只有八個 job 全部 `PASS` 才可提出 global `PASS`，否則 global 必須是 `NO-GO`。不論判定為何，launchd 都維持 disabled。

## 必要交付物

- `docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/preflight.md`
- `docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/job-matrix.md`
- 每個已執行週期的 machine-readable receipt 與 sample data。
- `docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/reclaim-and-stop-loss.md`
- `docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/verification.md`
- 精確 changed-file allowlist、完整 candidate SHA、測試結果、未驗證缺口與最終 `PASS`／`NO-GO`。

## 禁止事項

- 不得啟用、載入、kickstart、restart 或 reload 任何 TOP10new launchd job。
- 不得在 main checkout 執行代表性 workload、修改或提交其既存未提交檔案。
- 不得刪除或修改 production `data/`、`artifacts/`、`models/`；真實資料僅可作唯讀 input。
- 不得碰 MDreport、瀏覽器、cookie、認證、其他專案、使用者文件或歸屬不明檔案。
- 不得 merge、push、deploy、發布報牌、安裝外部 connector 或傳送外部訊息。

## 五行派工卡

- 任務 ID：`TOP10-STORAGE-REPRESENTATIVE-CYCLES-02`
- 卡片類型｜派工對象：`strict acceptance-implementation｜gpt-5.6-sol high`
- 請讀：`AGENTS.md`、本卡、parent card、`docs/evidence/TOP10-STORAGE-RUNAWAY-01/verification.md`、全域 `rules/24-storage-capacity-safety.md`
- 任務目的：在所有 live 排程持續停用下，以隔離 validation-only 路徑逐 job 補齊代表性兩週期、回收與停損證據，產出逐 job `PASS`／`NO-GO`。
- 證據路徑：`docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/`

## 施工結果（2026-08-03）

- 已建立只能在無 `.git` sandbox、manual marker 相符時使用的 validation-only 入口；production
  wrapper 仍以 `launch_verified=false` fail closed。
- 已補 hard runtime、process-tree RSS、swap-growth ceiling、resolved root、cache 收斂與完整
  receipt summary；hard-RSS stop-loss、restart denial 與 unrelated process isolation 已實測。
- 已修正 `baseline_outputs` reclaim 誤刪 unlock policy 的範圍缺陷並補 regression test。
- retrain scheduled monitor 完成兩週期；reference 自動 file-count stop；fog 隔離停止；PM cycle
  為空 workload；daily／external review 類因外部權限不執行；baseline 代表性 review gate 失敗。
- 逐 job 與 global 判定均為 `NO-GO`。八個 `launch_verified` 仍為 false，launchd 全程 disabled。
- affected storage tests 19 passed（16 subtests）；full pytest 為 652 passed、1 個 parent 已知 isolated evidence
  gap、270 subtests passed；`git diff --check` 通過。

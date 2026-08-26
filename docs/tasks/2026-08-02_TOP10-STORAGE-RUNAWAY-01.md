---
id: TOP10-STORAGE-RUNAWAY-01
chain_id: TOP10-STORAGE-RUNAWAY
status: no-go
blocker: REPRESENTATIVE_LIVE_CYCLES_NOT_RUN
blocker_detail: 修復、bounded 兩週期、隔離停損與回收測試已通過；八個 job 尚未各跑兩個代表性完整週期，policy 維持 launch_verified=false，live 排程不得啟用。
type: incident-remediation
priority: P0
owner: Codex isolated worktree
role: implementation
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 容量耗盡會使整台主機與其他專案失效，且涉及八條排程、程序記憶體、swap、artifact 與自動停損的跨模組契約。
allowlist:
  - scripts/**
  - app/**
  - tests/**
  - docs/operations/**
  - docs/evidence/TOP10-STORAGE-RUNAWAY-01/**
  - docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md
forbidden_scope:
  - artifacts/**
  - data/**
  - models/**
  - 瀏覽器資料、cookie、登入憑證與其他專案
  - 本機 launchd 載入、重啟或重新啟用
evidence_path: docs/evidence/TOP10-STORAGE-RUNAWAY-01/
verification:
  - bounded RED/GREEN regression test
  - 兩個代表性完整週期的容量、檔案數、RSS、swap 與回收證據
  - storage stop-loss dry-run and isolated-process drill
  - affected tests
  - git diff --check
---

# TOP10-STORAGE-RUNAWAY-01｜容量爆量根因修復與自動停損

## 問題與目標

TOP10new 曾使主機可用空間跌到約 5.24 GiB，並伴隨 `/System/Volumes/VM` swap 增長到約 38 GiB。事故期間無法證明輸出、log、cache、tmp、資料庫／WAL、子程序與 RSS／swap 的增長都有上限，也沒有可驗證的專案級自動停損。

本卡要找出可重現的根因，修正持續單向增長，並建立「允許預算內正常產出、禁止無上限增長」的容量契約。完成前不得重新啟用任何 TOP10new 排程。

## 已知事故證據

- 八個 launchd 任務目前全部停用：daily、retrain、reference、fog research worker、PM research harness、external review、external review preflight、baseline harness。
- 目前沒有 TOP10new 程序運行。
- 事故後 swap 曾約 38 GiB，之後回落到約 35 GiB；這只能證明停止後未再爆量，不能單獨證明根因已修復。
- 建卡時主機可用空間約 14 GiB，低於全域上線前門檻 `max(30 GiB, 15%)`，因此代表性重跑目前必須判定 `NO-GO`。
- main checkout 有兩個既存未提交檔案，屬使用者工作，禁止碰觸：
  - `scripts/build_weekend_universe_inventory.py`
  - `tests/test_weekend_universe_inventory_snapshot.py`

## 使用者故事

身為主機與 TOP10new 的維運者，我要讓每條排程與常駐功能只在可量測的容量預算內產出，超出預算或出現 RSS／swap 異常時只停止 TOP10new，以免拖垮整台電腦及其他專案。

## 必做範圍

1. 先查 CodeGraph，再以原始碼與 bounded harness 定位八個入口的寫入路徑、迴圈、子程序、重試、重疊執行與記憶體生命週期；不得只依檔名或單次 `du` 猜根因。
2. 建立一個可重跑、會在原缺陷下轉紅的最小測試訊號。測試只能使用 temp fixture 與硬上限，不得為了重現而真的填滿磁碟或製造大量 swap。
3. 列出所有寫入類型與實際路徑：輸出、log、cache、tmp、下載、截圖、資料庫／WAL、checkpoint、模型、build artifact、封存與 open-deleted file。
4. 以實測提出並落實每項功能的 `max_bytes`、`max_file_count`、每小時正常增長率、尖峰視窗、穩定／回收時間、保留期限、輪替／壓縮及專案內清理 allowlist。未知項目維持 `NO-GO`，不得臆造數字。
5. 修正已證實的根因，並防止重疊啟動、失控重試、未回收子程序、無界 queue／cache／log／artifact。只能修改經 CodeGraph 與實測確認在事故 call chain 內的 allowlist 檔案。
6. 建立專案級監控與 fail-closed 停損：至少量測專案 bytes／檔案數、主機可用空間、程序樹 RSS 與 swap；觸發時只停止 TOP10new 的 PID tree，並拒絕其自動重啟。
7. 實際驗證一次輪替／壓縮／清理可回收容量；只壓縮但保留原檔不算回收。

## 強制停損條件

任一成立立即停止 TOP10new 寫入並保持排程停用：

- 專案 bytes 或檔案數超過核准預算。
- 主機可用空間低於 `max(20 GiB, 10%)`。
- 連續兩個取樣點的增長率超過預估值 2 倍，且趨勢會在回收前突破預算或主機保留線。
- 超過預定穩定／回收時間仍持續單向增長。
- 程序 RSS 持續增加且 swap 同步異常增加。
- 發現未登記寫入路徑、無上限產物或清理失效。

## 驗收條件

### AC-1｜根因證據

Given 八個入口與其程序樹均已盤點
When 執行 bounded regression harness
Then 原缺陷在修正前可穩定轉紅，修正後轉綠，並留下入口、call chain、寫入路徑或記憶體增長的直接證據。

### AC-2｜容量契約

Given 每項會重複執行的功能
When 檢查其 storage policy
Then `max_bytes`、`max_file_count`、增長率、尖峰、回收時間、保留與 allowlist 全部有實測依據；缺一即 `NO-GO`。

### AC-3｜代表性試跑

Given 主機可用空間已回到至少 `max(30 GiB, 15%)`
When 以代表性資料執行兩個完整週期
Then 記錄前後專案占用、檔案數、主機空間、程序樹 RSS、swap、每小時增長率，以及一小時／一天／保留期峰值；推估後主機仍保留至少 `max(20 GiB, 10%)`。

若主機仍低於啟動門檻，只能完成 bounded tests；本卡狀態必須維持 `NO-GO`，不得用模擬數據宣稱已通過代表性試跑。

### AC-4｜隔離停損

Given 以 fixture 注入超額、異常增長、低磁碟與 RSS／swap 同升情境
When stop-loss 觸發
Then 只停止測試中的 TOP10new 程序樹，拒絕自動重啟，其他專案、瀏覽器與使用者檔案完全不受影響。

### AC-5｜回收與回歸

Given 測試產物已達輪替或保留條件
When 執行回收流程
Then allowlist 內容量確實下降、受保護檔案 hash 不變，相關測試與 `git diff --check` 全部通過。

## 禁止事項

- 不得重新載入、啟用或執行任何 live TOP10new launchd 任務。
- 不得重開機、清除 swapfile、刪除歸屬不明檔案或跨專案清理。
- 不得碰 MDreport、Chrome／瀏覽器認證、cookie、使用者文件或其他專案程序。
- 不得修改或提交 main checkout 的既存未提交變更。
- 不得 merge、push、deploy 或發布報牌結果。

## 交付物

- 根因與 falsified hypotheses。
- 精確 changed-file allowlist 與 candidate commit SHA。
- RED／GREEN 測試證據。
- 寫入盤點、容量預算、監控、停損與回收證據。
- 最終判定只能是 `PASS` 或 `NO-GO`；在代表性兩週期與停損演練完成前必須是 `NO-GO`。

## 五行派工卡

- 任務 ID：`TOP10-STORAGE-RUNAWAY-01`
- 卡片類型｜派工對象：`strict incident-remediation｜TOP10new isolated worktree`
- 請讀：`AGENTS.md`、本卡、全域 `rules/24-storage-capacity-safety.md`
- 任務目的：找出並修正持續容量／RSS／swap 增長，建立專案級容量預算、監控、回收與隔離停損；live 排程維持停用。
- 證據路徑：`docs/evidence/TOP10-STORAGE-RUNAWAY-01/`

## 施工結果（2026-08-03）

- 已確認主要根因：fog handoff 反覆執行 daily quota，而 quota wrapper 以秒級時間戳無條件
  複製同日 JSON／MD；事故 archive 的 `run_outputs` 為 3,084 檔、773,059,980 bytes。
- 已把同日快照改為穩定檔名；bounded harness 由舊版兩週期 4 檔 RED，轉為修正版 2 檔 GREEN。
- 八個 repo plist 全部先進 storage guard；guard 提供 per-job lock、project bytes／file count、
  host reserve、process-tree RSS、swap、未登記寫入、bounded log、allowlisted reclaim、
  isolated process-group stop 與 persistent restart denial。
- 已完成兩個 bounded guard 週期、隔離停損與實際 fixture 回收；未對 live artifacts 執行清理，
  未載入或啟用任何 launchd job。
- AC-3 的八 job 代表性 live-like 兩週期尚未獲授權執行，因此最終判定維持 `NO-GO`。

### 精確 changed-file allowlist

- `app/storage_safety.py`
- `scripts/com.new-top10.baseline-harness.plist`
- `scripts/com.new-top10.daily.plist`
- `scripts/com.new-top10.external-review-preflight.plist`
- `scripts/com.new-top10.external-review.plist`
- `scripts/com.new-top10.fog-research-worker.plist`
- `scripts/com.new-top10.pm-research-harness.plist`
- `scripts/com.new-top10.reference.plist`
- `scripts/com.new-top10.retrain.plist`
- `scripts/run_daily_research_quota.sh`
- `scripts/run_with_storage_guard.sh`
- `scripts/storage_safety.py`
- `scripts/verify_daily_publish_workflow.py`
- `scripts/verify_pm_research_harness_loop.py`
- `scripts/verify_resource_guard.py`
- `scripts/verify_scheduler_ownership.py`
- `tests/test_storage_safety.py`
- `docs/operations/top10-storage-policy.json`
- `docs/operations/top10-storage-safety.md`
- `docs/evidence/TOP10-STORAGE-RUNAWAY-01/root-cause.md`
- `docs/evidence/TOP10-STORAGE-RUNAWAY-01/inventory-and-budget.md`
- `docs/evidence/TOP10-STORAGE-RUNAWAY-01/verification.md`
- `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`

---
id: TOP10-STORAGE-FOG-REVALIDATION-03
chain_id: TOP10-STORAGE-FOG-REVALIDATION
parent_chain_id: TOP10-STORAGE-RUNAWAY
parent_candidate: a798a13785c505c73a005b7e045226f51f99dda9
status: ready_for_review
blocker: MISSING_VALID_LIVE_RESOURCE_SAMPLE
blocker_detail: Cycle 1 在 Seatbelt 拒絕 fog runner 的 /dev/null redirect 後於 2.39 秒內退出；沒有合格 live RSS/swap sample。依卡片禁止 retry 與 cycle 2，fog 維持 reason-coded NO-GO。
type: acceptance-implementation
priority: P0
owner: Codex visible isolated worktree
role: implementation
cycle: 1
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 單一 fog workload 曾觀測約 3.19 GiB process-tree RSS 與 1.32 GiB host-free 下降；本輪會實際建立隔離輸出並驗證 hard ceiling，錯誤執行仍可能造成主機容量或記憶體風險。
slice_id: SLICE-FOG-REVALIDATION-001
traces_to:
  - docs/tasks/2026-08-03_TOP10-STORAGE-REPRESENTATIVE-CYCLES-02.md#AC-1
  - docs/tasks/2026-08-03_TOP10-STORAGE-REPRESENTATIVE-CYCLES-02.md#AC-2
  - docs/tasks/2026-08-03_TOP10-STORAGE-REPRESENTATIVE-CYCLES-02.md#AC-3
  - docs/tasks/2026-08-03_TOP10-STORAGE-REPRESENTATIVE-CYCLES-02.md#AC-5
dependencies:
  - a798a13785c505c73a005b7e045226f51f99dda9 已取得 REVIEW_GO
  - fog-research-worker hard RSS、swap、bytes、file-count ceiling 已存在
  - validation-only trusted entrypoint contract 已取得 REVIEW_GO
blocking_edges: []
frontier: true
jira: not-applicable
jira_reason: 本卡是 repo 內 Codex visible task，不建立外部 Jira。
evidence_path: docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/
allowlist:
  - app/storage_safety.py
  - scripts/storage_safety.py
  - scripts/storage_validation/fog_research_worker.py
  - tests/test_storage_safety.py
  - tests/test_fog_storage_validation.py
  - docs/operations/top10-storage-policy.json
  - docs/operations/top10-storage-safety.md
  - docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/**
  - docs/tasks/2026-08-03_TOP10-STORAGE-FOG-REVALIDATION-03.md
forbidden_scope:
  - production data/**、artifacts/**、models/** 的寫入、刪除或清理
  - main checkout 的既有未提交檔案
  - daily、retrain、reference、pm-research-harness、external-review、external-review-preflight、baseline-harness 的 workload
  - 瀏覽器、cookie、外部 provider、connector、其他專案或使用者文件
  - launchd load、enable、kickstart、restart、reload 或 plist 安裝
  - merge、push、deploy、發布報牌或傳送外部訊息
verification:
  - trusted fog entrypoint RED／GREEN tests
  - capacity preflight 與 protected checkout hashes
  - 最多兩個串行 representative cycle receipts
  - project bytes／files、host free、process-tree RSS、swap、growth 與 stability samples
  - affected tests、full pytest 或精確 environment gap、git diff --check
---

# TOP10-STORAGE-FOG-REVALIDATION-03｜Fog hard-ceiling 兩週期重驗

## Root question

在 parent candidate 的 Seatbelt、trusted entrypoint、live metric-gap 與 process-group 修復全部通過 Review 後，`fog-research-worker` 能否在無 `.git` 的專屬 sandbox 中完成兩個代表性週期，且始終守住 bytes、file count、RSS、swap、host reserve 與 scope 邊界？

## Slice boundary

本卡只處理 `fog-research-worker`。其餘七個 job 保持既有 reason-coded `NO-GO`，不得為了全域轉綠而混入本卡。

上一輪 fog 第一週期在約 186.5 秒時人工隔離停止，觀測：

- peak process-tree RSS：`3,191,783,424` bytes
- swap delta：`594,081,219` bytes
- host-free delta：`-1,322,807,296` bytes
- reclaim：`151,684,204` bytes／`5,964` files
- blocker：當時沒有 hard RSS／swap ceiling；ceiling 補上後未重跑

目前 policy 固定上限：

- `max_bytes = 2,147,483,648`
- `max_file_count = 30,000`
- `max_process_tree_rss_bytes = 4,294,967,296`
- `max_swap_growth_bytes = 2,147,483,648`
- `expected_growth_bytes_per_hour = 16,777,216`
- `sample_interval_seconds = 60`

本卡不得提高這些上限來追求 PASS。若實測顯示預算不足，只能保留證據並判 `NO-GO`。

## Checkpoint 0｜Provisioning、trace 與容量 preflight

1. 確認獨立 worktree、HEAD 等於 provisioning SHA、worktree clean、無 `index.lock`；不得使用 main checkout 施工。
2. 先查 CodeGraph 的 storage validation、fog runner、caller／callee；無結果才限域讀 source。
3. trace preflight：本卡四個 `traces_to` anchor 必須存在；dependency SHA 必須是目前 source ancestor。任一 dangling reference 即 `BLOCKED / TRACE_PREFLIGHT`。
4. 重新量測 host free、swap、TOP10new process、open-deleted files、八個 launchd disabled 狀態與 persistent restart-denied marker。
5. host free 低於 `max(30 GiB, 15%)`、swap 不可讀、存在不明 TOP10new workload、任一 launchd 非 disabled、或 marker 歸屬不明時，不得建立 sandbox或啟動 child。
6. 保存 main checkout 既有 dirty path 清單與 protected hashes；本卡只讀取核准的真實 input，不得修改、清理或提交 main 的任何檔案。

## Checkpoint 1｜Trusted fog entrypoint

1. 建立單一、可測試的 Python trusted entrypoint `scripts/storage_validation/fog_research_worker.py`；它只負責在 sandbox clone 內以固定環境執行現有 fog runner，不重寫 fog business logic。
2. entrypoint 必須由 marker 的 `trusted_entrypoints.fog-research-worker` 以 sandbox-relative contract path 與 SHA-256 綁定；contract 固定 job、entrypoint digest 與完整 argv。
3. 禁止 raw shell、`python -c`、eval、任意 command remainder 或呼叫端動態拼 command。entrypoint／contract／marker 任一 digest、job、scope 不符，必須在 spawn 前 fail closed。
4. sandbox 由 reviewed candidate 建立且不得含 `.git`。若需要代表性真實 input，只能以 bounded copy 收斂到 sandbox；禁止 symlink、bind mount 或把 output 指回 main。
5. `.venv`、cache、tmp、logs、artifacts 與所有 child write path 必須位於 sandbox。source/main 只作受保護唯讀輸入；Seatbelt capability/probe 缺失即停止。
6. 先做 RED／GREEN：合法 entrypoint 可讀 sandbox input、只寫 sandbox output；raw command、digest mismatch、scope 外寫入與 TOCTOU 全部 fail closed。

若現有 fog runner 無法在不修改 business logic、且不寫回 main 的條件下由此 adapter 執行，停在 `BLOCKED / FOG_TRUSTED_HARNESS_UNAVAILABLE`，不得擴張 allowlist。

## Checkpoint 2｜最多兩個代表性週期

只允許串行，禁止 retry loop：

1. 先以 reviewed candidate 與核准真實 input 建立 bounded sandbox；copy 前先估算 bytes／files，確認完成 copy 與最壞 cycle 後仍保留 `max(20 GiB, 10%)` host free。
2. cycle 1 經 `validate-run --entrypoint-contract` 啟動。第一次寫入後、最長每 60 秒、child 結束與回收後取樣。
3. receipt 必須保存 command contract digest、resolved roots、elapsed、exit、bytes/files delta、host-free delta、peak process-tree RSS、swap delta、growth、stability、unknown writes 與 group quiescence。
4. cycle 1 只有在完整 workload、receipt `OK`、無 scope mutation、無 budget violation 且 protected hashes 不變時才可進 cycle 2。
5. cycle 2 使用相同 sandbox 與相同 pinned contract，驗證累積、輪替與穩定性；不得清空輸出後冒充第二週期。
6. 任一週期 STOP／BLOCKED／非代表性或超限後，立即停止該 group並留下 restart denial；不得跑下一週期、不得自動 retry。

## 立即停手條件

- project bytes 或 files 超過 policy hard ceiling。
- host free 低於 `max(20 GiB, 10%)`。
- live RSS／swap sample 缺失，或 RSS／swap 超過 hard ceiling。
- 連續兩個 sample 的 growth > 預估 2 倍且會在回收前越界。
- leader 退出但 descendant 未 quiescent、PGID identity 無法驗證或 unrelated process 受影響。
- 未登記寫入、scope 外 mutation、symlink、open-deleted growth 或 main protected hash 改變。
- 同一 blocker 連續三次。

停手後只保存 evidence 與 reason-coded `NO-GO`；禁止猜測性清理或提高預算重跑。

## Acceptance

### SC-001｜Trusted entrypoint

Given reviewed candidate 與無 `.git` sandbox
When 啟動 fog validation
Then 只有 digest-pinned Python entrypoint 可 spawn，所有 write 都留在 sandbox，main/protected state 不變。

### SC-002｜兩個代表性週期

Given cycle 1 完整通過
When 以同一 sandbox、同一 contract 執行 cycle 2
Then 兩份 receipt 都有完整容量、RSS、swap、growth、stability 與 group-quiescence evidence，且沒有無界累積。

### SC-003｜逐 job 判定

Given 本卡所有 evidence
When 收卡
Then fog 只能得到 `PASS_CANDIDATE` 或精確 reason-coded `NO-GO`；不得把 stop、空 workload、單週期或 fixture 當 PASS。

### SC-004｜Production 維持 fail closed

不論 fog 判定為何，production policy 的 `launch_verified` 必須維持 `false`，八個 launchd 必須維持 disabled。本卡只產出後續 policy proposal，不授權啟用。

## Deliverables

- `scripts/storage_validation/fog_research_worker.py`
- trusted entrypoint regression tests
- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/preflight.md`
- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/cycle-1.json`
- 若 cycle 1 通過：`cycle-2.json`
- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/verification.md`
- candidate commit、changed-file allowlist、affected/full tests 與 `git diff --check`

Machine receipt 每份須 bounded；不得提交 raw unbounded log，單份超過 2 MiB 時先保留必要 samples 與外部 temp artifact digest，不得把大量 runtime log 塞回 Git。

## 收卡狀態

- `READY_FOR_REVIEW / FOG_PASS_CANDIDATE`
- `READY_FOR_REVIEW / FOG_NO_GO_<REASON>`
- `BLOCKED / <REASON>`

strict 卡完成 candidate 後必須由主線建立獨立 Reviewer；implementation 不得自審、merge、push、deploy 或啟用排程。

## 施工結果（2026-08-03）

- 建立 digest-pinned `scripts/storage_validation/fog_research_worker.py`，固定 runner、argv、
  no-retry 與 sandbox-local HOME/cache/tmp/runtime paths。
- trusted entrypoint／storage affected suite `39 passed, 16 subtests passed`。
- cycle 1 fail closed：`MISSING_VALID_LIVE_RESOURCE_SAMPLE`；restart denial 已留下，cycle 2 未執行。
- bounded receipt：`docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/cycle-1.json`。
- 最終狀態：`READY_FOR_REVIEW / FOG_NO_GO_MISSING_VALID_LIVE_RESOURCE_SAMPLE`。

## 五行派工卡

- 任務 ID：`TOP10-STORAGE-FOG-REVALIDATION-03`
- 卡片類型｜派工對象：`strict acceptance-implementation｜gpt-5.6-sol high`
- 請讀：`AGENTS.md`、本卡、parent job matrix、repair-2 verification、全域 `rules/24-storage-capacity-safety.md`
- 任務目的：建立 trusted fog adapter，僅在安全 preflight 通過後串行重驗最多兩個代表性週期。
- 證據路徑：`docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/`

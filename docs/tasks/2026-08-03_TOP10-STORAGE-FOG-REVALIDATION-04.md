---
id: TOP10-STORAGE-FOG-REVALIDATION-04
chain_id: TOP10-STORAGE-FOG-REVALIDATION-FRESH
parent_chain_id: TOP10-STORAGE-FOG-REVALIDATION
status: ready_for_review
blocker: SWAP_GROWTH_BUDGET_EXCEEDED
blocker_detail: "raw guard 已因 swap growth 超限停止；post-run evidence 另確認 live sample cadence violation。cycle 2、retry 與任何 fresh workload 均禁止。"
type: implementation
priority: P0
role: implementation
cycle: 1
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 這是修復後首次執行高 RSS fog 代表性 workload，需同時守住 trusted runner、Seatbelt、meter、RSS／swap 與兩週期停止條件。
source_candidate: 001e2dbe7f3a5743a3542c2a36680a3fac8a9fc9
review_status: REVIEW_GO
review_thread: 019fc6b3-94d8-7373-bdbc-07f82e048d88
traces_to:
  - REPAIR-TOP10-STORAGE-FOG-REVALIDATION-03-1#AC-1
  - REPAIR-TOP10-STORAGE-FOG-REVALIDATION-03-1#AC-2
  - REPAIR-TOP10-STORAGE-FOG-REVALIDATION-03-1#AC-3
  - REPAIR-TOP10-STORAGE-FOG-REVALIDATION-03-1#AC-4
forbidden_scope:
  - 使用或清除前次失敗 sandbox、restart denial 或 raw local evidence
  - 修改 fog business logic、storage policy ceilings、其他七個 job 或 production data/artifacts/models
  - 瀏覽器、cookie、外部 provider、connector 或其他專案
  - launchd load、enable、kickstart、restart 或 reload
  - 自動 retry、平行 cycle、merge、push、deploy 或發布外部訊息
allowed_paths:
  - docs/tasks/2026-08-03_TOP10-STORAGE-FOG-REVALIDATION-04.md
  - docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-04/
---

# TOP10-STORAGE-FOG-REVALIDATION-04｜Fresh fog 兩週期重驗

## Root question

在 trusted runner、exact `/dev/null` Seatbelt capability、registered-write meter invariant 與固定
bytecode policy 全部取得 `REVIEW_GO` 後，`fog-research-worker` 能否在全新、無 `.git` 的專屬
sandbox 中完成兩個代表性完整週期，並始終守住 bytes、file count、RSS、swap、host reserve、
write scope 與 process-group 邊界？

## 不可混淆的前代狀態

- 前次 `TOP10-STORAGE-FOG-REVALIDATION-03` 在 2.39 秒因 `/dev/null` 被 Seatbelt 拒絕而
  `NO-GO / MISSING_VALID_LIVE_RESOURCE_SAMPLE`；cycle 2 未執行。
- 前次 sandbox、contract、marker、restart denial 與 executed digest 只作唯讀 evidence；本卡不得
  清除、修改、複製或復用。
- Final reviewed source 是 `001e2dbe7f3a5743a3542c2a36680a3fac8a9fc9`；它封住
  `BASH_ENV`／runner swap、保留 `$0`／cwd／exit semantics、精確允許 `/dev/null`、補上
  `REGISTERED_WRITE_OUTSIDE_METER`、meter `artifacts/host_runner`，並固定
  `PYTHONDONTWRITEBYTECODE=1`。
- 本卡只重新判定 `fog-research-worker`。其他七個 job 與 production 全域狀態保持 `NO-GO`。

## 固定政策上限

- `max_bytes = 2,147,483,648`
- `max_file_count = 30,000`
- `max_process_tree_rss_bytes = 4,294,967,296`
- `max_swap_growth_bytes = 2,147,483,648`
- `expected_growth_bytes_per_hour = 16,777,216`
- `sample_interval_seconds = 60`
- runtime host reserve：`max(20 GiB, 10%)`

不得提高、繞過或重解釋上限來追求 PASS。

## Checkpoint 0｜Fresh preflight

1. 確認 formal task、獨立 worktree、provisioning HEAD、clean state、無 `index.lock`；source candidate 必須是 HEAD ancestor。
2. CodeGraph 先查 trusted entrypoint、fog runner、Seatbelt、meter 與 caller/callee；失敗才限域 source fallback。
3. 四個 repair trace anchors 必須存在；reviewed SHA 與 `REVIEW_GO` thread 必須可核對。
4. 量測 host free、swap、TOP10 workload、open-deleted files、八個 launchd disabled/not-loaded、main dirty paths與 protected hashes。
5. host free 低於 `max(30 GiB, 15%)`、swap 不可讀、存在不明 workload、任一 launchd 非 disabled、或舊/new marker ownership 不可區分，立即 `BLOCKED / PREFLIGHT`。
6. 保存前次 sandbox 路徑與 marker digest作唯讀對照；不得刪除或把它當 fresh input。

## Checkpoint 1｜Fresh sandbox、contract 與 capability

1. 建立新的唯一 temp sandbox；不得含 `.git`、symlink、bind mount 或 output redirect 回 main。
2. reviewed tracked source、main `.venv` 與核准代表性真實 input 只作 bounded copy；copy 前估算 bytes/files，copy 後仍須保留 runtime host reserve。
3. 不複製前次 sandbox 的 logs、storage-safety runtime、marker、restart denial或其他 local-only evidence。
4. marker 的 source SHA、job、contract path/digest、entrypoint digest、runner digest 與 sandbox root 必須全部 fresh 且一致。
5. 在不執行 fog workload的前提下，先跑 reviewed regression suites與 confinement probe：hostile env、runner bytes、`$0`/cwd、bytecode、exact `/dev/null`、scope outside、meter invariant。
6. 任一 digest、Seatbelt probe、freshness、write-root 或 capacity gap 即停止，不得啟動 cycle。

## Checkpoint 2｜最多兩個代表性週期

只允許相同 fresh sandbox、相同 pinned contract 串行執行；禁止 retry loop：

1. cycle 1 經 validation-only `validate-run --entrypoint-contract` 啟動；第一次寫入後、最長每 60 秒、child exit 與回收後取樣。
2. receipt 保存 command/contract/entrypoint/runner digest、resolved roots、elapsed、exit、bytes/files、host-free、peak process-tree RSS、swap delta、growth、stability、unknown writes、registered-unmetered writes與 group quiescence。
3. cycle 1 只有在完整 workload、receipt `OK`、至少一筆有效 live resource sample、scope/protected hashes不變、無 budget violation時才可授權 cycle 2。
4. cycle 2 必須沿用同一 sandbox與同一 contract；不得清空 outputs、重建 input或改 digest冒充第二週期。
5. cycle 2 驗證累積、輪替回收與穩定性；兩個週期都必須代表性完整。
6. 任一 STOP／BLOCKED／非代表性／超限後立即終止 target group、保留 fresh restart denial；不得跑下一週期或自動重試。

## 立即停手條件

- bytes/files、RSS、swap或host reserve 超限。
- live RSS/swap sample 缺失，或 child exit 前從未形成有效 live sample。
- 連續 growth sample 顯示回收前將越界。
- leader exit 但 descendant 未 quiescent、PGID identity gap或 unrelated process受影響。
- `UNREGISTERED_WRITE_PATH`、`REGISTERED_WRITE_OUTSIDE_METER`、symlink、open-deleted growth、source/main protected mutation。
- entrypoint/runner/contract/marker digest drift、shell startup injection、source-tree `__pycache__`/`.pyc`。
- 同一 blocker 連續三次。

停手後只保存 bounded evidence 與 reason-coded `NO-GO`；禁止猜測性清理、提高上限或重跑。

## Acceptance

### SC-001｜Fresh trusted execution

Given reviewed source 與 fresh sandbox/contract/marker
When validation 啟動
Then 只有 pinned entrypoint與verified runner bytes執行，所有 write要嘛被 meter治理、要嘛 reason-coded stop，前次 sandbox完全不受影響。

### SC-002｜兩個代表性週期

Given cycle 1完整通過
When同一 sandbox/contract執行 cycle 2
Then兩份 receipt都有完整 live容量/RSS/swap/growth/stability/quiescence證據，且累積與回收在上限內。

### SC-003｜誠實逐 job判定

Fog 只能得到 `PASS_CANDIDATE` 或精確 reason-coded `NO-GO`；短 child、exit 0、單週期、fixture或缺 sample不得當 PASS。

### SC-004｜Production fail closed

不論 fog 判定，八個 job的 `launch_verified=false` 與 launchd disabled/not-loaded 維持不變；本卡不授權重跑以外的 live操作、merge、push、deploy或排程啟用。

## Deliverables

- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-04/preflight.md`
- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-04/cycle-1.json`
- cycle 1 通過才可有 `cycle-2.json`
- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-04/verification.md`
- 單一 candidate commit、changed-file allowlist、affected/full tests與 `git diff --check`

每份 machine receipt ≤2 MiB；raw log留 local temp並只記 digest。Implementation 不得自審。

## 收卡狀態

- `READY_FOR_REVIEW / FOG_PASS_CANDIDATE`
- `READY_FOR_REVIEW / FOG_NO_GO_<REASON>`
- `BLOCKED / <REASON>`

本次固定為 `READY_FOR_REVIEW / FOG_NO_GO_SWAP_GROWTH_BUDGET_EXCEEDED`。Raw guard reason
維持 `SWAP_GROWTH_BUDGET_EXCEEDED`；另有 post-run `LIVE_SAMPLE_CADENCE_EXCEEDED` evidence
finding。Cycle 2、retry 與任何 fresh workload 均禁止，未通過 Repair Review 且未取得新的 fresh
activation 前不得重跑。

strict candidate 必須由主線建立／喚醒獨立 Reviewer；不得 merge、push、deploy或啟用排程。

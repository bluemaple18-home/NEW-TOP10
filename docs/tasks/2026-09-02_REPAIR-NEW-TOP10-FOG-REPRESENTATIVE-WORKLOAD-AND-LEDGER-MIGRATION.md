---
id: REPAIR-NEW-TOP10-FOG-REPRESENTATIVE-WORKLOAD-AND-LEDGER-MIGRATION
status: READY_FOR_EXTERNAL_R6
type: runtime-repair
risk: high
baseline: ba1e8c6
---

# Fog Representative Workload and Ledger Migration Repair

👉 [假設與目標確認] 目標：修復 R5 已證實的 migration schema 與 storage write-contract blocker，並建立一個經正常 manager supply／selection 路徑產生、不可繞過 manager policy 的外接碟代表性 workload；邊界：不改模型權重、不啟用 launchd、不部署／push；驗收：各 blocker 先有可重跑 RED，再以 targeted tests、storage guard 與 `/Volumes/VibeCode` R6 兩週期 receipt 證明 GREEN。

## Root question

在不放寬 2 GiB stop-loss、不中斷其他專案且不繞過 manager policy 的條件下，fog worker 是否能完成兩個真正有 topic run 的週期？

## Evidence baseline

- R5 autonomous outcome：`TOPIC_SUPPLY_EXHAUSTED / topic_runs=[]`。
- R5 observation ingest：唯一既有 migration manifest 不符合 v2 disposition／inference／quality／reconciliation contract。
- R5 storage guard：合法 ledger 寫入 `data/research/research_ledger.duckdb` 未登記於 fog write/meter contract。
- R5 資源數據：memory pressure `2`、swap delta `0`、peak RSS `51,118,080 bytes`；因 workload 為空，不構成 capacity PASS。

## Falsifiable hypotheses

1. 若 migration blocker 是 active ingest 無法區分 legacy v1 與可驗證 v2 corpus，則以 append-only 方式產生／選取 current v2 manifest 後，同一 ingest seam 應通過且不得靜默略過無效 active manifest。
2. 若 ledger 是 daily fog pipeline 的必要 writer，則把精確 ledger path（及實際可觀測 sidecar）納入 registered write/meter contract 後，合法 ingest 應通過 guard，而任意 `data/` 寫入仍應 fail closed。
3. 若 topic exhaustion 是 production corpus 已完整消耗，而非 selector regression，則 validation sandbox 經正常 manager intake 建立一個全新、eligible topic 後，`select_topics_for_run` 應選中並執行；直接強制 topic id 或放寬 rerun policy不合格。

## Acceptance

- 一次一 blocker 的 red-capable test 已實際觀測 RED，minimal fix 後 GREEN。
- migration corpus／active selection 保持可追溯、append-only，舊證據不被原地改寫。
- fog storage policy 只新增 daily pipeline 真正需要的精確 write/meter scope。
- R6 cycle 1 與 cycle 2 都有非空 `topic_runs`、有效 live samples、零 unknown/unmetered writes、process group quiescent，且 peak RSS < 2 GiB。
- 正式 launchd 維持未載入；通過也只產生 activation candidate。

## History

- 2026-09-02：從已封存為第三次空 workload 的 R5 分出本卡；禁止在兩個 blocker 修復前再次盲目重跑 external validation。
- 2026-09-02：migration RED 重現：v1 舊 manifest 與 v2 manifest 共存時 ingest 被舊 schema 阻斷；修後只啟用目前 parser manifest，舊 manifest 保留，無目前版本時明確 `MIGRATION_CURRENT_MANIFEST_MISSING`。
- 2026-09-02：daily 新增 `--ensure-current`；只有缺 v2 parser manifest 才 append-only 重建，後續週期重用。
- 2026-09-02：storage RED 重現 `data/research/research_ledger.duckdb` 不在 fog meter/write contract；只新增該精確 path，未放寬整個 `data/`。
- 2026-09-02：代表性供應改由 validation-only fresh manager root，root identity 由 immutable Batch Intent 固定；production 仍使用原 manager root，distinct root 在非 validation 模式 fail closed。
- 2026-09-02：external harness 會拒絕空或沿用 source copy 的 stale `topic_runs`；只有本 cycle 寫出的非空 topic run 才算代表性 workload。
- 2026-09-02：targeted regression `132 passed, 31 subtests passed`，shell syntax、`git diff --check` 與 debug-marker scan PASS；等待 commit 與 `/Volumes/VibeCode` R6。

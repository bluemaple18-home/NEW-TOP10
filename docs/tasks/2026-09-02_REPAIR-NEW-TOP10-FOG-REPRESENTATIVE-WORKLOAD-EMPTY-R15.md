---
id: REPAIR-NEW-TOP10-FOG-REPRESENTATIVE-WORKLOAD-EMPTY-R15
status: IMPLEMENTED_LOCAL_VERIFIED / EXTERNAL_RERUN_PENDING_AUTHORIZATION
type: runtime-fixture-repair
risk: high
baseline: 860d945dc4246f4d5a3bed5971a4eba55e954c0e
---

# Fog Representative Workload Empty R15 Repair

👉 [假設與目標確認] 目標：以本機 deterministic seam 重現並修復 R15 historical exact-regime fixture 的空 `topic_runs`；不重跑 external cycle、不調高 2 GiB ceiling、不縮減代表性 workload、不改 production manager 或模型；以 RED→GREEN、targeted regressions 與 `git diff --check` 判定。

## Evidence baseline

- R15 storage guard 本身未因 RSS 停止，peak `1,635,909,632` bytes。
- `run_fog_representative_validation.py` 的 execute subprocess return code 為 0，但 output `topic_runs=[]`，只留下 generic `REPRESENTATIVE_WORKLOAD_EMPTY`。
- 既有 static test 只證明 fixture date／identity 與 horizon 3 ranking eligibility，不證明完整 manager supply／selection seam 會產生 topic。

## Falsifiable hypotheses

1. 若 static eligibility 與 runtime supply 之間有 contract drift，則用 fresh manager root 執行同一選題 seam 會穩定產生空 selection，並在 `outcome.topic_supply.exclusion_counts` 指出唯一排除邊界。
2. 若 fixture 缺的是診斷保存而非供應邏輯，則把 empty output 的 bounded selection diagnostics 寫入 failure evidence 後可定位下一個單一修復；不得直接放寬 manager policy。
3. 若本機 fresh-manager seam 能選出 topic，則 blocker 位於 batch-intent/write-set 或 execute-only boundary，下一個測試只縮到該層。

## Validation plan

1. 建立不執行 matrix 的 fresh-manager selection test，使用同一 fixture history／candidate／baseline contract，先取得 RED 或排除 selection 層。
2. 一次只修單一已證實 boundary，重跑最小測試後再跑 fixture、continuous supply 與 batch-owner targeted suites。
3. `git diff --check` 與 debug-marker scan；本卡不執行 external cycle。

## History

- 2026-09-02：fresh-manager selection test 已實際 RED；同一 fixture 在不執行 matrix 時即得到 `TOPIC_SUPPLY_EXHAUSTED / selected=[]`，blocker 已定位在 selection／supply 層，而非 batch execution 或 matrix runtime。
- 2026-09-02：RED diagnostics 顯示 `generated=[]`、`no_executable_ranking_template=1`。根因是 fixture candidate path 含 `historical_rankings_current_model`，被正式 `is_baseline_like()` selector 正確排除；舊 static test 直接呼叫 ranking eligibility，未覆蓋 selector。
- 2026-09-02：最小修復改用既有 `vwap_narrow_only_balanced_top10_long_2025-01-02_2026-05-15` candidate；它保留 exact date `2025-08-07` 且不放寬 selector、不改模型或 production ranking。
- 2026-09-02：fresh-manager RED 已轉 GREEN；fixture static eligibility 與 full fresh-manager selection 共 `2 passed`。
- 2026-09-02：受影響回歸 `99 passed, 31 subtests passed`，涵蓋 fixture、continuous supply、batch owner、external harness 與 storage safety；本卡未執行第二次 external cycle。

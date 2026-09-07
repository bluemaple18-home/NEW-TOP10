# RADAR-01 P1-B Finalized Daily Scanner Acceptance

- 日期：2026-09-07
- 基準：local `main@7a3f279`
- 狀態：`MAINLINE_ACCEPTED_LOCAL / VALIDATION_REPLAY_VERIFIED / NON_RUNTIME / P1-C_TO_P1-E_NOT_ADMITTED`

## Root question／blocker／fork

- Root question：能否只用 ME-D1 finalized Daily Close identity、feature artifact bytes、indicator semantics 與 P1-A eligible SignalSpec，產生 deterministic、read-only、market-wide scanner result？
- 已關閉 blocker：input lineage 不完整、feature row 消失可能被當成未觸發、snapshot weekday gap 未進 history semantics、previous-observed scan 可能近似 O(N²)。
- Pending forks：P1-C SignalOccurrence／Radar Projection、P1-D evidence statistics、P1-E confluence 均未准入；Fog 仍由另一 task 唯讀觀察。

## Acceptance verdict

```text
status: GO_LOCAL_NON_RUNTIME
scope: RADAR-01 P1-B only
default_catalog_status: NO_RADAR_ELIGIBLE_SIGNAL_SPEC
production_or_live_acceptance: NONE
ranking_impact: NONE
research_matrix_dimension_delta: 0
```

P1-B scanner contract、offline end-to-end 與代表性 validation replay 已通過。Repo 目前沒有 materialized official ME-D1 manifest，且 P1-A catalog 的四個 specs 全為 `CONTRACT_ONLY`；因此本結論不宣稱 live／production ready，也不讓任何 signal 取得 Radar eligibility。

## Implementation

`app/signals/scanner.py` 新增：

- scanner 自行驗證 content-addressed ME-D1 manifest／records，拒絕 unresolved-empty 或 identity drift；
- feature input 只接受 regular local parquet，自行計算 bytes SHA-256，讀取必要欄位並做 read-during-hash guard；
- feature key 不得超出 snapshot；matched OHLCV／market／stock identity 必須與 snapshot 一致；
- `indicator_semantics_ref` 必填且納入 scan identity；
- 只接受 `RADAR_ELIGIBLE` SignalSpec；default catalog 因 eligible count=0 回 explicit no-eligible status；
- observed-through date 的每個 snapshot row／spec 恰落入 `TRIGGERED / NOT_TRIGGERED / NOT_OBSERVABLE`；
- dataset-session policy 使用 manifest weekday candidates，previous-observed policy 只查 snapshot-bound rows；
- deterministic frozen report 保存 input identities、三態 counts、暫態 hits 與 structured warnings，不落盤。

沒有建立 canonical SignalOccurrence、統計、base-rate result、confluence、Radar UI/API、writer、scheduler、provider fetch、ranking 或 runtime wiring。

## Data-product gate

```text
data_contract:
  source_and_grain: ME-D1 snapshot records + feature parquet；(date, stock_id)，輸出 grain 為 observed-through date × eligible SignalSpec
  confirmed_schema_and_status_semantics: finalized snapshot；eligible-only；TRIGGERED / NOT_TRIGGERED / NOT_OBSERVABLE
  joins_and_cardinality: feature keys 必須為 snapshot subset；extra/duplicate/null key fail closed；as-of missing row 明示 warning
  aggregation_invariants: 每 spec triggered + not_triggered + not_observable = snapshot as-of rows
execution_boundary:
  database_pushdown: not-applicable；只讀 content-addressed snapshot 與 projected parquet 必要欄位
  controlled_artifacts: representative_probe.py + representative_result.json；snapshot 只建於 TemporaryDirectory
degradation:
  unavailable_data: FEATURE_PROJECTION_ROW_MISSING / REQUIRED_FEATURE_UNAVAILABLE / REQUIRED_HISTORY_UNAVAILABLE / RULE_RESULT_UNAVAILABLE
  provisional_thresholds: none
  model_limits: scanner 只重播 deterministic signal columns，不證明 economic edge
validation:
  fixture_or_unit: 15 P1-B tests；相鄰 P1-A／ME-D1／DatasetBundle 共 90 tests
  representative_real_data: 516,169-row local market-data validation replay；latest 1,930 rows
  old_vs_new_reconciliation: matched raw rows exact；feature missing=0；同 input 雙重 replay identity 相同
  business_invariants: current catalog eligible=0；ranking impact=NONE；matrix delta=0
warnings_and_exclusions:
  snapshot replay resolution=RESOLVED_WITH_GAPS；scanner status=PARTIAL，未掩蓋 47 個 gap/market coverage evidence
remaining_risk:
  checkout 尚無 official materialized ME-D1 manifest；代表性 replay 綁 legacy clean parquet，只具 validation authority
```

## Representative 516,169-row replay

可重跑腳本：`docs/evidence/RADAR-01-P1-B-FINALIZED-DAILY-SCANNER-20260907/representative_probe.py`

Receipt：`docs/evidence/RADAR-01-P1-B-FINALIZED-DAILY-SCANNER-20260907/representative_result.json`

為驗證 engine，probe 只在暫存 snapshot 上建立四個明示 `test-only://` evidence ref 的 eligible clones；這些 clones 不會回寫 catalog，也不具 research authority。

| Validation-only spec | Triggered | Not triggered | Not observable | Total |
|---|---:|---:|---:|---:|
| `ma5_cross_ma20_down@1.0.0` | 28 | 1,027 | 875 | 1,930 |
| `ma5_cross_ma20_up@1.0.0` | 46 | 1,009 | 875 | 1,930 |
| `rsi_break_below_50@1.0.0` | 89 | 1,818 | 23 | 1,930 |
| `rsi_rebound_from_40@1.0.0` | 57 | 1,850 | 23 | 1,930 |

```text
feature_matched_row_count = 1930
feature_missing_row_count = 0
hit_count = 220
deterministic_replay_equal = true
scan_content_id = sha256:ced9349f3558035d80c336756babdfe711e71d9c82384dd3eaaeb8836840abe1
replay_scan_content_id = sha256:ced9349f3558035d80c336756babdfe711e71d9c82384dd3eaaeb8836840abe1
```

`PARTIAL` 是正確降級：temporary replay snapshot 的 weekday-candidate contract 保留 47 個 unresolved gap／partial-market evidence；scanner 沒有把它們宣稱為市場休市或成功完整掃描。

## RED/GREEN and regression evidence

- RED 1：scanner module 不存在，11 cases 全部 import fail。
- GREEN 1：snapshot／feature／eligibility gates、三態 scan、history policies 與 deterministic report 通過。
- RED 2：gap snapshot 使用 previous-observed policy 時，測試原預期 `COMPLETE`；資料契約要求 gap 必須留存，因此改為 signal 可觸發但 report 維持 `PARTIAL`。
- Review repair 1：補 `indicator_semantics_ref` 並納入 identity。
- Review repair 2：previous-observed path 改為一次按 stock 分組。
- Review repair 3：nullable raw invalid string 不得 coercion 成合法 missing。
- Targeted：`.venv/bin/pytest -q tests/test_daily_signal_scanner.py tests/test_signal_specs.py tests/test_daily_close_snapshot.py tests/test_research_dataset_bundle.py tests/test_validation_snapshot_adapter.py` → `90 passed`。
- Trace preflight：FR-001～07、AS-US001-01～08、SC-001～03 → `OK`，0 critical／warning。
- Pipeline read-only validation：`ok=true`、0 errors、4 existing MA20／BB coverage warnings。
- `python -m compileall -q app/signals tests/test_daily_signal_scanner.py` 與 `git diff --check` → exit 0。

本輪未重跑全 repo suite。P1-A 驗收時全套已有跨卡紅燈，故本卡不宣稱全 repo 綠；acceptance authority 限於上述 targeted、offline ETL 與代表性 validation replay。

## Review

Review state：`.work/CARD-RADAR-01-P1-B-FINALIZED-DAILY-SCANNER/review/review_state.jsonl`

- `RADAR-P1B-REV-001` incomplete indicator semantics lineage：已修復。
- `RADAR-P1B-REV-002` previous-observed performance risk：已修復。
- `RADAR-P1B-REV-003` nullable raw coercion drift：已修復。
- Spec axis：全部 acceptance scenarios 有 deterministic tests/evidence。
- Standards axis：沒有未解 P0/P1；無 network、external write、runtime mutation 或 persistent scanner output。
- review orchestrator 因 `docs/operations/CURRENT_OPERATIONAL_FRONTIER.md` 路徑機械標記 lifecycle；實際 source 無 activation／rollback／teardown／trap 或外部副作用，failure-state review=`NOT_APPLICABLE`。

## Remaining limits and next gate

- Default catalog 仍是 `NO_RADAR_ELIGIBLE_SIGNAL_SPEC`；220 hits 只屬 validation-only clones，不能展示或發布。
- Official ME-D1 snapshot 首次出現後，仍需用相同 scanner 做 read-only observation；這不是 production activation。
- P1-B output 是暫態 report，不是 canonical SignalOccurrence。
- P1-C 若要開始，必須由 Owner 再次明確 admission；不得自動建立 Occurrence store／Radar projection。
- 不得 push、deploy、切 production 或改 Fog watcher。

# RADAR-01 P1-C SignalOccurrence / Radar Projection Acceptance

- 日期：2026-09-07
- 基準：local `main@5512795`
- 狀態：`MAINLINE_ACCEPTED_LOCAL / RE-REVIEW_GO / VALIDATION_REPLAY_VERIFIED / NON_RUNTIME`

## Root question／boundary

- Root question：能否只用 exact ME-D1 snapshot、P1-B scan report 與 exact Radar-eligible SignalSpec，產生 content-addressed occurrence 與 deterministic、無 ranking authority 的 Daily Radar read-model？
- Boundary：P1-C 只建立 in-memory rebuildable projection；不落盤、不建立第二套 truth、統計/base-rate、confluence、UI/API、scheduler、provider fetch、ranking 或 runtime。
- Default authority：目前四個 catalog SignalSpec 仍全為 `CONTRACT_ONLY`，所以 default projection 是 explicit no-eligible、零 occurrence；representative 220 occurrences 只來自 validation-only clones。

## Acceptance verdict

```text
status: GO_LOCAL_NON_RUNTIME
scope: RADAR-01 P1-C only
default_catalog_status: NO_RADAR_ELIGIBLE_SIGNAL_SPEC
production_or_live_acceptance: NONE
ranking_impact: NONE
research_matrix_dimension_delta: 0
```

## Implementation

- `SignalOccurrence` 只由 `TRIGGERED` hit 建立，帶 instrument/date、SignalSpec identity/version/direction、snapshot/records、feature artifact、indicator semantics、provider/adapter/source provenance、research evidence、scan identity 與 projection build version。
- occurrence 與 projection ID 均由 canonical content hash 計算；輸出只含 frozen dataclass 與 scalar/tuple fields，不暴露 mutable nested source mapping。
- builder 重新載入 exact content-addressed snapshot，驗證 scanner contract、scan date、snapshot/records identity、coverage counts、eligible spec/summaries、hit counts/uniqueness/direction 與 scan-date instrument membership。
- malformed report、nested item、enum、hash/ref、bool/negative count 或 warning 以 stable `SignalOccurrenceError.reason_code` fail closed。
- Radar item 只依 `instrument_id` deterministic 排序，分組 bullish/bearish/neutral occurrence IDs；schema 沒有 score、rank 或 recommendation，`ranking_impact=NONE`。
- `NOT_TRIGGERED`／`NOT_OBSERVABLE` 只留在 P1-B summary/warnings，不膨脹成 occurrence。

## Data-product gate

```text
data_contract:
  source_and_grain: exact ME-D1 snapshot + P1-B report + exact eligible SignalSpec；occurrence grain = scan date × instrument × SignalSpec identity
  lineage: snapshot/records/feature/indicator/provider/source/spec/research/scan/build identities 均進 occurrence identity
  aggregation_invariants: occurrence count = triggered hit count；每個 occurrence ID 在 Radar items 恰出現一次
  status_semantics: COMPLETE / PARTIAL / NO_RADAR_ELIGIBLE_SIGNAL_SPEC 原樣保留；缺資料不視為未觸發
execution_boundary:
  persistence: none；所有輸出只在記憶體
  ranking_authority: NONE
degradation:
  malformed_or_drifted_input: stable fail-closed reason code
  no_eligible_catalog: explicit zero-occurrence projection
validation:
  targeted_and_adjacent: 116 tests
  representative: 516,169 rows；scan-date 1,930 rows；220 occurrences；217 items
  replay: occurrence/projection IDs 可重算且 projection replay 相同
warnings_and_exclusions:
  validation snapshot = RESOLVED_WITH_GAPS；projection 正確維持 PARTIAL
  official materialized ME-D1 snapshot 尚未存在於 checkout
```

## Representative validation replay

- Probe：`docs/evidence/RADAR-01-P1-C-SIGNAL-OCCURRENCE-RADAR-PROJECTION-20260907/representative_probe.py`
- Receipt：`docs/evidence/RADAR-01-P1-C-SIGNAL-OCCURRENCE-RADAR-PROJECTION-20260907/representative_result.json`

```text
input_rows = 516169
snapshot_row_count = 1930
hit_count = occurrence_count = unique_occurrence_id_count = 220
item_count = 217
direction_counts = BULLISH 103 / BEARISH 117
all_occurrence_ids_recompute = true
projection_id_recomputes = true
items_cover_each_occurrence_once = true
warnings_preserved = true
deterministic_replay_equal = true
projection_id = replay_projection_id = sha256:5b17239bff71415ca0e4285f811e083050e8af932730f5a1b4cf5489bc35859f
ranking_impact = NONE
```

Default catalog 在同一 validation snapshot 上另行驗證：eligible=0、occurrence=0、item=0、`no_eligible=true`、`ranking_impact=NONE`。

## RED/GREEN／review evidence

- Initial RED：P1-C module 尚未存在，targeted test collection 以 `ModuleNotFoundError` 失敗。
- Initial GREEN：positive、deterministic、no-eligible、partial、multi-direction 與 report tampering tests 通過。
- Strict review `NO_GO`：發現三個 P1——snapshot 外 instrument 可注入、nested endpoint mapping 可改而 ID 不變、malformed dataclass 未一致 stable fail-closed。
- Repair generation 1：加入 scan-date instrument gate、以完整 source content hash 取代 mutable mapping、集中 exact-type/nested/count/warning validator。
- 原 Reviewer re-review：三個 P1 均 `RESOLVED`，結論 `RE_REVIEW_GO`；state 位於 `.work/RADAR-01-P1-C/review/review_state.jsonl`。
- Parent targeted＋相鄰 ME-D1/DatasetBundle seam：`.venv/bin/python -m pytest -q tests/test_signal_occurrence_radar_projection.py tests/test_daily_signal_scanner.py tests/test_signal_specs.py tests/test_daily_close_snapshot.py tests/test_research_dataset_bundle.py tests/test_validation_snapshot_adapter.py` → `116 passed`。
- Trace preflight：US-001、FR-001～07、AS-US001-01～07、SC-001～03 → `OK`，0 critical／warning。
- `git diff --check` → exit 0。

本輪未重跑全 repo suite。P1-A 驗收時全套已有跨卡紅燈，因此本卡不宣稱全 repo 綠；acceptance authority 限於上述 contract suite、strict review/re-review 與代表性 offline replay。

## Remaining limits／next gate

- Checkout 沒有 official materialized ME-D1 snapshot；本輪不是 live／production acceptance。
- P1-C 不從 feature parquet 重算 P1-B rule evaluation；它只接受已驗證 P1-B report，scanner 仍是 evaluation authority。
- Validation-only eligible clones 不回寫 catalog，不證明 signal edge，也不得展示、發布或改 ranking。
- P1-D historical statistics/base-rate 與 P1-E confluence 仍各自需要 Owner 明確 admission。
- 不得 push、deploy、切 production 或改 Fog watcher。

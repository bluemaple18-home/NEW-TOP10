# RADAR-01 P1-A SignalSpec Authority and Observability Acceptance

- 日期：2026-09-07
- 基準：local `main@cc6b1d5`
- 狀態：`MAINLINE_ACCEPTED_LOCAL / NON_RUNTIME / P1-B_TO_P1-E_NOT_ADMITTED`

## Root question／blocker／fork

- Root question：少量既有 Daily Close signals 能否先取得 versioned SignalSpec authority，並在缺資料或雙來源 drift 時 fail closed？
- 已關閉 blocker：既有 signal metadata 沒有 content identity；`0` 混合未觸發與不可觀測；重複 calculation seam 沒有 parity gate。
- Pending forks：P1-B scanner、P1-C SignalOccurrence/Radar、P1-D evidence statistics、P1-E confluence 全部未准入。Fog 仍由既有另一 task 唯讀觀察。

## Acceptance verdict

```text
status: GO
scope: RADAR-01 P1-A only
radar_eligible_signal_count: 0
runtime_authority: NONE
ranking_impact: NONE
research_matrix_dimension_delta: 0
```

P1-A 已達成 contract／observability／parity acceptance，但沒有任何 signal 因此取得 historical edge 或 Radar eligibility。完成本卡不授權 scanner、projection、statistics、confluence、runtime 或 push。

## Implementation

`app/signals/specs.py` 新增：

- frozen、content-addressed `SignalSpec`；identity 涵蓋版本、方向、rule reference/expression、dataset session policy、required feature/history、Daily Close dataset contract、horizon、evidence、eligibility 與 explanation reference；
- bounded initial catalog，只含 4 個本次代表性資料 parity 為零差異的既有 signals：MA5/MA20 上下穿、RSI 40 反彈與 RSI 50 跌破；
- 初始 specs 全部是 `CONTRACT_ONLY`，horizon/evidence 明示未配置，因此 `radar_eligible_signal_count=0`；
- `TRIGGERED / NOT_TRIGGERED / NOT_OBSERVABLE` resolver；required feature/history、rule result 或 evaluation error 不得 silent zero；
- read-only parity validator：key 欄位、null／duplicate key、key drift、missing signal/feature column、non-binary value 與 signal drift 全部使用穩定 reason code fail closed；
- structured observability warning 固定 `signal_id / reason_code / stage / affected_rows`。

沒有修改既有 indicator math、`EventDetector`、events parquet、ranking、Research Ledger、UI、API 或 runtime。

## Data-product gate

```text
data_contract:
  source_and_grain: data/clean/features.parquet + events.parquet；(date, stock_id)
  confirmed_schema_and_status_semantics: 4 個 contract-only binary projections；三態 resolver 不把 unavailable 當 0
  joins_and_cardinality: 516,169 vs 516,169；key set exact；duplicate=0
  aggregation_invariants: 每 spec observable + unobservable = 516,169；parity mismatch=0
execution_boundary:
  database_pushdown: not-applicable；本卡只讀 DataFrame validator
  controlled_artifacts: docs/evidence/RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY-20260907/representative_parity.json
degradation:
  unavailable_data: REQUIRED_FEATURE_UNAVAILABLE / REQUIRED_HISTORY_UNAVAILABLE
  provisional_thresholds: none；未新增 threshold 或 weight
  model_limits: parity 只證明既有兩 projection 一致，不證明 signal correctness 或 economic edge
validation:
  fixture_or_unit: 22 contract／failure-mode tests
  representative_real_data: 516,169 rows；4 signals；mismatch=0
  old_vs_new_reconciliation: features authority vs events projection
  business_invariants: eligible=0；matrix delta=0；ranking impact=NONE
warnings_and_exclusions:
  MA pair: 256,278 unobservable rows each
  RSI pair: 26,504 unobservable rows each
remaining_risk:
  clean parquet 尚未綁定 ME-D1 snapshot identity；exchange calendar／manifest gap semantics 留給未准入 P1-B
```

## Representative real-data evidence

Evidence：`docs/evidence/RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY-20260907/representative_parity.json`

| SignalSpec | Observable | Not observable | Mismatch | Eligibility |
|---|---:|---:|---:|---|
| `ma5_cross_ma20_up@1.0.0` | 259,891 | 256,278 | 0 | `CONTRACT_ONLY` |
| `ma5_cross_ma20_down@1.0.0` | 259,891 | 256,278 | 0 | `CONTRACT_ONLY` |
| `rsi_rebound_from_40@1.0.0` | 489,665 | 26,504 | 0 | `CONTRACT_ONLY` |
| `rsi_break_below_50@1.0.0` | 489,665 | 26,504 | 0 | `CONTRACT_ONLY` |

MA pair 的 unavailable 由 required feature 248,230 筆＋required history 8,048 筆組成；RSI pair 是 required feature 2,303 筆＋required history 24,201 筆。這些列不再被本契約稱為 `NOT_TRIGGERED`。

## RED/GREEN and regression evidence

- RED 1：`app.signals.specs` 不存在，new tests collection fail。
- GREEN 1：identity、bounded catalog、resolver、parity failure modes 通過。
- RED 2：只檢當日 feature 會漏掉跨日 history availability。
- GREEN 2：加入 `required_history_sessions`、兩種 dataset/observation policy 與 structured warning。
- Review repair：拒絕 mutable `required_features`，避免 frozen contract 被 list 突變；把過度宣稱的 `MARKET_SESSION_CONTIGUOUS` 收斂為 `DATASET_SESSION_CONTIGUOUS`。
- Targeted：`.venv/bin/pytest -q tests/test_signal_specs.py tests/test_daily_close_snapshot.py tests/test_validation_snapshot_adapter.py tests/test_daily_signals_preview.py tests/test_market_flow_radar.py` → `58 passed, 1 warning in 5.07s`。warning 是既有 Starlette/httpx deprecation。
- Pipeline read-only validation：`ok=true`、0 errors、4 existing feature coverage warnings；events validator 仍為 0 issue，這正是 P1-A observability contract 不可省略的原因。
- `python -m compileall -q app/signals tests/test_signal_specs.py` → exit 0。
- `git diff --check` → exit 0。

## Review

Review state：`.work/CARD-RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY/review/review_state.jsonl`

- `RADAR-P1A-REV-001` immutable collection risk：已修復。
- `RADAR-P1A-REV-002` market-session authority overclaim：已修復。
- Spec axis：task card FR-001～FR-005、AS-US001-01～07、SC-001～03 均有 evidence；trace preflight=`OK`。
- Standards axis：未發現未解 P0/P1；security、external write、runtime side effect 均不適用。
- review orchestrator 因 `docs/operations/CURRENT_OPERATIONAL_FRONTIER.md` 路徑機械標記 lifecycle review；實際 diff 只有非 runtime 狀態文字，沒有 activation／rollback／teardown code 或副作用，故 failure-state review 為 `NOT_APPLICABLE`。

全套 repo suite 另得 `1,383 passed / 76 failed / 275 subtests passed`。失敗集中於既有 automation signal timing、macOS sandbox confinement、committed authority artifact drift 與舊 test fixture arguments；沒有 P1-A test failure或指向 `app/signals/specs.py` 的 traceback。但本輪未在同環境重跑 pre-card baseline，因此不把 76 項全部宣稱為已證實 pre-existing，也不宣告全 repo 綠。P1-A 的 acceptance authority 限定於上述 targeted suite、代表性資料與 diff boundary。

## Remaining limits and next gate

- 本機 clean artifacts 是 legacy mutable outputs，沒有綁定 ME-D1 snapshot fingerprint；不能作 Radar occurrence evidence。
- 初始 catalog 只有 contract/parity authority，沒有 research evidence、horizon 或 economic validity。
- 本卡沒有 scanner，因此不產生 instrument/date occurrence。
- P1-B 若要開始，必須再由 Owner 明確 admission，並先決定 ME-D1 snapshot／gap manifest 如何提供完整 dataset-session authority。
- 不得 push、deploy、切 production 或改 Fog watcher。

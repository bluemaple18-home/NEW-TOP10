---
id: CARD-RADAR-01-P1-D-HISTORICAL-STATISTICS-BASE-RATE
status: mainline-accepted-local
type: implementation
thickness: strict
---

# CARD-RADAR-01-P1-D-HISTORICAL-STATISTICS-BASE-RATE

Owner admission：2026-09-07，本對話在 Mainline 明示唯一下一張卡為 P1-D、且說明需 admission 後，Owner 回覆「繼續」。授權只涵蓋本卡的本機實作、Review、Repair 與驗收；P1-E、SignalSpec promotion、ranking、runtime、push 與 deploy 均未授權。

## 驗收結果

- verdict：`MAINLINE_ACCEPTED_LOCAL / RE-REVIEW_GO / VALIDATION_REPLAY_VERIFIED / NON_RUNTIME`
- strict Review 首輪發現 `RADAR-P1D-STRICT-001`；Repair 1 將 public native exception leak 收斂為四個穩定 `HIST_*` reason codes，原 Reviewer targeted re-review 後關閉 finding。
- targeted＋P1-A～P1-C／Daily Close regression：`98 passed`；`compileall`、`git diff --check` 與 traceability validation 均通過。
- 代表性 validation replay：516,169 rows／1,967 stocks／4 validation-only eligible clones；coverage、raw/effective/overlap、incremental-edge 與 content ID 重算全部閉合，deterministic replay 相同。
- default catalog 仍為四個 `CONTRACT_ONLY` specs，輸出 `eligible_signal_count=0 / statistics_count=0`；不具 eligibility、ranking、runtime、OOS 或 sealed authority。
- acceptance evidence：`docs/evidence/RADAR-01-P1-D-HISTORICAL-STATISTICS-BASE-RATE-20260907.md`。
- 本卡 admission 已用畢並關閉；P1-E 仍須 Owner 另行明確 admission。

## Root question

如何在不改 Research Spine、Existing Backtest Engine 或 Radar ranking authority 的前提下，從 exact finalized Daily Close snapshot 與已驗證 feature artifact 產生可重算的 signal historical statistics，並用同 universe／horizon／direction 的 relevant base rate 表達 incremental edge，而不把 win rate 或平均報酬單獨包裝成研究結論？

## 已確認資料事實

- P1-C commit：`23401329f9ffea56b99765f821c29eb57e17caf7`；P1-A／P1-B／P1-C 已本機驗收。
- `data/clean/features.parquet` schema 直接量測為 516,169 rows、1,967 stocks、2025-07-08 至 2026-09-01、TWSE/TPEX、`(date, stock_id)` duplicate=0、close null=0、close non-positive=0。
- authoritative Daily Close contract 是 `daily-close-snapshot.v1`，price basis 固定 `UNADJUSTED`；所以本卡只可稱為未調整收盤價的 price-return 描述，不得稱 total return，且不含股息、費用、稅或公司行動調整。
- default 四個 SignalSpec 仍為 `CONTRACT_ONLY`，因此正式 default output 必須維持 zero eligible／zero statistics。代表性 replay 只可使用 validation-only eligible clones。
- P1-B 已有 exact snapshot／feature bytes／raw Daily Close parity／SignalSpec 三態 evaluation seam；P1-D 應沿用或最小抽取此 seam，不得複製出另一套較弱驗證。

## 使用者需求

### Relevant base rate before signal <!-- US-001 -->

- **FR-001**：只接受 exact finalized Daily Close manifest、不可變 parquet feature artifact、合法 indicator semantics ref 與 exact `RADAR_ELIGIBLE` SignalSpec；snapshot／records／feature／spec identity 漂移必須用穩定 reason code fail closed。 <!-- FR-001 traces_to: US-001 -->
- **FR-002**：每個 SignalSpec 使用其正整數 `evaluation_horizon_days`，依個股 observed sessions 計算 entry close 至第 H 個後續 session 的 forward price return；缺 H 個後續 session 的 observations 必須顯式排除並計數，不得補值或視為零報酬。 <!-- FR-002 traces_to: US-001 -->
- **FR-003**：conditional sample 只包含三態 evaluation 中的 `TRIGGERED` 且 outcome 完整者；`NOT_TRIGGERED`、`NOT_OBSERVABLE` 與 outcome-incomplete 分開計數並形成結構化 warning／coverage，不得靜默消失。 <!-- FR-003 traces_to: US-001 -->
- **FR-004**：relevant baseline 固定為同一 snapshot、同 universe、同 sample window、同 horizon、同 direction outcome definition 的 unconditional complete-outcome rows；caller 不得注入任意 baseline 或事後挑選 comparator。 <!-- FR-004 traces_to: US-001 -->
- **FR-005**：每個 signal 至少輸出 raw/effective sample size、event-date count、forward horizon、conditional 與 baseline 的 direction-positive rate、mean／median／quantiles、downside／max-adverse-excursion summary，以及 incremental edge（percentage-point 與 location effect）；不得讓 mean、win rate 或 cumulative return 單獨取得 authority。 <!-- FR-005 traces_to: US-001 -->
- **FR-006**：依賴性固定使用透明、可重算的 `per-instrument non-overlapping forward windows` effective-sample policy，並輸出 overlap count；不宣稱統計獨立性、顯著性或 causal edge。 <!-- FR-006 traces_to: US-001 -->
- **FR-007**：read-model 必須 immutable、content-addressed 且保留 snapshot／records／feature／indicator／SignalSpec／research evidence refs、universe、日期窗、market、currency、UNADJUSTED price-return、dividend／fees／tax assumptions、regime match、OOS/sealed 狀態與 policy versions。 <!-- FR-007 traces_to: US-001 -->
- **FR-008**：default catalog 無 eligible spec 時輸出 explicit no-eligible result；P1-D 不修改 SignalSpec eligibility、Research Ledger、Matrix、backtest math、P1-C occurrence、P1-E confluence、UI/API、資料庫、writer、scheduler 或 production。 <!-- FR-008 traces_to: US-001 -->

1. **Given** 一個合法 eligible bullish／bearish spec 與 exact input，**When** build，**Then** conditional 和 relevant baseline 使用同 horizon／universe／window，且 incremental edge 可由兩者重算。 <!-- AS-US001-01 traces_to: FR-001, FR-002, FR-004, FR-005 -->
2. **Given** outcome tail 不足、required feature 缺失或 required history 不足，**When** build，**Then** exclusion reason 與 affected count 可觀測，sample size 不含被排除列。 <!-- AS-US001-02 traces_to: FR-002, FR-003 -->
3. **Given** overlapping events，**When** build，**Then** raw sample 不變、effective sample 依固定 policy 降低，且 overlap count 閉合。 <!-- AS-US001-03 traces_to: FR-006 -->
4. **Given** 相同 inputs，**When** 重跑，**Then** result content ID、各 signal statistics、warnings 與排序完全一致。 <!-- AS-US001-04 traces_to: FR-007 -->
5. **Given** default catalog，**When** build，**Then** explicit zero eligible／zero statistics，沒有 promotion 或 ranking side effect。 <!-- AS-US001-05 traces_to: FR-008 -->
6. **Given** malformed enum/type、feature value、identity、direction 或 horizon，**When** build，**Then** 只回穩定 P1-D reason code，不洩漏 native pandas／numpy 例外作 public contract。 <!-- AS-US001-06 traces_to: FR-001, FR-007 -->
7. **Given** representative local replay，**When**檢查輸出，**Then**清楚標示 `VALIDATION_ONLY / NOT_OOS / NOT_SEALED / NO_ELIGIBILITY_OR_RANKING_AUTHORITY`，不得冒稱 live/production research acceptance。 <!-- AS-US001-07 traces_to: FR-007, FR-008 -->

- **SC-001**：P1-D targeted tests 與 P1-A～P1-C regression tests 全綠；涵蓋 bullish、bearish、baseline alignment、tail exclusion、unobservable、overlap、tampering、default-zero 與 deterministic replay。 <!-- SC-001 traces_to: US-001, FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008 -->
- **SC-002**：代表性 516,169-row validation replay 完成，輸出 invariants 與 source limitations；若無 official materialized snapshot，不得宣稱 production/live。 <!-- SC-002 traces_to: US-001, FR-001, FR-004, FR-007, FR-008 -->
- **SC-003**：獨立 strict Review 無未解 P0/P1；`git diff --check` 通過；Matrix dimension delta=0、ranking/runtime impact=`NONE`。 <!-- SC-003 traces_to: US-001, FR-008 -->

## 垂直切片與依賴

| Slice | Scope | traces_to | Blocking edge | Verification |
|---|---|---|---|---|
| `RADAR01-P1D-SLICE-001` | exact historical input seam、outcome/baseline observation contract與穩定錯誤 | `FR-001`–`FR-004`, `AS-US001-01`, `AS-US001-02`, `AS-US001-06` | P1-C accepted；Owner P1-D admission | RED/GREEN contract tests |
| `RADAR01-P1D-SLICE-002` | deterministic statistics、effective-sample policy、immutable content-addressed read-model | `FR-005`–`FR-008`, `AS-US001-03`–`AS-US001-05` | `SLICE-001` | recompute/invariant tests |
| `RADAR01-P1D-SLICE-003` | representative replay、strict Review、canonical status reconciliation | `AS-US001-07`, `SC-001`–`SC-003` | `SLICE-001`, `SLICE-002` | targeted+regression suite、replay、diff/review gate |

Checkpoint：SLICE-001/002 綠燈後才可做代表性 replay。任何 baseline grain、return basis、outcome window 或 input identity 無法證明時，只能 `PARTIAL/BLOCKED`，不得用推論補齊。

## Likely files

- `app/signals/historical_statistics.py`
- `app/signals/scanner.py`（只允許最小抽取既有 exact validated input seam）
- `app/signals/__init__.py`
- `tests/test_signal_historical_statistics.py`
- `docs/evidence/RADAR-01-P1-D-HISTORICAL-STATISTICS-BASE-RATE-20260907.md`
- `docs/RESEARCH_SPINE_BACKLOG.md`
- `docs/operations/CURRENT_OPERATIONAL_FRONTIER.md`

## Do not touch

- Fog、launchd、storage guard、runtime checkout、provider fetch、publish/deploy/push。
- Existing Backtest Engine、Research Matrix dimensions、Research Ledger writer／schema、ranking weights、P1-E confluence。
- default SignalSpec eligibility 與任何 production/live authority。

## Why this minimum

- Why not less：只有 absolute signal statistics 會違反 permanent `Base Rate Before Signal`；沒有 effective sample 與 exclusion coverage 會把重疊／缺資料誤包成證據。
- Why not more：eligibility promotion、regime engine、顯著性檢定、adjusted/total-return provider、UI/API、persistence 與 confluence 都是獨立 admission，這張卡沒有 authority。
- Do not absorb：不建立第二套 ledger／DB／writer／backtest engine；只建可重算的 in-memory evidence projection。

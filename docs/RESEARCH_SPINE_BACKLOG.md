# NEW-TOP10 Research Spine Backlog

更新：2026-09-07

狀態：`CARD_A_CLOSED / F0_ACCEPTED / B0_P1_AND_C0_P1_ACCEPTED / CURRENT_TIP_BASELINE_ACCEPTED / BC_CP1_DECIDED / C0_P2_ACCEPTED_CLOSED / B0_P2_NO_GO_INSUFFICIENT_DECISION_VALUE / B1_TO_D1_NOT_ADMITTED / R14_NO_GO / TALIB_01_P1_REGISTERED_NOT_ADMITTED / ME_D1_P1_SEAM_AUDITED_NOT_ADMITTED / RADAR_01_P1_REGISTERED_NOT_ADMITTED`

Repository：`bluemaple18-home/NEW-TOP10`

母卡：[#1 CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1](https://github.com/bluemaple18-home/NEW-TOP10/issues/1)

> 本檔是 NEW-TOP10 Research Spine 的 canonical domain backlog、依賴順序與 admission gate。
>
> GitHub Issues 是可派工工作卡；本檔決定哪些卡現在可動、哪些只可研究、哪些仍被依賴阻擋。不得掃描 Issue 後自行跳卡。
>
> AI Core 的共用治理 authority 是 `bluemaple18-home/aicore` 的 `docs/ai-core-backlog.md`。量化研究只增加 domain specialization，不得在 NEW-TOP10 建立第二套通用 execution、authority、queue、ledger 或 lifecycle runtime。

---

## 0. Authority reconciliation

### 現況

F0 已完成於 `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`；B0-P1、C0-P1、C0／BC evidence 與後續 R1–R14 已整合。current-tip independent acceptance 已在 `78d3b3b1d246dd37f8a1094ff85ba5175dae995e` 裁決 `REVIEW_GO_CURRENT_TIP_BASELINE`。

這個 GO 只接受目前 tracked tree 作為非 production 基線。repo 內未找到獨立 BC-CP1 admission decision artifact；C0 Phase 2 task 對 `ADMIT_C0_PHASE_2` 的自我引用，以及已 merge 的 Phase 2 evidence，都不能單獨成為 current admission authority。

BC-CP1 已依 Owner 明確授權、以 current accepted inputs 重新裁決：

```text
ADMIT_C0_PHASE_2 / SPENT_AND_CLOSED
```

此 verdict 只補足已完成 C0 Phase 2 evidence-only scope的checkpoint provenance；不提供持續execution authority。不得執行 B0-P2、重跑C0-P2、B1、C1、runtime mutation、benchmark、capture、replay或production。

---

## 1. Pinned observed baselines

### NEW-TOP10

```text
reconciled source baseline = f787437e2c88a327ad7be210f31d790fa96ee3f7
observed origin/main       = f787437e2c88a327ad7be210f31d790fa96ee3f7
authority note             = 這是 2026-09-07 seam audit 的固定證據基線；docs-only reconciliation commit 可再推進 HEAD，且不構成 push/deploy 或 implementation authority
```

### AI Core

```text
repository           = bluemaple18-home/aicore
observed origin/main = 26eb42f8e401807d3dbd6030171b9dfeb58207fb
canonical backlog    = docs/ai-core-backlog.md
```

這兩個 SHA 是本次裁決依據，不是永久 future execution base。正式派工時若遠端已前進，owner 必須先做 delta check 並固定新 SHA。

### Historical / supplemental sources

- `aeae2c3`：歷史草稿／問題清單，只可逐段取材；不 merge、不作 execution base。
- Trace V2：只有固定可驗證來源後，才可作 cross-project combination-kernel donor；無 pin 時標示 `UNPINNED_CROSS_PROJECT_DONOR`。
- OMI：market evidence／lineage supplemental prior art；ME-D1 只吸收其 target-architecture seam，不把 OMI 變成 runtime dependency，也不是 B／C governing architecture。
- Owner-provided signal-radar product pattern：只吸收 post-close scanner／confluence／evidence-backed UI 的 product interaction pattern；RADAR-01 不複製其 proprietary signal inventory、marketing claims 或 backtest percentages。
- Ben Carlson / A Wealth of Common Sense 2026-08-27「10 Things You Need to Know About Investing in Stocks」：只吸收 long-horizon market base-rate / distribution caution 作 RADAR-01 research-quality donor，不把美國指數歷史常識升格為個股 signal、交易規則或 universal market law。
- Bessembinder et al. 2023 `Long-Term Shareholder Returns: Evidence from 64,000 Global Stocks`：用來固定 `index/base-rate evidence != individual-stock guarantee` 與 long-run stock-return skewness caution。

---

## 2. Current unique frontier

### No active Research Spine execution frontier

```text
F0                         = ACCEPTED
B0-P1 / C0-P1              = ACCEPTED
CURRENT INTEGRATED BASELINE = ACCEPTED / NON_PRODUCTION
BC-CP1                     = ADMIT_C0_PHASE_2 / DECIDED
C0-P2                      = ACCEPTED / SPENT_AND_CLOSED
B0-P2                      = NO_GO_INSUFFICIENT_DECISION_VALUE
B1 / C1                    = NOT_ADMITTED
R14                        = NO_GO / NOT_ADMITTED
TALIB-01                   = P1 REGISTERED / NOT_ADMITTED / NO_RUNTIME_AUTHORITY
ME-D1                      = P1 REGISTERED / NOT_ADMITTED / FINALIZED_DAILY_CLOSE_ONLY / NO_RUNTIME_AUTHORITY
RADAR-01                   = P1 REGISTERED / NOT_ADMITTED / DAILY_CLOSE_PRODUCT_PROJECTION / NO_RUNTIME_AUTHORITY
```

已 merge 的 C0 Phase 2 與 BC-CP2 R1–R14 文件保留為設計／證據歷史；BC-CP1 decision只讓既有C0-P2 scope完成權限閉環，不產生current execution authority。B0-P2已因缺research-valid measured gap與E4 decision value裁決NO-GO；不得直接跳到B1、C1或implementation。獨立Forecast／TFM3 fork不由本backlog自動准入。

[#16 TALIB-01](https://github.com/bluemaple18-home/NEW-TOP10/issues/16) 只登記 TA-Lib 作為 P1 indicator-provider / correctness donor；它不改變 current frontier、不 admission runtime implementation，也不增加 canonical Research Matrix 維度。

[#17 ME-D1](https://github.com/bluemaple18-home/NEW-TOP10/issues/17) 只登記「finalized Daily Close first slice + future Market Evidence seam」。它保留未來完整 Market Evidence target architecture，但不 admission 即時行情、多 provider resolver、repair/reconciliation、broker integration 或其他 market-data runtime；Research Spine 與 canonical Research Matrix 維度均不變。

[#18 RADAR-01](https://github.com/bluemaple18-home/NEW-TOP10/issues/18) 只登記「Daily Close → eligible SignalSpec → scanner → SignalOccurrence → deterministic confluence → Radar Projection」的產品化路徑。它是 rebuildable product projection，不是 Research Truth、Research Matrix 或 production ranking authority；不 admission intraday、額外市場資料源、AI signal/ranking authority、scheduler/publish 或 production。其 research-quality rule 新增 `BASE_RATE_BEFORE_SIGNAL`：任何 signal historical statistic 必須能與同 horizon / universe / relevant regime 的 baseline 比較，不得只報 absolute win rate / forward return。

### 部分平行規則

B0-P1 與 C0-P1 可以同時盤點，但不能同時完成最終結論：

```text
B0-P1
→ matrix authority / dimension taxonomy / exact count / E1–E4 initial classification

C0-P1
→ execution authority / runner seam / queue and bridge inventory / benchmark readiness

B0-P1 + C0-P1
→ BC-CP1 shared checkpoint

BC-CP1 accepted
→ 才可能分別 admission B0-P2 / C0-P2
```

C0 不得在 B0 提供矩陣大小與 E1–E4 分類前，定案 daily capacity、cutover 或 runtime architecture。

---

## 3. Worker and reviewer routing

### Evidence Workers

- B0-P1：一名 `strict/core-bounded` Worker。
- C0-P1：一名獨立 `strict/core-bounded` Worker。
- 本次 pinned governance decision 下，Worker 使用 GPT-5.5；若 AI Core current router 已有可驗證 superseding route，依新 authority 執行並留下記錄。
- 每名 Worker 只寫自己 lane 的非重疊 evidence。
- 不使用單一 mega-agent 同時研究兩線。

### Integrator / reviewer

- Sol 只負責 architecture arbitration、cross-lane synthesis、checkpoint 與 final verdict。
- Sol 不下場撰寫大量 evidence 文件。
- Integrator 是唯一 cross-lane synthesis writer。

---

## 4. Product target

NEW-TOP10 的長期目標不是單次找一個 `best_params`，而是形成依市場盤況運作的可稽核研究工廠：

```text
股票專屬 Matrix Definition
        ↓
合法 Combination Universe
        ↓
B：Evidence-driven Research Controller
  - coverage fill
  - local refinement
  - boundary expansion
  - replication
  - interaction resolution
  - negative control / challenge
        ↓ explicit admission
Canonical TrialSpec
        ↓
C：Research Execution Control
  - queue reference
  - claim / lease
  - idempotency / retry
  - direct TrialSpec runner
        ↓
Immutable RunReceipt
        ↓
Observation / Eligibility / Failure / Learning
        └──────────────────────────────↺ 回到 B

通過 development、validation、sealed OOS、forward shadow
        ↓
D：RegimePolicyBundle / Promotion Gate
        ↓
每種市場盤況的 primary、robust alternatives、fallback、期限與證據
```

### Layer boundaries

```text
Layer 0 — Discrete Combination Kernel
回答有哪些合法組合、如何計數／產生／分批／找鄰居；不判斷好壞。

Layer A — Research Truth Spine（Card A，已完成）
回答要求跑什麼、實際跑什麼、產生什麼證據、是否可學。

Layer B — Research Decision Projection
回答下一批最值得研究什麼；沒有 execution authority。

Layer C — Research Execution Control
安全執行已 admission 的 canonical specs；沒有 ranking authority。

Layer D — Regime Policy Promotion
把通過多階段驗證的研究結果封裝成有生命週期的盤況配置。
```

RADAR-01 若未來 admission，位於上述 Research Spine／Research Ledger 之上的 **product projection surface**，不是新增 Layer A–D authority。它只能消費已治理的 Daily Close input、SignalSpec 與 research evidence，產出可刪除重建的 scanner/radar views。

---

## 5. Card A closeout and permanent invariants

Card A 母卡與 A0–A6 均已完成／主線接受：

- [x] [#2 A0](https://github.com/bluemaple18-home/NEW-TOP10/issues/2)
- [x] [#3 A1](https://github.com/bluemaple18-home/NEW-TOP10/issues/3)
- [x] [#4 A2](https://github.com/bluemaple18-home/NEW-TOP10/issues/4)
- [x] [#5 A3](https://github.com/bluemaple18-home/NEW-TOP10/issues/5)
- [x] [#6 A4](https://github.com/bluemaple18-home/NEW-TOP10/issues/6)
- [x] [#7 A5](https://github.com/bluemaple18-home/NEW-TOP10/issues/7)
- [x] [#8 A6](https://github.com/bluemaple18-home/NEW-TOP10/issues/8)
- [x] [#1 Card A parent](https://github.com/bluemaple18-home/NEW-TOP10/issues/1)

永久不變量：

1. Canonical truth 是 immutable spec／intent／attempt／receipt／artifact／migration evidence。
2. Observation、Eligibility、Failure、Learning、Fog Map、Priority、Candidate、Queue、PM/Ops 都是 rebuildable projections。
3. `combo_id` 是 legacy-only，不可成為新 canonical FK。
4. requested truth 與 executed truth 必須分開。
5. failure／orphan 是 first-class execution evidence。
6. DuckDB 可刪除重建，不是 canonical authority。
7. compatibility bridge 必須有 owner、removal condition、removal test、target stage。
8. B 可消費 Card A projections，但不得執行。
9. C 可執行 admitted specs，但不得重新計算 priority。
10. SignalOccurrence、ConfluenceScore、Radar ranking／view 與 AI explanation 都是 downstream rebuildable projections，不得升格為 Research Truth。
11. Signal historical performance 不得只保存／展示 absolute win rate 或 cumulative forward return 作 evidence authority；必須保留可比較的 baseline、distribution、sample/dependence 與 provenance。

---

## 6. Phased dependency graph

```text
F0 Backlog Reconciliation
        ↓ merge to main
        ├──────────────────────┐
        ↓                      ↓
#13 B0-P1                 #14 C0-P1
Matrix authority          Execution/runner/bridge inventory
Exact count               Benchmark readiness
E1–E4 initial class       Capacity dependencies
        └──────────┬───────────┘
                   ↓
               BC-CP1
                   ↓
        ┌──────────┴───────────┐
        ↓                      ↓
B0-P2 — NOT ADMITTED      C0-P2 — ACCEPTED / CLOSED
Search / overfit /        Capacity / claim / retry /
Regime bundle draft       canary / rollback / removal
        │                      │
        ↓                      │
B1 Combination Kernel          │
        ↓                      │
B2 Candidate Projection ───────┘
        │
        ├──────────────→ C1 Queue Reference Contract
        │                       ↓
        ↓                      C2 Claim / Lease / Idempotency
B3 Daily Research Policy        ↓
        │                      C3 Direct TrialSpec Runner
        ├───────────────────────┤
        ↓                       ↓
B4 Regime Finalist         C4 Shadow / Canary Cutover
        └──────────┬────────────┘
                   ↓
              D0 RegimePolicyBundle
                   ↓
              D1 Promotion / Expiry Gate
                   ↓
              C5 Legacy Bridge Retirement
```

依賴圖只表示 prerequisite，不代表任何 Phase 2 或後續卡已獲授權。ME-D1、TALIB-01、RADAR-01 是獨立 registered donor/product cards，不藉由此 B/C/D prerequisite graph 自動取得 implementation authority。

---

## 7. Backlog cards and admission state

| Card | Current status | Depends on | Bounded scope |
|---|---|---|---|
| F0 Backlog Authority Reconciliation | `ACCEPTED @ 35bb992` | Card A closed | 將 Card A closeout、B0/C0 phased admission 寫入 mainline backlog |
| B0-P1 Matrix Authority Checkpoint | `ACCEPTED / CURRENT_BASELINE` | F0 | matrix authority、dimension taxonomy、exact count、E1–E4 initial classification |
| C0-P1 Execution Inventory Checkpoint | `ACCEPTED / CURRENT_BASELINE` | F0 | execution authority、runner seam、queue/bridge inventory、benchmark readiness |
| BC-CP1 Shared Checkpoint | `DECIDED / ADMIT_C0_PHASE_2` | 兩線 Phase 1 已接受 | standalone current decision；只覆蓋fixed evidence-only C0-P2 scope |
| B0-P2 Search and Final Research Design | `NO_GO_INSUFFICIENT_DECISION_VALUE / NOT_ADMITTED` | BC-CP1 | 缺research-valid full-scan-vs-adaptive gap、larger matrix authority與E4 cadence；不產生futureware |
| C0-P2 Capacity and Cutover Design | `ACCEPTED / SPENT_AND_CLOSED / NO_EXECUTION_AUTHORITY` | BC-CP1＋B0 facts | 已完成capacity、claim/retry、dual-write、canary、rollback、bridge removal設計證據；未准入C1或cutover |
| B1 Discrete Combination Kernel | `PLANNED / NOT_ADMITTED` | B0 fully accepted | count／generate／rank／unrank／chunk／identity／neighbor／constraint validation |
| B2 Research Candidate Projection | `PLANNED / NOT_ADMITTED` | B1 accepted | Coverage＋Learning＋Failure＋budget → `CandidateDecision` shadow projection |
| B3 Daily Adaptive Research Policy | `PLANNED / NOT_ADMITTED` | B2 accepted | coverage/refinement/replication/challenge/rare-regime policy |
| B4 Regime Finalist Projection | `PLANNED / NOT_ADMITTED` | B3＋C3 first-party cycles | 每盤況 primary、robust alternatives、risks、forward prerequisites |
| C1 Canonical Queue Reference Contract | `PLANNED / NOT_ADMITTED` | C0 accepted＋B2 handoff pinned | queue only references canonical identity and admission metadata |
| C2 Claim / Lease / Idempotency | `PLANNED / NOT_ADMITTED` | C1 accepted | race、duplicate、lease expiry、retry、orphan、revocation |
| C3 Direct TrialSpec Runner | `PLANNED / NOT_ADMITTED` | C2 accepted | runner directly consumes immutable TrialSpec；不改 backtest math |
| C4 Shadow / Canary Cutover | `PLANNED / NOT_ADMITTED` | C3＋B3 | old/new parity、deterministic cohort、single writer、rollback |
| C5 Legacy Bridge Retirement | `PLANNED / NOT_ADMITTED` | C4＋per-bridge evidence | 逐橋移除 A6 指定 readers/writers/adapters |
| D0 RegimePolicyBundle | `PLANNED / NOT_ADMITTED` | B4＋C4 evidence | primary、alternatives、fallback、evidence、validity lifecycle |
| D1 Promotion and Expiry Gate | `PLANNED / NOT_ADMITTED` | D0 accepted | development → validation → sealed OOS → forward shadow → review／expiry |
| [#16 TALIB-01 Indicator Provider & Conformance Hardening](https://github.com/bluemaple18-home/NEW-TOP10/issues/16) | `P1 / REGISTERED / NOT_ADMITTED / NO_RUNTIME_AUTHORITY` | Owner future admission＋existing indicator seam audit | TA-Lib adapter、indicator metadata/compatibility gate、behavioral conformance、RunReceipt provenance；**zero canonical Research Matrix dimension growth** |
| [#17 ME-D1 Daily Close Evidence Slice & Future Market Evidence Seam](https://github.com/bluemaple18-home/NEW-TOP10/issues/17) | `P1 / SEAM_AUDITED / NOT_ADMITTED / NO_RUNTIME_AUTHORITY` | existing seam audit complete；Owner admission pending | finalized Daily Close → validated observation → immutable DatasetSnapshot；保留 future Market Evidence seam，**zero Research Spine / Matrix dimension growth** |
| [#18 RADAR-01 Daily Close Signal Radar Projection](https://github.com/bluemaple18-home/NEW-TOP10/issues/18) | `P1 / REGISTERED / NOT_ADMITTED / NO_RUNTIME_AUTHORITY` | Owner future admission＋ME-D1 input seam＋existing Signal/Research Ledger audit | SignalSpec catalog、Daily Close scanner、SignalOccurrence、evidence-backed stats、`Base Rate Before Signal`、deterministic confluence、Radar Projection；**zero Research Spine / Matrix dimension growth** |

---

## 8. B0 Phase 1 contract

Issue authority：[#13](https://github.com/bluemaple18-home/NEW-TOP10/issues/13)

Required outputs：

```text
01-matrix-authority-and-dimension-taxonomy.md
02-exact-count-or-missing-authority-receipt.md
03-e1-e4-initial-cost-classification.md
04-bc-checkpoint-input.md
```

Checkpoint questions：

1. 目前可證明的是 `720`，還是存在可追溯的更大合法空間？
2. 哪些維度／區域可完整掃描？
3. 哪些維度／區域真的需要 adaptive research？
4. C0 應以何種矩陣大小與 evaluation class 規劃容量？
5. 哪些未知阻擋 Phase 2？

Phase 1 不做：

- 完整 search policy；
- full donor landscape；
- overfit guard 定案；
- RegimePolicyBundle 定案；
- B1 admission；
- full matrix campaign。

### Current facts until stronger evidence exists

- 已證明 executable dimensions：`horizon`、`stop_loss_pct`、`take_profit_pct`、`max_group_exposure`。
- 現行 formal executable legal count：`720`。
- `regime_gate`、`risk_guard`、`entry_filter`：contract-dependent／coverage-only。
- 股票「兩百萬級矩陣」尚未由 committed canonical dimension source 證明。

---

## 9. C0 Phase 1 contract

Issue authority：[#14](https://github.com/bluemaple18-home/NEW-TOP10/issues/14)

Required outputs：

```text
01-execution-authority-and-runner-seam.md
02-queue-and-bridge-reader-writer-inventory.md
03-capacity-dependencies-and-benchmark-readiness.md
04-bc-checkpoint-input.md
```

Checkpoint questions：

1. 現有 runner 能否直接接受 canonical TrialSpec？最小缺口在哪？
2. queue／claim／retry 責任目前在哪裡，或是否缺失？
3. A6 bridges 哪些 active、historical、recovery-only、unverified？
4. 哪些 capacity 結論必須等待 B0 matrix size／E1–E4？
5. C0 Phase 2 應限制在哪些 measured gaps？

Phase 1 不做：

- 完整 daily capacity 定案；
- claim／lease／retry 設計定案；
- outbox／broker／workflow runtime 選型；
- canary／rollback／bridge removal 定案；
- C1 admission；
- queue／runner／bridge mutation。

---

## 10. BC-CP1 shared checkpoint

B0-P1 與 C0-P1 必須各自完成獨立驗收後，才進入共同 checkpoint。

Integrator 必須至少裁決：

```text
proven matrix authority and exact count
full-scan / adaptive / hybrid preliminary boundary
direct TrialSpec runner seam
daily capacity dependency envelope
Phase-2 measured gaps
cross-lane authority conflicts
```

唯一允許 verdict：

```text
ADMIT_B0_PHASE_2
ADMIT_C0_PHASE_2
ADMIT_BOTH_PHASE_2_WITH_DEPENDENCIES
REQUEST_BOUNDED_RESEARCH_REPAIR
BLOCK_ON_AUTHORITY_CONFLICT
```

BC-CP1 不得 admission：

```text
B1 / B2 / B3 / B4
C1 / C2 / C3 / C4 / C5
D0 / D1
任何 runtime / queue / runner / production mutation
```

---

## 11. Phase 2 reserved scopes

### B0-P2 — not admitted

Current admission verdict：`NO_GO_B0_PHASE_2_INSUFFICIENT_DECISION_VALUE`。只有形成committed larger matrix authority、同一research-valid workload的full-scan/adaptive comparator，或E2 semantic/performance加E4 cadence的新證據後才可重新裁決。

若未來重新准入，reserved outputs仍限制為：

```text
05-full-scan-vs-adaptive-search-decision.md
06-daily-research-and-refinement-policy.md
07-outcome-evidence-and-overfit-guards.md
08-prior-art-and-open-source-reuse-matrix.md
09-regime-policy-bundle-contract-draft.md
10-b1-admission-recommendation.md
```

### C0-P2 — accepted／spent and closed

BC-CP1 已依 Owner 明確授權、以 current accepted inputs 裁決 `ADMIT_C0_PHASE_2`。下列既有成果只按 evidence-only design scope 接受，該 authority 已用畢並關閉；不得據此重跑或啟動 runtime／cutover：

```text
05-capacity-and-intermediate-reuse-audit.md
06-idempotency-retry-orphan-and-dual-write-gaps.md
07-a6-bridge-to-cutover-map.md
08-shadow-canary-rollback-and-removal-plan.md
09-prior-art-and-open-source-reuse-matrix.md
10-c1-prerequisites-and-admission-blockers.md
```

C1 仍必須等待 B0 fully accepted，以及未來 B2 或等價卡固定：

```text
CandidateDecision → explicit admission → Canonical TrialSpec
```

---

## 12. Trace absorption boundary

Trace 可提供的只有通用離散組合核心：

```text
legal constrained generation
exact counting
deterministic ordering
rank / unrank
chunking
batch / vectorized evaluation
no per-candidate I/O
audit and benchmark receipts
```

明確禁止偷渡：

```text
15% mandatory equal floor
85% adjustable budget
CPC 60 / CPM 40
2M per-order cap
15 strategies / 10 grids
1,961,256 as stock-matrix count
Trace tie-break
winner immediate write-back
order lock / rounding / budget settlement
```

只有股票矩陣自身證明存在 constrained allocation dimension，才可研究 sum/floor/ceiling 與 pairwise weight transfer。

---

## 13. Outcome semantics

三條軸永久分開：

### Execution status

```text
SUCCEEDED
FAILED
CANCELLED
TIMED_OUT
ABORTED
ORPHANED
REJECTED_BEFORE_EXECUTION
```

### Research outcome

```text
POSITIVE
VALID_NEGATIVE
INCONCLUSIVE
UNSTABLE
OVERFIT_RISK
REGIME_SPARSE
```

### Evidence eligibility

```text
ADAPTIVE_ELIGIBLE
DIAGNOSTIC_ONLY
SEALED_VALIDATION_ONLY
INVALID_LINEAGE
UNSUPPORTED
```

`FAILED` 不得轉成 `VALID_NEGATIVE`。只有合法完成且 evidence eligible 的差表現 trial，才是可學習的負向證據。

---

## 14. Prior-art registry by phase

### Phase 1 required scope

B0-P1、C0-P1 只固定直接支援 authority／count／identity／runner seam／benchmark readiness 的來源。

不要求在 checkpoint 前完成完整 donor landscape。

### B0 Phase 2 registered sources

- SciPy QMC／Sobol／LatinHypercube。
- Optuna Ask-and-Tell。
- OSS Vizier。
- Ray Tune SearchAlgorithm／Scheduler boundary。
- SMAC3、DEHB。
- Ax、BoTorch。
- Open Bandit Pipeline（admissibility only）。
- Deflated Sharpe Ratio、Probability of Backtest Overfitting。
- OMI（supplemental evidence semantics only；完整吸收邊界由 ME-D1 固定）。

### C0 Phase 2 registered sources

- Branch by Abstraction、Strangler Fig。
- Google SRE Canary。
- OpenFeature spec／Python SDK／flagd。
- Temporal Worker Versioning。
- DBOS Transact Python。
- Debezium Outbox（conditional only）。
- PostgreSQL `SKIP LOCKED`。
- Ray Tune responsibility boundary。
- Taskiq／Celery（reference only）。

### TALIB-01 — P1 indicator-provider / correctness donor

Issue authority：[#16](https://github.com/bluemaple18-home/NEW-TOP10/issues/16)

Current verdict：

```text
PRIORITY = P1
REUSE = ABSORB / DIRECT_REUSE_WITH_ADAPTER
ADMISSION = REGISTERED / NOT_ADMITTED
RUNTIME_AUTHORITY = NONE
CANONICAL_MATRIX_DIMENSION_DELTA = 0
```

TA-Lib 的定位只允許是 `Technical Indicator Compute Provider`、indicator metadata donor 與 conformance/correctness prior art。不得把它升格為 Market Data Truth、Research Truth、Backtest Engine 或策略有效性的 oracle。

未來若 Owner 明確 admission bounded implementation，P1 scope 限制為：

```text
P1-A indicator provider adapter
P1-B indicator canonical metadata / execution-semantics contract
P1-C compile-time compatibility gate
P1-D behavioral Indicator Conformance Corpus
P1-E RunReceipt indicator provenance
```

其中 provider、provider version、wrapper version、backend、lookback、warmup、unstable period、stability class、history-start policy、missing-data policy **不得因 TA-Lib integration 自動升格為 canonical Research Matrix 維度**。它們應依語意放在 TrialSpec/execution semantics、compile validation、RunReceipt provenance 或 conformance evidence。

允許建立獨立 `Indicator Conformance Matrix` 驗 provider / implementation，但該矩陣不是 Research Matrix，不得改變 canonical research-space count。

最低 acceptance 邊界：

- TA-Lib 導入造成的 canonical Research Matrix dimension growth = `0`；
- invalid indicator configuration 在 execution 前被 compatibility gate 拒絕；
- conformance corpus 至少覆蓋 full-range/partial-range、不同 history start、flat price、zero close、tiny-scale values、NaN gaps、period/session boundaries 與已知歷史 defect classes；
- wrapper `set/get` round-trip 不得單獨作 correctness proof，必須驗 observable behavior；
- material provider/core/wrapper/backend/input/output provenance 可由 RunReceipt／其 referenced artifact 重建；
- provider swap 不得要求改寫 Research Spine、核心 strategy semantics 或 backtest authority。

P2 watch only：TA-Lib current `main` 的 0.8.x streaming/codegen 只作 donor/reference；必須等正式 0.8.x release pin 且證明 batch-vs-stream conformance，才可另行裁決 production adoption。沒有多 executor language 的 measured requirement，不建立 NEW-TOP10 自有 general indicator codegen subsystem。

Hard stops：

```text
NO new canonical research dimensions solely for TA-Lib concerns
NO Research Spine replacement
NO Backtest/Strategy Matrix replacement
NO Existing Backtest Engine replacement
NO TA-Lib formula copy into Research Spine authority code
NO direct StrategySpec/TrialSpec binding to Python talib.* implementation detail
NO TA-Lib output as research oracle
NO unreleased 0.8.x streaming production dependency
NO runtime / queue / runner / schema / scheduler / publish / production authority from this registration
```

Pinned research sources for future admission review：

- `https://github.com/TA-Lib/ta-lib`
- `https://ta-lib.org/functions/`
- `https://ta-lib.org/api/`
- `https://ta-lib.org/functions/stability.html`
- `https://github.com/TA-Lib/ta-lib/blob/main/CLAUDE.md`
- `https://github.com/TA-Lib/ta-lib/blob/main/docs/streaming-api-design.md`
- `https://github.com/TA-Lib/ta-lib/issues/98`
- `https://github.com/ta-lib/ta-lib-python`
- `https://github.com/ta-lib/ta-lib-python/issues/752`

2026-09-06 research observation：latest formal core release observed=`v0.7.1`（2026-07-03）；current main 含未正式 release 的 0.8.1 work；license=`BSD-3-Clause`。若未來 admission 時 upstream 已前進，必須重新 pin exact release/SHA 與 wrapper version，不得沿用本次 observed version 作永久 authority。

### ME-D1 — P1 Daily Close evidence slice / future Market Evidence seam

Issue authority：[#17](https://github.com/bluemaple18-home/NEW-TOP10/issues/17)

Owner ruling / current verdict：

```text
PRIORITY = P1
REUSE = ARCHITECTURE_ABSORB / EXTEND_EXISTING
ADMISSION = REGISTERED / NOT_ADMITTED
RUNTIME_AUTHORITY = NONE
CURRENT_MARKET_DATA_SCOPE = FINALIZED_DAILY_CLOSE_ONLY
TARGET_MARKET_EVIDENCE_ARCHITECTURE = PRESERVED / DEFERRED
RESEARCH_SPINE_DELTA = 0
CANONICAL_MATRIX_DIMENSION_DELTA = 0
```

2026-09-07 已在固定基線 `f787437e2c88a327ad7be210f31d790fa96ee3f7` 完成 bounded read-only seam audit；證據位於 `docs/evidence/ME-D1-DAILY-CLOSE-SEAM-AUDIT-20260907.md`。Audit 確認既有 provider、validation snapshot、ETL parquet 與 DatasetBundle seams 可延伸，也確認 production 尚無 immutable provider-neutral Daily Close snapshot／finalization／price-basis／fetch lineage。狀態只提升為 `MEASURED_GAP_CONFIRMED / READY_FOR_OWNER_ADMISSION_DECISION`，**不構成 ME-D1 admission 或 implementation authority**。

此卡固定兩層而不可混為同一 implementation scope：

```text
CURRENT / first bounded slice if separately admitted
Daily Close Source
        ↓
Daily Close Adapter
        ↓
Validated DailyBar / DailyClose Observation
        ↓
Immutable DatasetSnapshot
        ↓
ResearchDefinition / Canonical TrialSpec / Matrix
        ↓
Existing Backtest Engine

TARGET / preserved architecture, not admitted now
Provider Adapter(s)
        ↓
Raw Fetch Receipt / MarketObservation
        ↓
Pure Resolver
  selection · freshness · fallback · repair/reconciliation
        ↓
DatasetSnapshot + MarketEvidenceManifest
        ↓
Research Spine
```

`DatasetSnapshot` 是 Market Evidence 與 Research Spine 的 handoff seam。未來增加 provider、resolver 或 richer market evidence 時，Research Spine／Matrix／Existing Backtest Engine 不應因 provider architecture 而改寫。

永久 authority boundary：

```text
MarketObservation != ResearchObservation
Dataset Registry != Research Ledger
Capability Registry != Parameter Catalog
Market Evidence Plane != Research Spine
OMI != runtime dependency
```

若未來 Owner 明確 admission ME-D1 bounded implementation，Daily Close 最小 data/evidence contract 必須由既有 contract 映射或等價欄位覆蓋：

```text
instrument / symbol identity
trading_date
open / high / low / close (when daily OHLC is supplied)
volume (when supplied)
price_basis / adjustment_policy
source / provider identity
observed_at / fetched_at
finalization_status
dataset_version / dataset_fingerprint
missing / duplicate status
calendar / trade-date semantics
lineage to exact DatasetSnapshot consumed by the trial
```

以上是 data contract / provenance / reproducibility semantics，**不是 Research Matrix 維度**。provider、source、freshness、finalization、version、adjustment policy 不得因 Market Evidence work 自動膨脹 canonical research-space count；只有本來就是研究問題的語意才可由另卡明確裁決為研究維度。

最低 deterministic validation：

- missing 不得 silent convert to `0`；
- duplicate `(instrument, trading_date)` 必須 reject 或依固定 deterministic rule 顯式分類／解決；
- canonical research dataset 預設只消費 finalized EOD data；
- raw / adjusted price basis 必須明示，不得在相同 dataset identity 下 silent drift；
- 若保留 OHLC，必須驗基本值域／關係 invariant，例如 `low <= open/close <= high`；
- 缺交易日／gap 保留為 evidence，不得默默製造不存在的 bar；
- 同一 immutable `DatasetSnapshot` / fingerprint 必須代表同一 research input truth，可被重跑與稽核；
- backtest／strategy authority 不得直接呼叫 provider API 或把 mutable CSV path 當 implicit canonical truth。

現在要保留但不必先長出完整 subsystem 的 seams：

```text
Source Adapter Boundary
DatasetSnapshot Contract
Evidence / Lineage Metadata
Dataset Version / Fingerprint
reserved MarketEvidenceManifest boundary
```

OMI prior-art absorption：

```text
repo = https://github.com/lulu930128/open-market-intelligence
observed main = dce83d63bc88da475001ae787c43a4ca848784e7
README version = 4.5.0
license = Apache-2.0
role = TARGET-ARCHITECTURE REFERENCE / FUTURE MARKET-EVIDENCE DONOR
runtime adoption = DEFERRED
```

只吸收下列 architecture concepts，不整包搬 OMI product/runtime：

1. provider → provider-neutral/canonical observation → resolver 的 responsibility split；
2. resolver 負責 resolve，不應在 read path 偷做 acquisition／repair；
3. source、time、limitations、lineage 與 evidence 一起傳遞；
4. session、finalization、authority、release、freshness、reconciliation 是正交語意，不應壓成單一 health/freshness flag；
5. dataset／capability／lineage 等 executable truth 應由 typed contracts/registries 擁有，不由 UI 或文件複製 inventory 當 authority。

Daily Close 第一階段只實作上述概念的最小適用子集；較完整的 session/freshness/authority/release/reconciliation/provider-role semantics 保留為 target seam，等 measured need 再 admission。

Explicitly deferred / NOT ADMITTED：

```text
intraday / live quotes
multi-provider automatic selection / fallback
broker API / account integration
Level 2 / order book
live futures feeds
fundamentals / news / ownership / institutional feeds
live freshness arbitration
automated repair / reconciliation runtime
cross-market synchronization
portfolio live valuation
OMI UI / Decision Dock / MCP
full provider registry / market-data runtime platform
```

Future admitted ME-D1 acceptance boundary：

- canonical Research Matrix dimension growth = `0`；
- Research Spine 與 Existing Backtest Engine authority 不變；
- data acquisition 隔離在 adapter seam，backtest 不直接 fetch；
- trial 可定位 exact immutable `DatasetSnapshot` / fingerprint；
- raw/adjusted price basis、EOD finalization、gap/missing/duplicate semantics 明確且有 deterministic tests；
- future resolver/provider expansion 可插在 DatasetSnapshot 上游而不改 Research Spine／Matrix；
- OMI 不成為 runtime dependency；
- full Market Evidence Plane 必須從 measured need 另行 admission，不得由 ME-D1 自動展開。

Hard stops：

```text
NO full Market Evidence runtime from this registration
NO live / intraday expansion from this registration
NO automatic multi-provider fallback from this registration
NO Research Spine replacement
NO Existing Backtest Engine replacement
NO canonical Research Matrix dimension growth
NO provider-specific calls embedded in TrialSpec / strategy authority
NO silent source / adjustment / finalization drift
NO runtime / queue / runner / scheduler / publish / production authority
```

Pinned OMI sources for future admission review：

- `https://github.com/lulu930128/open-market-intelligence`
- `https://github.com/lulu930128/open-market-intelligence/blob/dce83d63bc88da475001ae787c43a4ca848784e7/README.md`
- `https://github.com/lulu930128/open-market-intelligence/blob/dce83d63bc88da475001ae787c43a4ca848784e7/docs/architecture/index.md`
- `https://github.com/lulu930128/open-market-intelligence/blob/dce83d63bc88da475001ae787c43a4ca848784e7/docs/architecture/BackendArchitecture.md`
- `https://github.com/lulu930128/open-market-intelligence/blob/dce83d63bc88da475001ae787c43a4ca848784e7/docs/architecture/MarketTemporalContract.md`

若未來 admission 時 OMI upstream 已前進，必須重新 pin exact release/SHA 並做 delta check；本次 observed SHA 只保存 2026-09-06 donor research provenance，不是永久 implementation authority。

### RADAR-01 — P1 Daily Close signal-radar product projection

Issue authority：[#18](https://github.com/bluemaple18-home/NEW-TOP10/issues/18)

Owner ruling / current verdict：

```text
PRIORITY = P1
REUSE = EXTEND_EXISTING / PRODUCT_PROJECTION
ADMISSION = REGISTERED / NOT_ADMITTED
RUNTIME_AUTHORITY = NONE
CURRENT_INPUT_SCOPE = FINALIZED_DAILY_CLOSE_ONLY
RESEARCH_SPINE_DELTA = 0
CANONICAL_MATRIX_DIMENSION_DELTA = 0
AI_DECISION_AUTHORITY = NONE
RESEARCH_QUALITY_RULE = BASE_RATE_BEFORE_SIGNAL
```

定位只允許是 **Research Spine／Research Ledger 之上的 rebuildable product projection**：

```text
ME-D1 finalized Daily DatasetSnapshot
        ↓
Indicator Provider Boundary
  ├─ existing/native
  └─ TALIB-01 future adapter (only if separately admitted)
        ↓
Radar-eligible SignalSpec
        ↓
Daily Market-wide Signal Scanner
        ↓
SignalOccurrence
        ↓
Evidence Comparison
  conditional outcome vs relevant base rate
        ↓
Deterministic Confluence Engine
        ↓
Radar Projection
  ├─ bullish
  ├─ bearish
  └─ later personalized views
        ↓
optional AI explanation (P2, downstream only)
```

永久 semantic split：

```text
Indicator != Signal != Research Trial != Radar Rank
Market / Index Base Rate != Individual-stock Signal Evidence
```

- `Indicator` 是計算結果／feature primitive，例如 `RSI(14)`；
- `SignalSpec` 是 deterministic condition，例如 `RSI crosses above 30` 或已治理的 composite condition；
- `TrialSpec / Matrix` 是研究與驗證空間；
- `SignalOccurrence / ConfluenceScore / Radar view` 是可重建產品 projection；
- diversified-index 長期歷史只能作 context/base-rate donor，不得直接替 individual-stock signal 提供 validity。

TALIB-01 若未來 admission，只可提供 indicator computation / metadata / conformance；不得因 RADAR-01 被強制施工，也不得成為 SignalSpec、研究 admission 或 Radar rank authority。

未來若 Owner 明確 admission bounded implementation，P1 scope 限制為：

```text
P1-A Signal Catalog / SignalSpec contract
P1-B finalized-Daily market-wide scanner
P1-C SignalOccurrence + Radar Projection
P1-D evidence-backed historical statistics + relevant base-rate comparison
P1-E deterministic confluence ranking with redundancy policy
```

SignalSpec 最小語意應由既有 contract 映射或等價欄位覆蓋：

```text
signal_id / signal_version
name / category / direction
deterministic rule reference
required indicators / features
required dataset contract
evaluation horizon
regime applicability when evidence-backed
research_evidence_ref
eligibility_status
educational_explanation_ref
```

`SignalOccurrence` 至少應能追到：instrument、trading_date、SignalSpec version、direction、input DatasetSnapshot fingerprint、indicator/provider provenance reference、rule evaluation result、research_evidence_ref 與 projection build version。它不得成為第二套 canonical signal/research truth。

#### Base Rate Before Signal — permanent research-quality rule

Radar 不得把「signal 之後常上漲」直接等同「signal 有 edge」。任何 material historical performance claim，至少必須能比較：

```text
ConditionalOutcome(signal, horizon, universe, regime?)
vs
RelevantBaseRate(horizon, universe, regime?)
```

例如 `20D positive rate = 64%` 沒有獨立意義；若同 universe / horizon 的 unconditional positive rate 是 `61%`，incremental edge 只有 `+3pp`。只有 absolute signal statistic、沒有 baseline comparator 的結果不得作 Radar eligibility / ranking 的主要 evidence。

最低 comparison semantics 或可追溯等價欄位：

```text
signal_sample_size
signal_effective_sample_size (when dependence matters)
forward_horizon
conditional_positive_rate / conditional_return_distribution
baseline_definition
baseline_sample_size
baseline_positive_rate / baseline_return_distribution
incremental_edge / effect-size summary
regime_match policy
universe definition
OOS / sealed / forward status
max adverse excursion / downside summary
provenance / evidence version
```

Baseline 必須和研究問題對齊。不得拿不相干的 broad-market 長期平均去比較一個特定 universe、特定 horizon 或特定 regime 的 signal；需要時應有 unconditional、universe-matched、regime-matched baseline，但不得為了讓 signal 看起來好而事後挑 baseline。

#### Average is not a sufficient observation model

`mean_return`、`win_rate`、單一 cumulative-return 數字都不能單獨代表 signal quality。底層 evidence/projection reference 至少要能追到適用的：

```text
sample_size / effective sample size
forward horizon
return distribution / median / robust summary
downside / drawdown / max adverse excursion
regime-conditioned result
baseline comparator / effect size
OOS / sealed / forward status
freshness / evidence version
Research Ledger / receipt reference
```

UI 可以縮減欄位，但 authority 不可縮成一個勝率或平均值。

#### Dependence / overlapping-window caution

長 horizon rolling windows、相鄰 crash events、同 regime cluster 不得機械地當成獨立 samples。若 observation window 高度重疊或事件集中在同一市場 episode，必須顯式記錄 dependence / clustering，必要時用 effective sample size、episode count、block/bootstrap 或等價方法表達不確定性。

因此：

```text
80 overlapping 30Y windows != 80 independent 30Y experiments
6 extreme months in one depression-era cluster != 6 fully independent regimes
```

不得把 long-horizon cumulative return 或少數 crash-after-return observation 直接編譯成交易 SignalSpec。

#### Market / country / asset provenance

任何 long-horizon base-rate claim 必須帶至少：

```text
market / country
index or universe definition
sample period
nominal vs real
price return vs total return / dividend treatment
fees / tax assumptions when material
currency basis when material
overlapping-window policy
```

美國 diversified index 歷史不自動外推到台股個股、單一股票、其他國家或其他 asset class。Bessembinder et al. 的全球個股研究顯示 long-run stock returns 高度 skewed；這只作反誤用 donor，不變成任何特定 signal 的 authority。

Signal eligibility 必須阻擋 feature zoo：

```text
Candidate Signal
      ↓
Research Matrix / governed evaluation
      ↓
Conditional Outcome vs Relevant Base Rate
      ↓
Evidence / acceptance criteria
      ↓
Radar Eligible SignalSpec
      ↓
Daily scanner
```

競品有 36、50 或 200 個訊號都不是 NEW-TOP10 的數量目標。沒有最低研究 evidence 的 signal 不因 UI 需求直接進 Radar。

Confluence 第一版必須 deterministic、可稽核；LLM 不得計算 authoritative rank。單純 `hit count` 不能直接當有意義的共振分數，因 MA5/MA10/MA20／多頭排列等高度相關訊號會重複投票。至少先固定 signal-family grouping 與 redundancy/correlation policy；精確 scoring math 若會影響 production ranking，仍需另行 evidence/admission。

P2 / Later only：

```text
P2 AI one-line explanation = structured deterministic evidence → LLM explanation only
P2 personalized Radar Profile = filter/weight already-admitted SignalSpecs only
LATER push notification / intraday radar = separate market-data/runtime admission required
```

AI 可以解釋「為何入榜、相對 base rate 的 edge、證據、反證、資料限制」，不可創造 authoritative signal、改寫 SignalOccurrence、覆蓋 Research Ledger evidence 或取得 rank authority。

Explicitly deferred / NOT ADMITTED：

```text
intraday / live radar
realtime provider / broker integration
multi-provider resolver / fallback / repair runtime
fundamental / institutional / branch-flow sources only to imitate competitor breadth
blind signal-count expansion / feature zoo
new canonical Research Matrix dimensions
second canonical signal/research truth store
AI-generated authoritative signals or AI ranking authority
raw hit-count ranking without documented redundancy policy
absolute win-rate marketing without relevant baseline comparison
long-horizon/index historical regularities compiled directly into individual-stock signals
scheduler / publish / production changes
Existing Backtest Engine authority changes
```

Future admitted RADAR-01 acceptance boundary：

- canonical Research Matrix dimension growth = `0`；
- Research Spine 與 Existing Backtest Engine authority 不變；
- scanner 只消費 finalized immutable Daily `DatasetSnapshot`，不直接 fetch provider；
- 相同 dataset fingerprint + SignalSpec versions + indicator semantics 產生 deterministic occurrences；
- `SignalOccurrence`／Radar 可由上游 contracts/evidence 重建；
- displayed historical stats 可追到 governed research evidence，`win_rate`／mean／cumulative return 不單獨成 authority；
- material signal-performance claim 有 relevant horizon/universe/regime baseline comparator，且能表達 incremental edge/effect size；
- overlapping windows / clustered events 不被誤算為完全獨立 samples；
- long-horizon claims 保留 market/country/index/dividend/nominal-real/window provenance；
- Radar-eligible SignalSpec 必須通過明確 evidence／eligibility gate；
- confluence 不把高度相關 signal variants 當獨立票無限累加；
- AI explanation 可完全移除而不影響 deterministic signal/rank/evidence inspectability；
- current market-data scope 仍是 Daily Close；不要求 intraday 或 provider-platform expansion；
- 本卡不取得 scheduler/publish/production authority。

Hard stops：

```text
NO Research Spine replacement
NO Research Matrix replacement or canonical dimension growth
NO Existing Backtest Engine replacement
NO second canonical research/signal truth
NO feature-zoo target based on competitor signal count
NO absolute win-rate / mean-only evidence authority
NO baseline cherry-picking to manufacture edge
NO treating overlapping windows as independent evidence
NO U.S.-index long-run statistics as individual-stock guarantee
NO AI authority over signal generation or ranking
NO intraday / live / provider expansion from RADAR-01
NO runtime / queue / runner / scheduler / publish / production authority
```

Research-quality donor provenance：

- Ben Carlson, `10 Things You Need to Know About Investing in Stocks`, A Wealth of Common Sense, 2026-08-27: `https://awealthofcommonsense.com/2026/08/10-things-you-need-to-know-about-investing-in-stocks/`。吸收的是 market base-rate、lumpy-return、drawdown、long-horizon sample caution；不採其美國市場歷史統計為 NEW-TOP10 signal validity。
- Hendrik Bessembinder, Te-Feng Chen, Goeun Choi, K. C. John Wei, `Long-Term Shareholder Returns: Evidence from 64,000 Global Stocks`, Financial Analysts Journal 79(3), 2023, DOI `10.1080/0015198X.2023.2188870`。研究涵蓋 1990–2020 逾 64,000 支全球普通股；用來固定 individual-stock return skewness / index-to-stock extrapolation caution，不當成策略 oracle。

Product donor provenance：Owner 於 2026-09-06 提供一個 post-close 全市場 signal-radar pattern，包含分類訊號、同日多訊號共振、歷史統計／教學與一句話 AI 解讀。只吸收 interaction/product architecture；未提供可驗證 public source URL，因此 backlog 不捏造 donor URL，也不採信其 proprietary signal formulas、marketing claims 或回測勝率為 prior-art evidence。

每一個實際使用的 donor 都必須固定：

```text
source repository / publication
exact commit / tag / version / publication date
license when applicable
relevant source and tests / methodology
what to absorb
what not to absorb
existing NEW-TOP10 equivalent seam
why custom code remains necessary
```

Reuse taxonomy：

```text
ALREADY_EXISTS
USE_AS_IS
CONFIGURE
WRAP
ADAPT
COPY_CODE
CUSTOM_REQUIRED
CONDITIONAL
RESEARCH_ONLY
DEFER
REFERENCE_ONLY
REJECT
```

優先順序：`EXTEND_EXISTING > ADD_SUBSYSTEM`。

---

## 15. Cross-lane evidence contract

每個 material claim 至少記錄：

```text
claim_id
claim
classification
source_repo
source_sha_or_version
source_path_or_official_url
source_range_or_section
observed_at
confidence
authority_level
conflict_with
implication
open_question
owner
```

個別證據缺失時，標記後繼續：

```text
UNKNOWN
UNPINNED_RUNTIME_ARTIFACT
UNPINNED_CROSS_PROJECT_DONOR
UNMEASURED_CAPACITY
UNVERIFIED_BRIDGE_ACTIVITY
```

只有以下情況整卡停止：

- committed governing authorities materially conflict；
- canonical identity grain 無法確定；
- terminal receipt boundary 無法確定；
- exact matrix count 必須靠捏造維度／限制；
- 必須修改 runtime 才能回答；
- 研究觸碰 production、scheduler/publish 或不當使用 sealed evidence。

---

## 16. Operational lane

- Issue #9：`OPEN / LONG-TERM HARDENING`；保留為獨立 operational lane。
- Issue #10：`CLOSED / ACCEPTED`；不是現行可執行 lane，不得因歷史 body 或留言重新派工。

B0／C0：

- 不得修改 scheduler、publish、OpenClaw、Discord、ranking、model 或 production；
- 不得把 operational urgency 當成 research authority；
- 不得因 #9 仍 open 阻擋純 read-only Phase 1；
- 若 benchmark 會干擾 operational lane，立即停止該 benchmark 並標記 `OPERATIONAL_INTERFERENCE_RISK`。

---

## 17. Monitoring and current instruction

節省監工模式：

- Phase 1 各自只交四份文件。
- 不在每個小發現重審。
- BC-CP1已完成；B0-P2 admission已裁決NO-GO。Research Spine目前沒有active execution frontier。
- TALIB-01 只是 P1 donor registration；未經 Owner 後續明確 admission 不得施工，也不得擴大 Research Matrix。
- ME-D1 已完成 bounded read-only seam audit，但仍是 P1 Daily Close / future Market Evidence seam registration；未經 Owner 後續明確 admission 不得施工，完整 Market Evidence runtime 仍 deferred。
- RADAR-01 只是 P1 Daily Close product-projection registration；未經 Owner 後續明確 admission 不得施工，不得取得 AI/ranking/runtime authority，也不得藉 Radar 需求擴市場資料範圍；`Base Rate Before Signal` 是未來 bounded implementation 的 acceptance requirement，不是新的 runtime subsystem。
- 卡片研究完成不等於下一張自動 admission。
- B 不得因最優化需求取得 execution authority。
- C 不得因可靠執行需求取得 decision authority。
- D 不得因歷史高分跳過 sealed OOS、forward shadow、review、expiry 與 fallback。

目前施工指令：

```text
CURRENT:
- accepted non-production baseline = 78d3b3b
- F0 / B0-P1 / C0-P1 = ACCEPTED
- R13 = REGISTERED_FORWARD_BUNDLE_VERIFIED / downstream_authority=NONE
- R14 = NO_GO_R14_INSUFFICIENT_DECISION_VALUE
- TALIB-01 = P1 REGISTERED / NOT_ADMITTED / NO_RUNTIME_AUTHORITY / MATRIX_DIMENSION_DELTA=0
- ME-D1 = P1 SEAM_AUDITED / MEASURED_GAP_CONFIRMED / NOT_ADMITTED / FINALIZED_DAILY_CLOSE_ONLY / TARGET_ARCHITECTURE_PRESERVED / NO_RUNTIME_AUTHORITY / MATRIX_DIMENSION_DELTA=0
- RADAR-01 = P1 REGISTERED / NOT_ADMITTED / DAILY_CLOSE_PRODUCT_PROJECTION / BASE_RATE_BEFORE_SIGNAL / AI_AUTHORITY=NONE / NO_RUNTIME_AUTHORITY / MATRIX_DIMENSION_DELTA=0

REQUIRED NEXT GATE:
- no active Research Spine execution gate
- B0-P2 = NO_GO_INSUFFICIENT_DECISION_VALUE
- C0-P2 = ACCEPTED / SPENT_AND_CLOSED / NO_EXECUTION_AUTHORITY
- TALIB-01 requires a future explicit Owner admission before bounded implementation
- ME-D1 seam audit is complete；requires a future explicit Owner admission before any Daily Close implementation；full Market Evidence Plane requires a separate measured-need admission
- RADAR-01 requires a future explicit Owner admission after ME-D1 input seam + existing Signal/Research Ledger audit; any material signal-performance claim must compare against a relevant base rate; confluence production ranking requires bounded evidence/admission
- independent Forecast / TFM3 fork requires its own preflight and authority

NOT ADMITTED:
- B0 Phase 2
- B1 / B2 / B3 / B4
- C1 / C2 / C3 / C4 / C5
- D0 / D1
- TALIB-01 provider implementation / conformance execution / 0.8.x streaming adoption
- ME-D1 Daily Close implementation / data migration / provider rollout
- full Market Evidence provider resolver / fallback / repair / live-intraday runtime
- RADAR-01 SignalSpec/scanner/SignalOccurrence/confluence/Radar implementation
- RADAR-01 AI explanation / personalized profile / push / intraday expansion

NO CHANGE AUTHORIZED:
- runtime / queue / runner / schema / database
- model / ranking / backtest math
- scheduler / publish / production
```

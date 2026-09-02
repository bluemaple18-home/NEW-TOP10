# NEW-TOP10 Research Spine Backlog

更新：2026-09-02

狀態：`CARD_A_CLOSED / F0_ACCEPTED / B0_P1_AND_C0_P1_ACCEPTED / CURRENT_TIP_BASELINE_ACCEPTED / BC_CP1_DECIDED / C0_P2_ACCEPTED_CLOSED / B0_P2_AND_B1_TO_D1_NOT_ADMITTED / R14_NO_GO`

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
accepted local main  = 78d3b3b1d246dd37f8a1094ff85ba5175dae995e
local origin/main ref = 5d7c5296beb912827aaa828f4d3b68d72dcec16f
authority note       = local main acceptance is not a push/deploy authorization
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
- OMI：market evidence／lineage supplemental prior art，不是 B／C governing architecture。

---

## 2. Current unique frontier

### B0-P2 admission decision — current

```text
F0                         = ACCEPTED
B0-P1 / C0-P1              = ACCEPTED
CURRENT INTEGRATED BASELINE = ACCEPTED / NON_PRODUCTION
BC-CP1                     = ADMIT_C0_PHASE_2 / DECIDED
C0-P2                      = ACCEPTED / SPENT_AND_CLOSED
B0-P2 / B1 / C1            = NOT_ADMITTED
R14                         = NO_GO / NOT_ADMITTED
```

已 merge 的 C0 Phase 2 與 BC-CP2 R1–R14 文件保留為設計／證據歷史；BC-CP1 decision只讓既有C0-P2 scope完成權限閉環，不產生current execution authority。下一個可裁決點是B0-P2 admission；不得直接跳到B1、C1或implementation。

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

依賴圖只表示 prerequisite，不代表任何 Phase 2 或後續卡已獲授權。

---

## 7. Backlog cards and admission state

| Card | Current status | Depends on | Bounded scope |
|---|---|---|---|
| F0 Backlog Authority Reconciliation | `ACCEPTED @ 35bb992` | Card A closed | 將 Card A closeout、B0/C0 phased admission 寫入 mainline backlog |
| B0-P1 Matrix Authority Checkpoint | `ACCEPTED / CURRENT_BASELINE` | F0 | matrix authority、dimension taxonomy、exact count、E1–E4 initial classification |
| C0-P1 Execution Inventory Checkpoint | `ACCEPTED / CURRENT_BASELINE` | F0 | execution authority、runner seam、queue/bridge inventory、benchmark readiness |
| BC-CP1 Shared Checkpoint | `DECIDED / ADMIT_C0_PHASE_2` | 兩線 Phase 1 已接受 | standalone current decision；只覆蓋fixed evidence-only C0-P2 scope |
| B0-P2 Search and Final Research Design | `NOT_ADMITTED` | BC-CP1 | search policy、overfit guards、full donor matrix、RegimePolicyBundle draft |
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

只有 BC-CP1 接受後才可考慮：

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
- OMI（supplemental evidence semantics only）。

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

每一個實際使用的 donor 都必須固定：

```text
source repository
exact commit / tag / version
license
relevant source and tests
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
- BC-CP1 已完成 standalone current-input裁決；下一個正式裁決點是B0-P2 admission decision。
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

REQUIRED NEXT GATE:
- B0-P2 admission decision
- C0-P2 = ACCEPTED / SPENT_AND_CLOSED / NO_EXECUTION_AUTHORITY
- no B0-P2 execution before a separate verdict

NOT ADMITTED:
- B0 Phase 2
- B1 / B2 / B3 / B4
- C1 / C2 / C3 / C4 / C5
- D0 / D1

NO CHANGE AUTHORIZED:
- runtime / queue / runner / schema / database
- model / ranking / backtest math
- scheduler / publish / production
```

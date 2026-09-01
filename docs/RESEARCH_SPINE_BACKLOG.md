# NEW-TOP10 Research Spine Backlog

更新：2026-09-01

狀態：`CARD_A_CLOSED / B0_AND_C0_PARALLEL_READ_ONLY_RESEARCH_READY / B1_TO_D1_NOT_ADMITTED`

Repository：`bluemaple18-home/NEW-TOP10`

母卡：[#1 CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1](https://github.com/bluemaple18-home/NEW-TOP10/issues/1)

> 本檔是 NEW-TOP10 Research Spine 的 canonical domain backlog、依賴順序與 admission gate。
>
> GitHub Issues 是可派工工作卡；本檔決定哪些卡現在可動、哪些只可研究、哪些仍被依賴阻擋。不得掃描 Issue 後自行跳卡。
>
> AI Core 的共用治理 authority 是 `bluemaple18-home/aicore` 的 `docs/ai-core-backlog.md`。量化研究只增加 domain specialization，不得在 NEW-TOP10 建立第二套通用 execution、authority、queue、ledger 或 lifecycle runtime。

---

## 0. Pinned baselines

### NEW-TOP10

```text
origin/main = 2b9eccda11433016261c529ad1f94352bcfcd6d5
commit      = merge: integrate A6 research spine closure
```

此 SHA 是 B0／C0 建卡時的 observed baseline。正式執行時若 `origin/main` 已前進，研究 owner 必須重新固定最新 clean baseline，記錄 delta，不能默默沿用舊 SHA。

### AI Core

```text
repository  = bluemaple18-home/aicore
origin/main = 26eb42f8e401807d3dbd6030171b9dfeb58207fb
canonical   = docs/ai-core-backlog.md
```

本機未提交的 AI Core working-tree 內容不是 current authority。dated backlog、舊 `.work`、reading map 與實驗只能作 historical evidence。

### Historical drafts

- `aeae2c3` 只作歷史草稿／問題清單來源，不 merge、不作 execution base、不以 rebase 後直接續作。
- Trace V2 只有在固定可驗證來源後，才可作 cross-project combination-kernel donor；無 pin 時標示 `UNPINNED_CROSS_PROJECT_DONOR`。
- OMI 只作 market evidence／lineage supplemental prior art，不是 B／C governing architecture。

---

## 1. Current research frontiers

目前允許兩條**平行唯讀研究線**：

- [#13 B0 — Matrix Authority and Search Design](https://github.com/bluemaple18-home/NEW-TOP10/issues/13)  
  `READY_FOR_READ_ONLY_RESEARCH / NO_IMPLEMENTATION / NO_QUEUE_WRITE`
- [#14 C0 — Execution Capacity and Control Cutover Precheck](https://github.com/bluemaple18-home/NEW-TOP10/issues/14)  
  `READY_FOR_READ_ONLY_PRECHECK / ISOLATED_BENCHMARK_ALLOWED / NO_CUTOVER`

兩張卡都可以立即由乾淨 worktree 啟動，但不得自動放行 B1 或 C1。

### 允許

- 讀取固定 SHA 的 repo、Issue、committed evidence 與現行 AI Core。
- 查閱並固定官方文獻、開源 repo、tag／commit、license、source／tests。
- 產生 docs/evidence、authority map、cost benchmark receipt、prior-art reuse matrix 與 admission recommendation。
- C0 可用 immutable inputs，在隔離 temporary output 中執行無外部 side effect 的 benchmark。

### 禁止

- 修改 runtime、schema、database、runner、queue、scheduler、model、backtest math、ranking、publish 或 production。
- 安裝 optimizer、workflow server、broker、CDC、outbox、feature-flag service 或新 task runtime。
- 讓 B 寫 queue、claim、retry 或執行工作。
- 讓 C 重算 candidate value、priority 或研究排序。
- 啟動 B1–B4、C1–C5、D0–D1。
- 以 Trace 的產品規則替股票矩陣補齊未知欄位。

### Operational lane

Issue #9／#10 的 scheduler、daily publish 與 operational hardening 是獨立 lane。B0／C0 不得對其執行 mutation；其現況以各 Issue 最新 current-state evidence 為準，不由本 backlog 猜測或覆寫。

---

## 2. Product target

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

## 3. Card A closeout

Card A 的 truth migration 與 learning core 已完成，母卡與 A0–A6 均已關閉／主線接受：

- [x] [#2 A0 — Precheck and Prior Art](https://github.com/bluemaple18-home/NEW-TOP10/issues/2) — `COMPLETE / ACCEPTED`
- [x] [#3 A1 — Canonical Identity and Parameter Catalog](https://github.com/bluemaple18-home/NEW-TOP10/issues/3) — `COMPLETE / MAINLINE_ACCEPTED`
- [x] [#4 A2 — ExecutionIntent and Immutable Receipt](https://github.com/bluemaple18-home/NEW-TOP10/issues/4) — `COMPLETE / MAINLINE_ACCEPTED`
- [x] [#5 A3 — Legacy Migration and Reconciliation](https://github.com/bluemaple18-home/NEW-TOP10/issues/5) — `COMPLETE / MAINLINE_ACCEPTED`
- [x] [#6 A4 — Rebuildable Ledger and Observations](https://github.com/bluemaple18-home/NEW-TOP10/issues/6) — `COMPLETE / MAINLINE_ACCEPTED`
- [x] [#7 A5 — Matched Learning Projection](https://github.com/bluemaple18-home/NEW-TOP10/issues/7) — `COMPLETE / MAINLINE_ACCEPTED`
- [x] [#8 A6 — Deprecation, Rebuild and Bridge Removal Gates](https://github.com/bluemaple18-home/NEW-TOP10/issues/8) — `COMPLETE / MAINLINE_ACCEPTED`
- [x] [#1 Card A parent](https://github.com/bluemaple18-home/NEW-TOP10/issues/1) — `CLOSED / ACCEPTED`

Card A established these permanent invariants:

1. Canonical truth is immutable spec／intent／attempt／receipt／artifact／migration evidence.
2. Observation、Eligibility、Failure、Learning、Fog Map、Priority、Candidate、Queue 與 PM/Ops 都是 rebuildable projections.
3. `combo_id` is legacy-only and cannot be a new canonical FK.
4. Requested and executed truth must remain distinguishable.
5. Failure and orphan states are first-class execution evidence.
6. DuckDB is deletable and rebuildable, not canonical authority.
7. Compatibility bridges are temporary and require owner、removal condition、removal test and target stage.
8. Card B may consume Card A projections but may not execute.
9. Card C may execute admitted specs but may not recompute research priority.

---

## 4. Dependency graph

```text
Card A — CLOSED
        │
        ├──────────────┐
        ↓              ↓
#13 B0             #14 C0
Matrix authority   Capacity/control precheck
        │              │
        ↓              │
B1 Combination Kernel  │
        ↓              │
B2 Candidate Projection┘
        │
        ├──────────────→ C1 Queue Reference Contract
        │                       ↓
        ↓                      C2 Claim / Lease / Idempotency
B3 Daily Research Policy        ↓
        │                      C3 Direct TrialSpec Runner
        ├───────────────────────┤
        ↓                       ↓
B4 Regime Finalist         C4 Shadow / Canary Cutover
        │                       │
        └──────────┬────────────┘
                   ↓
              D0 RegimePolicyBundle
                   ↓
              D1 Promotion / Expiry Gate

C5 Legacy Bridge Retirement
只能在 canonical path accepted、parity/rollback/removal receipts 完整後逐橋退場。
```

依賴圖表示 admission prerequisite，不代表後續卡已獲授權。

---

## 5. Backlog cards

| Card | Status | Depends on | Scope | Explicit non-goal |
|---|---|---|---|---|
| B0 Matrix Authority and Search Design | `READY_FOR_READ_ONLY_RESEARCH` | Card A | 證明股票矩陣維度、限制、精確組合數、E1–E4 成本、full-scan／adaptive 分界 | 不實作 generator、optimizer、queue |
| C0 Execution Capacity and Cutover Precheck | `READY_FOR_READ_ONLY_PRECHECK` | Card A；與 B0 協作 | runner/control map、capacity、intermediate reuse、claim/retry gaps、A6 bridge cutover plan | 不改 queue／runner，不刪 bridge |
| B1 Discrete Combination Kernel | `PLANNED / NOT_ADMITTED` | B0 accepted | 純函式 count／generate／rank／unrank／chunk／identity／neighbor／constraint validation | 不回測、不排序、不執行 |
| B2 Research Candidate Projection | `PLANNED / NOT_ADMITTED` | B1 accepted | Coverage＋Learning＋Failure＋budget → versioned `CandidateDecision` shadow projection | 不寫 canonical queue |
| B3 Daily Adaptive Research Policy | `PLANNED / NOT_ADMITTED` | B2 accepted | coverage/refinement/replication/challenge/rare-regime budget policy | 不直接 promotion，不接管 scheduler |
| B4 Regime Finalist Projection | `PLANNED / NOT_ADMITTED` | B3；需 C3 產生足夠 first-party cycles | 每盤況 primary、robust alternatives、unresolved risks、forward prerequisites | 不產 production config |
| C1 Canonical Queue Reference Contract | `PLANNED / NOT_ADMITTED` | C0 accepted＋B2 handoff pinned | queue only references `trial_spec_id`、decision/admission metadata | 不複製 spec truth |
| C2 Claim / Lease / Idempotency | `PLANNED / NOT_ADMITTED` | C1 accepted | race、duplicate、lease expiry、retry、orphan、revocation semantics | 不宣稱 exactly-once |
| C3 Direct TrialSpec Runner | `PLANNED / NOT_ADMITTED` | C2 accepted | runner directly consumes immutable canonical TrialSpec and emits first-party receipt | 不重算 priority、不改 backtest math |
| C4 Shadow / Canary Cutover | `PLANNED / NOT_ADMITTED` | C3＋B3 | old/new resolve parity、deterministic cohort、single-writer cutover、rollback | 不做 random rollout、不得雙重 side effect |
| C5 Legacy Bridge Retirement | `PLANNED / NOT_ADMITTED` | C4 accepted＋per-bridge removal evidence | 逐條移除 A6 指定的 legacy readers/writers/adapters | 不為了清零而刪 archival/recovery evidence |
| D0 RegimePolicyBundle | `PLANNED / NOT_ADMITTED` | B4＋C4 evidence | versioned regime bundle、primary、alternatives、fallback、evidence、validity | 不自動 promotion |
| D1 Promotion and Expiry Gate | `PLANNED / NOT_ADMITTED` | D0 accepted | development → validation → sealed OOS → forward shadow → review → approval／expiry | 不讓每日研究結果直接改 production |

---

## 6. B0 admission target

B0 必須完成 [Issue #13](https://github.com/bluemaple18-home/NEW-TOP10/issues/13) 的完整研究，至少交付：

```text
01-current-matrix-authority-map.md
02-stock-matrix-definition-and-exact-count.md
03-dimension-and-constraint-taxonomy.md
04-evaluation-separability-and-cost-audit.md
05-full-scan-vs-adaptive-search-decision.md
06-daily-research-and-refinement-policy.md
07-outcome-evidence-and-overfit-guards.md
08-prior-art-and-open-source-reuse-matrix.md
09-regime-policy-bundle-contract-draft.md
10-b1-admission-recommendation.md
```

B0 只可裁決：

```text
B1 = ADMIT_BOUNDED / RESEARCH_ONLY / BLOCK_SCOPE_EXPANSION / BLOCKED_BY_MEASURED_GAP
```

B0 不得自動 admission B2–B4、C1–C5 或 D0–D1。

### Current matrix facts to preserve until disproven by stronger authority

- 現行 canonical Parameter Catalog 只有四個已證明 executable dimensions：`horizon`、`stop_loss_pct`、`take_profit_pct`、`max_group_exposure`。
- 現行 formal executable legal count 是 `720`。
- `regime_gate`、`risk_guard`、`entry_filter` 仍是 contract-dependent／coverage-only。
- 股票完整「兩百萬級矩陣」尚未由 committed canonical dimension source 證明。
- 不得用 Trace 的 `15 strategies / 10 grids / 1,961,256 candidates` 填補股票未知欄位。

---

## 7. C0 admission target

C0 必須完成 [Issue #14](https://github.com/bluemaple18-home/NEW-TOP10/issues/14) 的完整 precheck，至少交付：

```text
01-current-execution-and-control-authority-map.md
02-runner-entry-and-direct-trialspec-gap-map.md
03-queue-reader-writer-claim-lease-inventory.md
04-capacity-and-intermediate-reuse-audit.md
05-idempotency-retry-orphan-and-dual-write-gaps.md
06-a6-bridge-to-cutover-map.md
07-shadow-canary-rollback-and-removal-plan.md
08-prior-art-and-open-source-reuse-matrix.md
09-c1-prerequisites-and-admission-blockers.md
```

C0 只能列出 C1 prerequisites／blockers。C1 必須等待：

1. C0 accepted；
2. B0 accepted；
3. B2 或等價卡已固定 `CandidateDecision → admission → Canonical TrialSpec` handoff；
4. current queue/control authority 無 material conflict；
5. direct-TrialSpec runner seam 與 terminal receipt boundary 可被證明；
6. no speculative broker/workflow/outbox dependency。

---

## 8. Trace absorption boundary

Trace 與 NEW-TOP10 可以共用的只有**通用離散組合核心**：

```text
legal constrained combination generation
exact counting
deterministic ordering
rank / unrank
chunking
batch / vectorized evaluation
no per-candidate I/O
audit and benchmark receipts
```

下列是 Trace 產品規則，明確禁止偷渡到股票專案：

```text
15% mandatory equal floor
85% adjustable budget pool
CPC 60 / CPM 40 scoring
2,000,000 per-order cap
15 strategies / 10 grids
1,961,256 as stock-matrix count
fully-feasible Trace definition
Trace tie-break
winner immediate write-back
order lock / rounding / budget settlement semantics
```

若股票矩陣日後證明存在 constrained allocation dimension，才可研究 sum/floor/ceiling 與 pairwise weight-transfer neighbor；不得因結構相似就先假設存在。

---

## 9. Research outcome semantics

三條軸必須永遠分開：

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

## 10. Prior-art map

### B0 primary donors

- SciPy QMC／Sobol／LatinHypercube — space-filling seed design。
- Optuna Ask-and-Tell — suggestion／external execution separation。
- OSS Vizier — suggestion/completion and algorithm benchmark contracts。
- Ray Tune — SearchAlgorithm／Scheduler responsibility split。
- SMAC3、DEHB — racing、intensification、multi-fidelity concepts。
- Ax、BoTorch — constrained multi-objective／Pareto concepts; defer runtime adoption until corpus justifies it。
- Open Bandit Pipeline — off-policy admissibility contract only；沒有 propensity evidence 不得聲稱 OPE。
- Deflated Sharpe Ratio、Probability of Backtest Overfitting — multiple-testing／selection-bias guard。
- OMI — supplemental evidence/freshness/lineage semantics only。

### C0 primary donors

- Branch by Abstraction、Strangler Fig — incremental seam and bridge retirement。
- Google SRE Canary — bounded comparison, abort and rollback evidence。
- OpenFeature spec／Python SDK／flagd — deterministic cohort and evaluation-reason pattern only。
- Temporal Worker Versioning — ramp／drain／rollback failure cases; no Temporal authority adoption。
- DBOS Transact Python — idempotency／crash-recovery tests; dependency remains conditional。
- Debezium Outbox — only for measured DB＋broker atomicity gap。
- PostgreSQL `SKIP LOCKED` — queue-like claim pattern with explicit limitations。
- Taskiq／Celery — transport references only, not default control-plane answer。

每一個 donor 都必須固定：

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

## 11. Cross-lane evidence contract

B0、C0 的每個 material claim 至少記錄：

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

個別證據缺失時：

```text
UNKNOWN
UNPINNED_RUNTIME_ARTIFACT
UNPINNED_CROSS_PROJECT_DONOR
UNMEASURED_CAPACITY
```

標記後繼續其他盤點。

只有以下情況才整卡停止：

- committed governing authorities materially conflict；
- canonical identity grain 無法確定；
- terminal receipt boundary 無法確定；
- exact matrix count 必須靠捏造維度／限制才能得到；
- 必須修改 runtime 才能回答研究問題；
- 研究會觸碰 production、scheduler/publish 或不當使用 sealed evidence。

每條 lane 只寫自己的非重疊 evidence；Integrator 是唯一 cross-lane synthesis writer。

---

## 12. Monitoring and admission rule

節省監工模式：

- B0／C0 可平行，不在每個小發現重審。
- 每張卡只在 authority、scope、source pin、acceptance、重大 conflict 與 final verdict 檢查。
- 卡片研究完成不等於下一張自動 admission。
- B 不得因「最優化」需求取得 execution authority。
- C 不得因「可靠執行」需求取得 decision authority。
- D 不得因歷史高分跳過 sealed OOS、forward shadow、review、expiry 與 fallback。
- 新 runtime、store、queue、optimizer、broker 或 workflow engine 必須另有 measured gap 與獨立 admission。

目前施工指令：

```text
CARD A: CLOSED / ACCEPTED

PARALLEL RESEARCH FRONTIERS:
- #13 B0: READY_FOR_READ_ONLY_RESEARCH
- #14 C0: READY_FOR_READ_ONLY_PRECHECK

NOT ADMITTED:
- B1 / B2 / B3 / B4
- C1 / C2 / C3 / C4 / C5
- D0 / D1

PRODUCTION / RANKING / MODEL / BACKTEST MATH / SCHEDULER / PUBLISH:
- NO CHANGE AUTHORIZED
```

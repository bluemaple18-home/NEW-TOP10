# C0 Phase 2 Capacity and Cutover Design Worker 派工卡

工作名稱：C0 Phase 2 容量量測與 Control Cutover 證據

任務簡介：依 BC-CP1 `ADMIT_C0_PHASE_2`，以已接受的 B0 matrix-size／E1–E4 facts，完成 capacity、execution-control gaps 與 cutover/removal 設計證據；不得實作 C1 或修改 runtime。

來源：NEW-TOP10 canonical main `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`；B0 Phase 1 fixed SHA `d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98`；C0 Phase 1 fixed SHA `c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba`；AI Core dispatch baseline `21801303adff285268f7646df94dc53da31a835f`；Issue #14；`docs/RESEARCH_SPINE_BACKLOG.md`。

執行規範：你是 GPT-5.5 high strict/core-bounded Evidence Worker，不是 Mainline／Integrator。只做 read-only research 與隔離、bounded、temporary benchmark；不得修改 code、config、schema、database、queue、runner、scheduler、workflow、model、backtest math、ranking、publish、production 或 A6 bridges。不得 production invocation、external write、dual-write、canary、cutover、bridge removal、merge、push、Issue write，亦不得准入 C1／B1。不得自行切換或降低模型／推理設定。

固定輸入：容量 denominator 為 `720`；current evaluator=`E3`；`E2=NOT_PROVEN`；`E4=REQUIRED_BUT_UNCHARACTERIZED`；context axes 不乘入 720；canonical 720-spec generation／dedupe／identity／partition path 未證明。若無法建立有 authority 的 bounded representative sample，只能交 missing-authority receipt，不得把 convenience sample 宣稱為 representative 或推估完整 daily capacity。

交付：只交 Phase 2 六份 evidence：

```text
05-capacity-and-intermediate-reuse-audit.md
06-idempotency-retry-orphan-and-dual-write-gaps.md
07-a6-bridge-to-cutover-map.md
08-shadow-canary-rollback-and-removal-plan.md
09-prior-art-and-open-source-reuse-matrix.md
10-c1-prerequisites-and-admission-blockers.md
```

驗收：material claims 必須固定 source SHA／range 與 claim schema。容量證據須記錄 immutable inputs、sample authority、sample size、wall time、candidate/sec、CPU、peak RSS、I/O、cache/intermediate reuse、temporary output boundary與可重跑命令；不可將 verifier pass 當 benchmark。明確區分 measured fact、projection 與 unknown；證明 direct TrialSpec seam、per-item claim／lease／retry、orphan reconciliation、dual-write necessity、bridge live-activity與 removal gate 的現況或缺口。Donor 只做最小 sufficient comparison，記錄 version／license／adopt-adapt-reject 與 `why_not_less / why_not_more / do_not_absorb`。

停止條件：若需要 runtime mutation、production state、未授權外部 write、捏造 sample identity、跨越 sealed evidence，或發現 authority conflict，立即停止並回報證據。完成後只回 candidate SHA、changed files、verification、remaining unknowns 與 C1 blocker recommendation；需獨立 reviewer GO，且不得自行宣告 C1 admission。

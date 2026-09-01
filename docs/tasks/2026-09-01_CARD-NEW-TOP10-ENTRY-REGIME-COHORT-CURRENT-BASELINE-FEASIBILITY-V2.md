---
id: CARD-NEW-TOP10-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY-V2
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: CONTRACT_DRAFT / NOT_ADMITTED
type: feasibility-contract
risk: high
model: gpt-5.5
reasoning: high
cycle: BC-CP2-R10
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
---

# Entry-Regime Cohort Current-Baseline Feasibility V2

## Objective

建立 current-baseline 的 Entry-Regime Cohort h20 feasibility 契約草案，讓後續 Owner／Mainline 若明示 admission，可在 outcome-free 邊界內檢查 cohort capacity、split authority 與 ranking provenance authority。

本卡只修補契約，不准入 feasibility worker、不執行 replay、不計算 outcome、不修改 production。

## Authority

本 V2 草案的 authority 固定如下：

| Authority | Path / SHA |
| --- | --- |
| R10 fixed parent | commit `e9f2c93761d385bbe6c2e6e26a7d45e608189c65` |
| R10 control card | `docs/tasks/2026-09-01_REPAIR-NEW-TOP10-BC-CP2-R10-ENTRY-REGIME-COHORT-CURRENT-BASELINE-CONTRACT.md`; sha256 `5e856dcc50cdbdf6a7569c8f301505e54dc5a9cea98b59311a02c169cdfde53a` |
| R9 current-baseline reconciliation | commit `ba2c5310ae4a8e89ec81e8ec347433123dbcbb49`; evidence sha256 `37b2e0a92fbca1464c5293ca7f76408a0dae3108f39deecd38a9a110f585e2a6` |
| R8 exact-holding successor decision | commit `27327b670142e22c4c4cdd5bda7cae03ac2eb1e4`; task sha256 `69fca1c1cfc311f7111f7cba3cb3c455587696d9711c7783172ccf41e20e84bb` |
| R7 identity/episode authority | commit `e1a30830d0ab2ee24af0f81d703cbf350be4819e`; evidence sha256 `d2ecacfe8e762fa939704649f6461bb4be4db39ddb935a01cdd5969083219574` |
| R6 configured ranking source authority | commit `b7ba1fc6065d6221353f7362db92ac7638bb8017`; evidence sha256 `d4492b7711ee8a532a5a1b1b9e232dd285b030c22d7931cc2b13f0f52788bf98` |
| Canonical backlog | `docs/RESEARCH_SPINE_BACKLOG.md`; sha256 `5065a341c3a050c78a6d94a341c8f47664dec36c201a2c2943489b8c8d5d5dc8` |
| Entry-Regime architecture prior art | `docs/tasks/2026-08-16_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-ARCHITECTURE-DECISION-V1.md`; sha256 `3b46c863ed23e638569deb6a0ca54f89a69d2f199e2503292db8647b16a90d4a` |
| Entry-Regime architecture evidence | `docs/evidence/CARD-NEW-TOP10-ENTRY-REGIME-COHORT-ARCHITECTURE-DECISION-V1/decision.json`; sha256 `6bda001a0d5a9dae37f62acb4620e9e194077ad099d7541870a8d93916609db0` |
| Entry-Regime architecture doc | `docs/architecture/entry_regime_cohort_replay_v1.md`; sha256 `e998a2fceb726d2e86f23ad6b5a82b574cdd3fca486a579f9deff6d9603ab5c2` |
| Entry-Regime feasibility prior art | `docs/tasks/2026-08-16_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1.md`; sha256 `0a37b7b35e346d2eac301df4fd8f380cb65cc6a987d32a94e2306763bf03df6e` |
| Entry-Regime feasibility prior-art JSON | `docs/evidence/CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1/feasibility.json`; sha256 `68f540b2e87ceb8422fe083a7c0e01abd9f6db4899029c2d04f2539a6835bea6` |
| Forward ranking provenance contract | `docs/tasks/2026-08-16_CARD-NEW-TOP10-FORWARD-RANKING-PROVENANCE-RECEIPT-V1.md`; sha256 `c8025c4d184d05ba010a72a8917fd6ed123e8ef24c225f5c501b123199789979` |

Current configured input refs 由 R6／R7／R9 committed evidence 固定；若未來 admission 後無法在 execution worktree 重新驗證同一 bytes，必須 fail closed：

| Input | Current configured sha256 |
| --- | --- |
| `artifacts/market_regime_history_2026-05-29.json` | `4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70` |
| `data/clean/features.parquet` | `93e8432987b6037db243b2864f7bc8d09f12acd50249d9238d2acddacd2561d2` |
| `data/clean/universe.parquet` | `ba9c69dc5270bf53968e39a51c93e6e80421d7545c83b29df5a95a693aede85a` |
| `models/latest_lgbm.pkl` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` |
| `config/signals.yaml` | `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a` |

## Scope

- 研究語義固定為 Entry-Regime Cohort：ranking date `D` 的 as-of exact identity 決定 cohort；holding window 可跨 regime，但 future regime path 只能作 availability／描述性診斷。
- Horizon 固定 `h20`；entry 固定 `D+1`；不得縮短 horizon、改 entry timing、改 taxonomy、改 split、改 episode construction 或合併 exact identities 來補 capacity。
- Selection eligibility、outcome attribution、transition diagnostics、promotion gate 必須分離。
- Split 固定單一全域 chronological allocation；development／validation 與 validation／sealed 兩個邊界都必須做 outcome-interval purge，且 embargo 至少 `20` 個 market trade days。
- 統計 grain 固定為 `ranking_date × scenario × top-N portfolio`；holding interval 相交者必須合併為 overlap component；raw date 數或個股數不得冒充 independent sample size。
- 本草案只允許作未來 feasibility admission 的契約輸入；不提供 implementation、runner、queue、workflow、promotion 或 production authority。

## Constraints

- 本卡狀態固定 `CONTRACT_DRAFT / NOT_ADMITTED`；任何後續 feasibility、R11、B0 Phase 2、B1、C0 Phase 2、C1、preregistration、promotion 或 production 都需要 Owner／Mainline 另行明示 admission。
- 必須明確 supersede 2026-08-16 feasibility prior-art JSON 的 stale runtime hashes、`split.authoritative=false` 與 blocked capacity output；舊 JSON 只能作 prior art，不得作 current-baseline feasibility result。
- 舊 Entry-Regime architecture 的 h20、D+1、ranking-date as-of identity、future path diagnostic-only、outcome-free、global chronological split、雙邊界 purge／embargo、overlap component grain 與 research-only invariant 可被保留；舊 `status: ready` 不得自動延伸為 current admission。
- Ranking corpus 若缺 model、config、universe、top-N、per-ranking receipt 或 contemporaneous provenance authority，唯一允許結果是 `BLOCKED_RANKING_PROVENANCE_AUTHORITY`。
- 不得用舊 manifest、R6 fog root、historical rebuild、`REPLAY_GENERATED`、filename existence 或 coverage completeness 補 ranking provenance 洞。
- 不得讀取、輸出或衍生 return、PnL、win rate、Sharpe、alpha、promotion score、target、sealed outcome 或任何 outcome metric。
- 若 current configured authority 與 R6／R7／R8／R9 refs 無法一致固定，唯一允許結果是 `BLOCKED_CURRENT_AUTHORITY_CONFLICT`；不得自行改研究語義。

## Acceptance

本 V2 草案達成 admission-review ready 的條件：

- Objective、authority、scope、constraints、acceptance、verification、status、handoff 與 evidence refs 完整且互相一致。
- 狀態維持 `CONTRACT_DRAFT / NOT_ADMITTED`，未准入任何 feasibility execution 或後續 phase。
- R6、R7、R8、R9、canonical backlog、current configured input refs 與 ranking provenance boundary 均被固定。
- 舊 feasibility prior art 的可相容 invariant 與不可沿用 authority 被明確分離。
- Ranking provenance 缺口被寫成 fail-closed precondition，而不是 future worker 可自由補洞的空白。

未來若本卡被 Owner／Mainline 另行准入，feasibility worker 的結果只允許下列其中之一：

- `FEASIBLE_FOR_PREREGISTRATION`
- `NO_GO_INSUFFICIENT_ENTRY_COHORT_CAPACITY`
- `BLOCKED_RANKING_PROVENANCE_AUTHORITY`
- `BLOCKED_CURRENT_AUTHORITY_CONFLICT`

## Verification

R10 本次驗證固定如下：

- Preflight `HEAD` 必須等於 `e9f2c93761d385bbe6c2e6e26a7d45e608189c65`。
- Changed-file allowlist 只能是 `docs/tasks/2026-09-01_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY-V2.md`。
- `git diff --check` 必須通過。
- Commit 後 worktree 必須 clean。
- Source decision：CodeGraph 在本 worktree 未初始化；本卡只依限域任務卡、committed evidence 與 fixed hashes 對帳，不宣稱 runtime replay evidence。
- Execution guard：不得執行 feasibility、replay、benchmark、訓練、outcome、sealed access、merge、push、Issue write、deploy 或 external write。

## Status

- 本卡結果：`CONTRACT_DRAFT_READY_FOR_OWNER_ADMISSION`
- 本卡狀態：`CONTRACT_DRAFT / NOT_ADMITTED`
- Current feasibility：`NOT_RUN`
- R11／Phase 2／B1／C1：`NOT_ADMITTED`
- Production：`NO_CHANGE`

## Handoff

唯一 frontier：`OWNER_ADMISSION_REVIEW_FOR_R11_ENTRY_REGIME_COHORT_CURRENT_BASELINE_FEASIBILITY`

若 Owner／Mainline 後續明示 admission，下一張卡只能以本 V2 草案作 contract input，先驗 current authority 與 ranking provenance precondition；若 provenance 仍缺，必須停在 `BLOCKED_RANKING_PROVENANCE_AUTHORITY`，不得進入 replay、outcome 或 preregistration。

## Evidence Refs

- R6：`docs/evidence/BC-CP2-R6-CONFIGURED-RANKING-SOURCE-AUTHORITY/01-existing-source-authority-decision.md`
- R7：`docs/evidence/BC-CP2-R7-HORIZON-SAFE-IDENTITY-EPISODE-AUTHORITY/01-identity-episode-authority-decision.md`
- R8：`docs/tasks/2026-09-01_DECISION-NEW-TOP10-BC-CP2-R8-EXACT-HOLDING-SUCCESSOR.md`
- R9：`docs/evidence/BC-CP2-R9-ENTRY-REGIME-COHORT-FEASIBILITY-RECONCILIATION/01-current-baseline-reconciliation.md`
- Backlog：`docs/RESEARCH_SPINE_BACKLOG.md`
- Prior-art architecture：`docs/architecture/entry_regime_cohort_replay_v1.md`
- Prior-art feasibility：`docs/evidence/CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1/feasibility.json`

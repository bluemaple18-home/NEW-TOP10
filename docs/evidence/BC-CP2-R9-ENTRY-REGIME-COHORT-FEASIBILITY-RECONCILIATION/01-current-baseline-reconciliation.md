# BC-CP2 R9 Entry-Regime Cohort 可行性對帳

## Receipt

- 任務：`BC-CP2-R9-ENTRY-REGIME-COHORT-FEASIBILITY-RECONCILIATION`
- 固定 parent：`bce29ae0460eadac36d04c1a7be4f0eb41bb1081`
- 任務卡：`docs/tasks/2026-09-01_RESEARCH-NEW-TOP10-BC-CP2-R9-ENTRY-REGIME-COHORT-FEASIBILITY-RECONCILIATION.md`
- 任務卡 sha256：`a4b2d2fb152a0a8c278eed88736b7cab70e433f9bf20a92311895c95239ecc62`
- Verdict：`PARTIAL_CONTRACT_REPAIR_REQUIRED`
- 裁決範圍：只裁決新版 current-baseline Entry-Regime Cohort feasibility card 是否可另行准入；不直接實作、不 replay、不讀 outcome。
- 產出限制：只新增本檔；未修改 code、tests、config、data、history、features、ranking、taxonomy、split、episode、horizon、workflow、runner、queue、scheduler、backtest、production或既有 evidence。

## Verification Receipt

- `HEAD` preflight：`bce29ae0460eadac36d04c1a7be4f0eb41bb1081`，符合 fixed parent。
- Worktree preflight：開始寫 evidence 前為 clean；任務卡是 fixed parent 內已追蹤檔，不是未追蹤副本，因此未移除。
- CodeGraph：本 worktree 未初始化，source decision 降級為限域文件與 committed evidence 對帳。
- Changed-file allowlist：只允許 `docs/evidence/BC-CP2-R9-ENTRY-REGIME-COHORT-FEASIBILITY-RECONCILIATION/01-current-baseline-reconciliation.md`。
- Execution guard：未執行 replay、benchmark、訓練、outcome 計算、merge、push、Issue write、deploy、external write。

## Authority Refs

| Authority | Path / SHA |
| --- | --- |
| R6 source authority | commit `b7ba1fc6065d6221353f7362db92ac7638bb8017`; evidence sha256 `d4492b7711ee8a532a5a1b1b9e232dd285b030c22d7931cc2b13f0f52788bf98` |
| R7 identity/episode authority | commit `e1a30830d0ab2ee24af0f81d703cbf350be4819e`; evidence sha256 `d2ecacfe8e762fa939704649f6461bb4be4db39ddb935a01cdd5969083219574` |
| R8 successor decision | commit `27327b670142e22c4c4cdd5bda7cae03ac2eb1e4`; task sha256 `69fca1c1cfc311f7111f7cba3cb3c455587696d9711c7783172ccf41e20e84bb` |
| Canonical backlog | `docs/RESEARCH_SPINE_BACKLOG.md`; sha256 `5065a341c3a050c78a6d94a341c8f47664dec36c201a2c2943489b8c8d5d5dc8` |
| Entry-Regime architecture prior-art task | `docs/tasks/2026-08-16_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-ARCHITECTURE-DECISION-V1.md`; sha256 `3b46c863ed23e638569deb6a0ca54f89a69d2f199e2503292db8647b16a90d4a` |
| Entry-Regime architecture decision JSON | `docs/evidence/CARD-NEW-TOP10-ENTRY-REGIME-COHORT-ARCHITECTURE-DECISION-V1/decision.json`; sha256 `6bda001a0d5a9dae37f62acb4620e9e194077ad099d7541870a8d93916609db0` |
| Entry-Regime architecture doc | `docs/architecture/entry_regime_cohort_replay_v1.md`; sha256 `e998a2fceb726d2e86f23ad6b5a82b574cdd3fca486a579f9deff6d9603ab5c2` |
| Entry-Regime feasibility prior-art task | `docs/tasks/2026-08-16_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1.md`; sha256 `0a37b7b35e346d2eac301df4fd8f380cb65cc6a987d32a94e2306763bf03df6e` |
| Entry-Regime feasibility prior-art JSON | `docs/evidence/CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1/feasibility.json`; sha256 `68f540b2e87ceb8422fe083a7c0e01abd9f6db4899029c2d04f2539a6835bea6` |
| Forward ranking provenance contract | `docs/tasks/2026-08-16_CARD-NEW-TOP10-FORWARD-RANKING-PROVENANCE-RECEIPT-V1.md`; sha256 `c8025c4d184d05ba010a72a8917fd6ed123e8ef24c225f5c501b123199789979` |

## Current Baseline Facts

- R6 verdict：`PARTIAL_EXISTING_SOURCE_AUTHORITY_GAP`。目前 configured ranking root `artifacts/backtest/historical_rankings_current_model` 對 R5 required dates 是 `0/9`；fog root 只保留為 ranking-date/file lineage candidate，不是 current configured feature-compatible 或 research-replay authority。
- R7 verdict：`NO_GO_IDENTITY_EPISODE_AUTHORITY_MISSING`。28 個 taxonomy exact identities 全量 census；16 個有 rows，2 個 split-OK，0 個具 h3/h5/h10/h20 全 horizon-safe development dates。
- R8 decision：`KEEP_CONFIGURED_EXACT_HOLDING_PATH_CLOSED`、`DO_NOT_RELAX_TAXONOMY_SPLIT_EPISODE_OR_HORIZON`、`ENTRY_REGIME_COHORT_IS_SEPARATE_SUCCESSOR_CANDIDATE`、`SUCCESSOR_NOT_ADMITTED`。
- Backlog current boundary：B0 Phase 2、C0 Phase 2、B1、C1、D0/D1 均 `NOT_ADMITTED`；卡片研究完成不等於下一張自動 admission。

## Compatible Claims

| Claim | Status | Basis |
| --- | --- | --- |
| Entry-time attribution is semantically separate from exact-holding regime evidence | Compatible | Architecture prior art fixes entry cohort at ranking date and forbids claiming entire-holding exact-regime causal evidence. R8 also separates Entry-Regime Cohort as successor candidate after exact-holding path closure. |
| h20 and D+1 remain fixed | Compatible | Architecture decision fixes `horizon_trade_bars=20` and `entry_delay_trade_days=1`; R8 rejects shortening horizon as repair. |
| Entry identity must be as-of ranking date | Compatible | Architecture decision requires `trade_date == as_of_date == D` and rejects latest-row fallback, UNKNOWN and transition rows. |
| Future regime path is diagnostic only | Compatible | Architecture decision sets `future_path_is_descriptive_only=true` and forbids future path from changing selection, eligibility, weighting, parameters or stopping conditions. |
| Old episode split cannot be reused | Compatible | Architecture decision sets `old_episode_split_reuse_allowed=false`; R8 forbids relaxing split/episode authority. |
| Successor should remain outcome-free before preregistration | Compatible | Prior-art feasibility task and architecture both prohibit returns/PnL/win rate/Sharpe/alpha/promotion score and sealed outcome access. |

## Superseded Claims

| Claim | Superseded by | Decision |
| --- | --- | --- |
| Prior-art card status `ready` means current admission | R8 `SUCCESSOR_NOT_ADMITTED` and backlog admission boundary | Superseded; cannot use old `ready` as present authority. |
| 2026-08-16 feasibility audit can be reused as current-baseline feasibility | R6/R7/R8 current authorities | Superseded; old feasibility JSON used old runtime hashes and ended `BLOCKED_EVIDENCE_OR_CONTRACT_CONFLICT`. |
| Old exact-regime closure counts are enough for current decision | R7 `28 / 16 / 2 / 0` census | Superseded for current exact identity/episode authority. |
| Old global split allocation is authoritative | Old feasibility JSON `split.authoritative=false` | Superseded; any new card must rebuild current-baseline split authority outcome-free. |
| Baseline/candidate ranking roots in old feasibility have complete provenance | Old feasibility reason codes and forward provenance contract | Superseded; provenance was explicitly incomplete. |

## Unproven Claims

| Claim | Current evidence gap |
| --- | --- |
| A new current-baseline Entry-Regime feasibility card can immediately produce a valid feasibility verdict | Not yet proven; it first needs a repaired contract binding current authority refs and fail-closed provenance rules. |
| Current configured ranking corpus has model/config/universe/top-N provenance sufficient for Entry-Regime feasibility | Unproven. Old feasibility reported `RANKING_MODEL_CONFIG_UNBOUND_IN_COMMITTED_MANIFEST`, `RANKING_UNIVERSE_UNBOUND_IN_COMMITTED_MANIFEST`, `RANKING_TOP_N_UNBOUND_IN_COMMITTED_MANIFEST`; R6 did not repair this. |
| Current-baseline calendar/regime inputs match old feasibility inputs | False as reusable authority. Old feasibility used `data/clean/features.parquet` sha256 `6dfeed9a54ff5513c516e4aa1e0a6258bd7a8e1f7c61036459d72da96b64d7c9` and `artifacts/market_regime_history.json` sha256 `96372f3e7fcfc8416d123496c4d2d3f32218b75d22e80fce70e394640b3527cd`; current BC-CP2 refs use features sha256 `93e8432987b6037db243b2864f7bc8d09f12acd50249d9238d2acddacd2561d2` and configured history `artifacts/market_regime_history_2026-05-29.json` sha256 `4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70`. |
| At least one entry cohort has development/validation/sealed independent component count >= `n_min` | Unproven under current baseline. Old feasibility measured only old prior-art state and reported overlap component count `1`, family `M=10`, `n_min=20`, status blocked. |
| Ranking source binding can be handled after feasibility starts | Unproven and risky. R6 says source binding remains a separate authority gap; forward provenance forbids retroactively granting old rankings contemporaneous provenance. |

## Ranking Provenance Boundary

Ranking provenance is a material current-baseline blocker, not a cosmetic documentation gap:

- Forward provenance requires each new `ranking_YYYY-MM-DD.csv` to bind scenario/date/run identity, artifact path/hash, producer source, model, config, universe, feature/calendar source, top-N and sort/tie-break policy.
- `REPLAY_GENERATED` is fixed `admission_eligible=false`; historical range rebuild cannot解除 provenance blocker by completeness alone.
- New receipts cannot claim old rankings had contemporaneous provenance.
- Old Entry-Regime feasibility already ended blocked because ranking model/config, universe and top-N were unbound in committed manifest.
- R6 confirmed fog root is not current configured feature-compatible authority and configured root remains coverage/provenance-limited.

Therefore a new current-baseline feasibility card cannot simply reuse old feasibility outputs or old ranking manifests. It must first repair the card contract to make incomplete ranking provenance a fail-closed input, not an implicit pass.

## Decision

`PARTIAL_CONTRACT_REPAIR_REQUIRED`

Rationale：

1. There is no successor authority conflict at the architecture level: Entry-Regime Cohort remains compatible as a separate successor candidate because it preserves h20, D+1, as-of entry identity, outcome-free feasibility, transition diagnostics and non-production boundaries.
2. There is a material contract gap before admission: current R6/R7/R8/backlog and ranking provenance boundaries supersede the old feasibility card. The old card was `ready` historically, but not current-baseline admissible as written.
3. Direct `GO_FOR_NEW_CURRENT_BASELINE_FEASIBILITY_CARD` would incorrectly skip contract repair around current authority refs, ranking provenance fail-closed behavior, and backlog admission boundaries.
4. `NO_GO_SUCCESSOR_AUTHORITY_CONFLICT` is too strong: R8 explicitly preserves Entry-Regime Cohort as a separate successor candidate, so the architecture idea is not rejected.

## Absorption Boundary

Why not less：

- R9 must compare prior art against R6/R7/R8/backlog/provenance together; reading only old Entry-Regime cards would falsely preserve stale `ready`/feasibility claims.
- Ranking provenance must be explicit because old feasibility already failed on unbound model/config/universe/top-N, and R6 did not repair that gap.
- R7 must be considered because it proves exact-holding is closed, which is why Entry-Regime Cohort can only be a successor semantic contract, not a repair of the original path.

Why not more：

- R9 is not the new feasibility audit and must not calculate cohort capacity under current baseline.
- R9 is not contract implementation; it must not edit architecture, code, tests, ranking manifests, taxonomy, split or runner.
- R9 must not admit Phase 2, B1, C1, replay, preregistration, promotion or production.

Do not absorb：

- 不吸收 outcome、return、PnL、win rate、Sharpe、alpha、target、sealed outcome 或 benchmark/replay。
- 不吸收 fog source binding、ranking backfill、ranking provenance implementation、`FORWARD_CAPTURE` 或 admission registration。
- 不吸收 taxonomy/split/episode/horizon 變更，亦不吸收 exact-holding repair。
- 不吸收 old feasibility JSON 的 split/capacity numbers 作 current authority。

## Unique Frontier

唯一最小下一卡：`R10-ENTRY-REGIME-COHORT-CURRENT-BASELINE-CONTRACT-REPAIR`

R10 只應產出新版 current-baseline feasibility card/spec 的契約修補，不跑 feasibility/replay/outcome：

- 固定 current authority refs：R6、R7、R8、canonical backlog、configured history/features hashes、ranking provenance contract。
- 將 old Entry-Regime architecture 中 compatible invariants 帶入新版 card：h20、D+1、ranking-date as-of identity、future path diagnostic only、global chronological split、雙邊界 purge/embargo、overlap component grain、research-only。
- 明確 supersede 舊 feasibility JSON 的 stale runtime hashes、non-authoritative split與 blocked capacity output。
- 將 ranking provenance 設為 fail-closed precondition：若 current baseline ranking corpus仍缺 model/config/universe/top-N/per-ranking receipt authority，feasibility worker只能回 `BLOCKED_RANKING_PROVENANCE_AUTHORITY`，不得用舊 manifest補洞。
- 明確不准入 implementation、replay、preregistration、Phase 2、B1、C1 或 production。

# AUTO-TRAINING-BATCH-01 Mass Candidate Training and Evaluation

## 目標

進入大量訓練 / 批次評估模式，系統性測候選特徵、候選規則、盤勢上下文與 ranking/portfolio overlay，最後只回報 surviving candidates。

本卡取代後續一張一張小卡的節奏。除非要碰 production、正式模型、正式 ranking、正式推播，否則不中途找 PM 決策。

## 背景

目前已收斂：

- `BIG_BULL family_only`：只能 `RESTRICTED_SHADOW_ONLY` / monitor，不進 overlay proposal。
- `BIG_BULL` model promotion：blocked。
- `HIGH_CHOPPY rolling context`：可做 soft feature / stratified evaluation，但目前不作 promotion evidence。
- `models/latest_lgbm.pkl`：不得覆蓋。
- `promotion_ready`：必須維持 false，直到另有正式 promotion review。

因此下一步不是繼續鑽單一候選，而是批次掃描更多候選，找出真正穩定的方向。

## 固定基準

- production model：目前 `models/latest_lgbm.pkl`。
- production ranking：目前正式 ranking 流程輸出的 Top10。
- baseline artifacts：現有 replay / portfolio / daily ranking artifacts。
- all candidates 必須與 baseline 比較，不得只看自身絕對報酬。

## 候選池

### Model / Feature Candidates

- global model variants。
- feature group ablation：
  - technical trend。
  - volume / price action。
  - volatility / risk。
  - sector / industry context。
  - candidate persistence。
  - market regime context。
  - HIGH_CHOPPY rolling context as soft feature。
- feature group add-back：
  - 一次只加入已可追溯 feature group。
  - 不得用不可重現欄位。

### Ranking / Overlay Candidates

- production ranking rerank。
- sector concentration cap。
- turnover cap。
- candidate persistence rerank。
- portfolio risk overlay。
- regime-aware risk overlay。
- HIGH_CHOPPY restricted risk overlay candidate。

### Regime Stratification

- base regime 固定，不新增正式 label。
- family tag 固定：
  - `BIG_BULL`
  - `HIGH_CHOPPY`
- regime 只用於：
  - soft feature。
  - stratified evaluation。
  - restricted overlay。
  - diagnostics。
- regime 不可直接繞過 sealed / replay / rollback / promotion gate。

## 評估矩陣

每個候選都要盡量跑同一套比較：

- sealed / walk-forward。
- no-hindsight replay。
- Top5 / Top10 / Top15 sensitivity。
- D+1 / D+2 / D+3 entry-day sensitivity。
- 1D / 3D / 5D / 10D holding outcome。
- portfolio replay。
- max drawdown。
- hit rate。
- turnover。
- sector concentration。
- overlap vs production ranking。
- BIG_BULL stratified result。
- HIGH_CHOPPY stratified result。

資料未成熟時必須標 `PENDING_OUTCOME`，不得當成功或失敗證據。

## 自動淘汰規則

直接淘汰：

- replay / portfolio 明顯輸 baseline。
- 只在單一漂亮視窗有效。
- D+1 有效但 D+2 / D+3 崩壞且無法解釋。
- turnover 過高。
- sector concentration 過高且無 cap。
- HIGH_CHOPPY 分層明顯惡化。
- 無法追溯 feature lineage。
- 任何 guard 無法驗證。

降級 monitor：

- 有部分訊號，但樣本不足。
- soft feature 對整體沒幫助，但分層診斷有用。
- ranking 有效但與 production overlap 太低，尚不適合 overlay。

保留下一階段：

- 跨 window 穩定勝 baseline。
- drawdown 沒惡化。
- turnover 可控。
- sector concentration 可控。
- regime 分層沒有明顯破洞。
- ledger lineage 完整。

## 輸出狀態

候選只能輸出以下狀態之一：

- `SURVIVED_FOR_REPLAY_EXTENSION`
- `SURVIVED_FOR_SHADOW_DRY_RUN`
- `SURVIVED_FOR_OVERLAY_REVIEW`
- `MODEL_CANDIDATE_NEEDS_MORE_EVIDENCE`
- `RESTRICTED_SHADOW_ONLY`
- `MONITOR_ONLY`
- `REJECTED`
- `BLOCKED_CONTRACT`
- `BLOCKED_MODEL_EVIDENCE`

不得輸出 `PROMOTION_READY`。

## Guardrails

- 不覆蓋 `models/latest_lgbm.pkl`。
- 不改 production ranking artifact。
- 不改 production `risk_adjusted_score`。
- 不正式推播。
- 不產生正式 Clawd message。
- 不啟用 auto / scheduled retrain promotion。
- 不新增正式 base regime 或 family tag。
- 不用結果倒推切分或定義。
- 不用 metadata 修正掩蓋模型證據不足。

## Artifact 規格

批次結果集中輸出到：

```text
artifacts/model_experiments/mass_candidate_training_batch_YYYY-MM-DD.json
artifacts/model_experiments/mass_candidate_training_batch_YYYY-MM-DD.md
```

每個候選至少要包含：

- candidate_id。
- candidate_type。
- hypothesis。
- input_artifacts。
- feature_groups。
- regime_usage。
- baseline_comparison。
- replay_summary。
- portfolio_summary。
- stratified_summary。
- guard_status。
- decision。
- rejection_or_survival_reason。
- next_allowed_step。

## 驗收標準

- 批次 artifact 存在。
- 每個候選都有明確 decision。
- surviving candidates 數量可控，不能全部都保留。
- rejected / monitor candidates 有理由，不只是分數低。
- `models/latest_lgbm.pkl` hash unchanged。
- `promotion_ready=false`。
- `git diff --check` OK。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900
git diff --check
```

## 最終回報格式

```text
batch_status:
candidates_tested:
survived:
monitor_only:
rejected:
blocked:
top_surviving_candidates:
best_next_step:
models_latest_changed:
production_ranking_changed:
risk_adjusted_score_changed:
promotion_ready:
errors:
```

## 執行結果

產出：

- `artifacts/model_experiments/mass_candidate_training_batch_2026-06-01.json`
- `artifacts/model_experiments/mass_candidate_training_batch_2026-06-01.md`
- `scripts/build_mass_candidate_training_batch.py`

批次結果：

```text
batch_status: OK
candidates_tested: 13
survived: 2
monitor_only: 6
rejected: 2
blocked: 3
top_surviving_candidates:
  - feature_group_ablation_by_regime
  - sector_industry_context
best_next_step: run replay extension for feature_group_ablation_by_regime and sector_industry_context only
models_latest_changed: false
production_ranking_changed: false
risk_adjusted_score_changed: false
promotion_ready: false
errors: []
```

Decision counts：

```text
SURVIVED_FOR_REPLAY_EXTENSION: 2
RESTRICTED_SHADOW_ONLY: 1
MODEL_CANDIDATE_NEEDS_MORE_EVIDENCE: 1
MONITOR_ONLY: 4
REJECTED: 2
BLOCKED_CONTRACT: 1
BLOCKED_MODEL_EVIDENCE: 2
```

Surviving candidates：

```text
feature_group_ablation_by_regime
  decision: SURVIVED_FOR_REPLAY_EXTENSION
  next: run no-hindsight replay extension for top feature groups only
  reason: feature screen found traceable SHADOW_CANDIDATE rows; survival limited to replay extension, not model training

sector_industry_context
  decision: SURVIVED_FOR_REPLAY_EXTENSION
  next: run replay extension with sector cap and leave-one-out industry features
  reason: industry / sector rows appear among SHADOW_CANDIDATE features and are lineage-traceable
```

自動淘汰 / 降級摘要：

- `BIG_BULL family_only model`：`BLOCKED_MODEL_EVIDENCE`，sealed stability 仍擋 model promotion。
- `BIG_BULL family_only ranking`：`RESTRICTED_SHADOW_ONLY`，14B 已證明 overlap 太低、turnover 偏高、sector concentration 太高且 10D 輸 production。
- `big_bull_blended_rerank`：`MONITOR_ONLY`，D+1 接近 family_only，但 D+2 / D+3 轉弱。
- `big_bull_blended_score`：`REJECTED`，先前 portfolio replay 已淘汰。
- `HIGH_CHOPPY soft feature`：`MONITOR_ONLY`，soft feature 整體 AUC / TopN delta 微負，只保留分層診斷。
- `HIGH_CHOPPY restricted overlay`：`REJECTED`，14B 中 rolling / strict 10D slice 明顯輸 production。
- `candidate_persistence`：`MONITOR_ONLY`，近期有部分訊號但 extended evidence 不穩。
- `portfolio_risk_overlay`：`MONITOR_ONLY`，缺 replay / extended evidence。
- `combined_conservative`：`BLOCKED_CONTRACT`，必須等單項候選先通過。
- `technical_only_training_lane`：`MODEL_CANDIDATE_NEEDS_MORE_EVIDENCE`，research-only lane，仍需 sealed/replay evidence。
- `global_regime_family_training_candidates`：`BLOCKED_MODEL_EVIDENCE`，總 artifact monitor-only，且 BIG_BULL downstream sealed stability blocked。

## 2026-06-07 Alpha Overlay Follow-up

這輪補測 `alpha_candidate` 研究鏈，結論是降級 `MONITOR_ONLY`，不進 portfolio promotion。

Artifact：

- `artifacts/model_experiments/alpha_candidate_features_2026-06-07.parquet`
- `artifacts/model_experiments/alpha_candidate_signal_check_2026-06-07.json`
- `artifacts/model_experiments/alpha_candidate_offline_ablation_2026-06-07.json`
- `artifacts/model_experiments/alpha_candidate_overlay_2026-06-07.json`
- `artifacts/model_experiments/alpha_candidate_overlay_replay_constrained_2026-06-07.json`
- `artifacts/model_experiments/alpha_candidate_overlay_replay_constrained_blend020_2026-06-07.json`
- `artifacts/model_experiments/alpha_candidate_overlay_replay_constrained_blend030_2026-06-07.json`

結果：

```text
feature_materialization: OK
signal_check: OK, shadow_candidate_count=3
offline_ablation: REJECTED as model feature, auc_delta=-0.000440, topn_return_delta=-0.003507
overlay_proxy: PROMOTE_TO_REPLAY_CANDIDATE, best_variant=blend_0.10, best_topn_delta=+0.002585, positive_folds=2/3
constrained_replay_blend_0.10: REJECTED, return_delta=+0.001505, positive_folds=1/3, avg_overlap=0.705000
constrained_replay_blend_0.20: REJECTED, return_delta=+0.000712, positive_folds=1/3, avg_overlap=0.675000
constrained_replay_blend_0.30: REJECTED, return_delta=+0.002056, positive_folds=1/3, avg_overlap=0.656667
portfolio_replay: SKIPPED, because replay fold gate failed
decision: MONITOR_ONLY
```

修正：

- `scripts/research_alpha_candidate_overlay_replay.py` 現在未指定 `--overlay-artifact` 時會讀最新 `alpha_candidate_overlay_YYYY-MM-DD.json`，避免錯用 fallback `blend_0.30`。
- `scripts/research_alpha_candidate_overlay_replay.py` 的正式 replay 採 constrained 設定可明確保留 baseline 股票池，不讓 alpha overlay 大幅換股。
- `scripts/research_alpha_candidate_overlay_portfolio_replay.py` / `scripts/verify_alpha_candidate_overlay_portfolio_replay.py` 已補 portfolio gate 與 verifier mutation self-test，防止壞 artifact 硬標 promotion-review candidate。

判斷：

`alpha_candidate` 可以保留為 monitor / future overlay tuning source，但本輪不允許進 production ranking、不允許進 portfolio promotion review、不允許改 `risk_adjusted_score`。

## 2026-06-08 Operational Rule Follow-up

接續 BATCH-01 survivor 與 constrained K7 / sector-cap / operational rule 既有 artifact，今天重建營運規則報告並推進 gross55 shadow monitor。

Artifact：

- `artifacts/model_experiments/operational_rule_candidate_report_2026-06-08.json`
- `artifacts/model_experiments/operational_rule_experiment_report_2026-06-08.json`
- `artifacts/model_experiments/operational_portfolio_rule_report_2026-06-08.json`
- `artifacts/model_experiments/operational_long_rule_validation_report_2026-06-08.json`
- `artifacts/model_experiments/gross55_operational_shadow_dry_run_2026-06-08.json`
- `artifacts/model_experiments/gross55_daily_shadow_monitor_2026-06-08.json`
- `artifacts/model_experiments/gross55_daily_shadow_monitor_batch_2026-06-08.json`

結果：

```text
operational_rule_candidate: CONTINUE_RULE_RESEARCH_NO_PROMOTION
operational_rule_experiment: KEEP_RESEARCHING_NO_DEPLOYABLE_RULE_YET
oprule_01: DYNAMIC_GUARD_CANDIDATE
oprule_02: RANK_BUCKET_NOT_STABLE_ENOUGH
oprule_03: SECTOR_GUARD_REQUIRED_BUT_NOT_VALIDATED
oprule_04: READY_FOR_SHADOW_MONITOR_ONLY
portfolio_rule: PORTFOLIO_RULE_RESEARCH_ONLY
long_validation: DENSE_LONG_VALIDATION_SELECTS_CONSERVATIVE_GROSS55_CANDIDATE
gross55_operational_shadow: READY_FOR_OPERATIONAL_SHADOW_MONITOR
gross55_daily_monitor: MONITOR_WOULD_REDUCE_TODAY_EXPOSURE
gross55_batch_monitor: MONITOR_ACTIVE_RECENT_EXPOSURE_REDUCTION
recent_ranking_days: 12
would_reduce_exposure_days: 12
default_allowed: false
```

判斷：

`gross55` 是 portfolio 層保守曝險 shadow candidate，不是新模型、不改 Top10、不改正式分數。長區間證據顯示它降低回撤但犧牲報酬，所以目前只能進每日 shadow monitor；未達最小樣本前不得升預設。

下一步：

- 繼續累積 `gross55_daily_shadow_monitor_batch`，直到 ranking days / matured outcomes 達 sample policy。
- `sector45` 保留 monitor，不作 default。
- `rank bucket top3/top7` 只保留分層觀察，不改 Top10 規則。

### Daily Shadow Status Automation

2026-06-08 已補一張每日彙整 artifact，避免主線需要人工翻多條 shadow 分支：

- `artifacts/model_experiments/daily_shadow_status_2026-06-08.json`
- `artifacts/model_experiments/daily_shadow_status_2026-06-08.md`
- `artifacts/model_experiments/daily_shadow_status_verification_latest.json`

狀態：

```text
active_daily_monitor_count: 2
research_monitor_only_count: 3
total_branch_count: 5
closest_to_review: gross55_exposure_shadow
gross55 ranking_days_remaining: 8
gross55 matured_1d_days_remaining: 6
production_ready_branch_count: 0
training_schedule_status: candidate training/retrain remains manual; daily automation only runs ranking and shadow monitors
```

Automation 接入：

- `config/automation.yaml` 新增 `daily.daily_shadow_status_report_enabled=true`。
- `scripts/run_automation.py` daily 流程在 `gross55` / `capital_entry_quality` shadow monitor 後產生 `daily_shadow_status_YYYY-MM-DD.json`。
- `uv run --with-requirements requirements.txt python scripts/run_automation.py daily --dry-run --resource-profile local_safe` 已確認 `daily_shadow.status_report` step 會被排入流程。

Guard：

```text
models/latest_lgbm.pkl hash: 76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675
production_ranking_changed: false
risk_adjusted_score_changed: false
formal_clawd_message_created: false
promotion_ready: false
```

## PM 介入條件

只有以下情況需要停下來找 PM：

- 要覆蓋或替換 `models/latest_lgbm.pkl`。
- 要改正式 production ranking / `risk_adjusted_score`。
- 要正式推播或產生正式 Clawd message。
- 要新增正式盤勢類別。
- 三次重跑仍遇同一 blocker。
- 需要外部資料或人工決策才能避免後照鏡。

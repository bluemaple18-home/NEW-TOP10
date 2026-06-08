# RESEARCH-TOOLING split plan

## 任務ID

`RESEARCH-TOOLING-SPLIT-PLAN`

## 卡片類型｜派工對象

Merge Slicing / Review Guard｜Codex / reviewer

## 任務目的

把 2026-06-08 dirty tree 拆成可獨立 review、可獨立 commit 的小線，避免 research tooling、正式 ranking、model contract、daily automation 與 ops hardening 混成大包。

## 全域邊界

- 不把 `training_launch_ready=true` 解讀成 production promotion。
- 不把 shadow / replay / diagnostic result 直接寫入正式 `ranking_YYYY-MM-DD.csv`。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不修改 production `risk_adjusted_score`，除非該線已走正式 promotion review。
- 每條線 stage 前先跑：

```bash
uv run --with-requirements requirements.txt python scripts/verify_research_tooling_merge_slices.py --staged
git diff --check
```

`--staged` 預設只允許一個完整 slice；若 reviewer 明確要合併多個完整 slice，必須加 `--allow-multiple-slices`，並在 review 證據中說明。

## Slice A：production ranking overlay / K9

### 狀態

暫停普通 research tooling commit。已修正預設：

- `production_ranking_overlay.enabled=false`
- `production_ranking_overlay.promotion_review_approved=false`
- ranker 必須同時 enabled + approved 才會改正式 Top10。

### 可 stage 檔案

- `app/agent_b_ranking.py`
- `config/signals.yaml`
- `scripts/verify_production_ranking_overlay.py`
- `docs/tasks/2026-06-04_RANKING-QUALITY-11_promote_k9_with_baseline_k8_controls.md`

### 必跑

```bash
uv run --with-requirements requirements.txt python scripts/verify_production_ranking_overlay.py --mode default-off
uv run --with-requirements requirements.txt python -m py_compile app/agent_b_ranking.py scripts/verify_production_ranking_overlay.py
```

### 不可做

- 不在未完成 promotion review 時開啟 `enabled=true` 或 `promotion_review_approved=true`。
- 不與 chip-flow / daily monitor / factor registry 混 commit。

## Slice B：factor registry / leakage guard

### 可 stage 檔案

- `app/modeling/factor_registry.py`
- `app/modeling/__init__.py`
- `app/modeling/feature_contract.py`
- `scripts/build_factor_run_manifest.py`
- `scripts/verify_model_foundation.py`

### 必跑

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
uv run --with-requirements requirements.txt python -m py_compile app/modeling/factor_registry.py app/modeling/feature_contract.py scripts/build_factor_run_manifest.py scripts/verify_model_foundation.py
```

### Review 重點

- `future_*`、`target`、`label_*` 欄位不得進 LightGBM candidate feature。
- 這是 model contract change，不可混進純 research closure。

## Slice C：daily shadow monitor automation

### 狀態

已修正預設為手動開啟：

- `gross55_shadow_monitor_enabled=false`
- `gross55_shadow_monitor_batch_enabled=false`
- `capital_entry_quality_shadow_monitor_enabled=false`
- `capital_entry_quality_shadow_monitor_batch_enabled=false`
- `shadow_historical_evidence_report_enabled=false`
- `daily_shadow_status_report_enabled=false`

### 可 stage 檔案

- `config/automation.yaml`
- `scripts/run_automation.py`
- `scripts/build_gross55_daily_shadow_monitor.py`
- `scripts/build_gross55_daily_shadow_monitor_batch.py`
- `scripts/build_capital_entry_quality_daily_shadow_monitor.py`
- `scripts/build_capital_entry_quality_daily_shadow_monitor_batch.py`
- `scripts/build_shadow_historical_evidence_report.py`
- `scripts/build_daily_shadow_status_report.py`
- 對應 `scripts/verify_*` 檔案

### 必跑

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/run_automation.py scripts/build_gross55_daily_shadow_monitor.py scripts/build_capital_entry_quality_daily_shadow_monitor.py scripts/build_shadow_historical_evidence_report.py scripts/build_daily_shadow_status_report.py
```

### 不可做

- 不只 stage `config/automation.yaml` / `scripts/run_automation.py`。
- 不把 shadow monitor 預設開成 daily production 流程。

## Slice D：portfolio replay / exit-rule tooling

### 可 stage 檔案

- `scripts/run_backtest_replay.py`
- `scripts/run_portfolio_replay.py`
- `scripts/verify_backtest_replay.py`
- `scripts/verify_portfolio_replay.py`
- `scripts/build_high_choppy_context_overlay.py`
- `scripts/research_regime_family_training_candidates.py`

### 已修正

`scripts/run_portfolio_replay.py` 的 regime helper 改成 lazy import；未使用 `--market-regime-history` / regime exposure 參數時，clean checkout 不會因 untracked helper import 失敗。

### 必跑

```bash
uv run --with-requirements requirements.txt python scripts/verify_backtest_replay.py
uv run --with-requirements requirements.txt python scripts/verify_portfolio_replay.py
```

## Slice E：Clawd timeout hardening

### 可 stage 檔案

- `scripts/report_stock_status.sh`

### 必跑

```bash
bash -n scripts/report_stock_status.sh
```

### Review 重點

- 只新增 timeout wrapper。
- 不改實際送出開關、不改 channel/target 預設。

## Slice F：chip-flow research-only tooling

### 可 stage 檔案

- `app/finmind_integrator.py`
- `scripts/build_chip_data_contract.py`
- `scripts/build_chip_flow_materialized_features.py`
- `scripts/build_chip_flow_runtime_coverage.py`
- `scripts/build_chip_warning_shadow_report.py`
- `scripts/build_chip_warning_replay_aggregate.py`
- `scripts/build_chip_composite_warning_report.py`
- `scripts/build_chip_flow_readiness_report.py`
- 對應 `scripts/verify_chip_*` 檔案

### 不可做

- 不改 production ranking / score。
- 不把 warning-only result 轉成 promotion evidence。

## Guard

使用：

```bash
uv run --with-requirements requirements.txt python scripts/verify_research_tooling_merge_slices.py
uv run --with-requirements requirements.txt python scripts/verify_research_tooling_merge_slices.py --staged
```

第一個檢查 workspace 中被碰到的 slice 依賴是否存在；第二個檢查 staged set 是否半套。
第二個也會擋多個完整 slice 同時 staged；只有明確加 `--allow-multiple-slices` 才放行。

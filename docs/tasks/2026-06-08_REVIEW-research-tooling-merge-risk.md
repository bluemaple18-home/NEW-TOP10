# REVIEW-20260608 research tooling merge risk

日期：2026-06-08
狀態：REVIEWED_BLOCKED_FOR_MIXED_COMMIT

## Scope

本次只做 dirty / untracked code 與 research tooling merge risk 盤點，未 `git add`、未 commit、未 push，未修改 production ranking / model。

已讀：

- `docs/tasks/2026-06-08_RESEARCH-CLOSURE-STATUS.md`
- `docs/tasks/2026-06-08_CHIP-FLOW_warning_research_handoff.md`
- `docs/tasks/2026-06-08_EXIT-SIGNAL-01_price_rank_volume_overheat_reversal.md`
- `git status --short`

輕量檢查：

- `git diff --check`：OK

## Findings

- [P0] 正式 ranking overlay 已預設啟用，會改 production Top10 - `config/signals.yaml:54`
  `production_ranking_overlay.enabled: true`，且 `app/agent_b_ranking.py:737` 會在正式 `run_ranking()` 裡啟動 `_overlay_topn()`。這會把 baseline Top10 改成「保留 Top9 + shadow score 補 1 檔」，與 closure / chip-flow handoff / EXIT-SIGNAL-01 的「不可直接改 production ranking、risk_adjusted_score、正式推播」邊界衝突。這組不可進下一個普通 research tooling commit；若要保留，必須另開正式 promotion review，且預設應為 off。

  Fix status：已修正為 `production_ranking_overlay.enabled=false` 並新增 `promotion_review_approved=false`；`StockRanker._production_overlay_enabled()` 現在必須同時滿足 strict boolean `enabled is True` + `promotion_review_approved is True`，env request 也不能繞過 approval。default-off 不再額外寫 `baseline_ranking_YYYY-MM-DD.csv` / comparison artifacts。

- [P1] production ranking overlay 與 verifier 是一整組正式升級，不是純 research tooling - `app/agent_b_ranking.py:445`
  新增 `_production_overlay_enabled()`、`_feature_group_shadow_score()`、`_overlay_topn()` 與 comparison artifact，另有 untracked `scripts/verify_production_ranking_overlay.py` 驗證正式 K overlay。這不是只產生研究 artifact，而是讓正式 `ranking_YYYY-MM-DD.csv` 可被 shadow score 改寫。建議整組暫不 stage：`app/agent_b_ranking.py`、`config/signals.yaml`、`scripts/verify_production_ranking_overlay.py`。

- [P1] modified 檔案依賴 untracked 新檔，分批 stage 會造成 import/runtime failure - `app/modeling/feature_contract.py:19`
  `feature_contract.py` 與 `app/modeling/__init__.py` 現在引用 `app/modeling/factor_registry.py`，但該檔是 untracked。`scripts/run_portfolio_replay.py:25` 也引用 untracked `scripts/build_high_choppy_context_overlay.py` 與 `scripts/research_regime_family_training_candidates.py`。若只 stage modified 檔，乾淨 checkout 會直接壞掉。這些必須成套 commit，或整組暫不 stage。

- [P1] daily automation 預設新增 shadow monitor 步驟，但 runner 依賴大量 untracked scripts - `scripts/run_automation.py:126`
  `config/automation.yaml:29` 到 `:34` 把 gross55、capital entry、historical evidence、daily shadow status 監控設為 true；runner 會呼叫 `scripts/build_gross55_daily_shadow_monitor.py`、`scripts/build_capital_entry_quality_daily_shadow_monitor.py`、`scripts/build_shadow_historical_evidence_report.py`、`scripts/build_daily_shadow_status_report.py` 等 untracked scripts。雖然呼叫多數是 `allow_failure=True`，但不可只 stage config/runner；否則 daily status 會出現缺腳本/缺 artifact 的噪音，且 merge 後行為與 review 證據不一致。

  Fix status：已修正 config 預設為 false；shadow monitors 只允許手動開啟或成套 stage 後再開。

- [P2] model feature contract change 屬模型邊界，需要獨立 review，不應混進 research closure - `app/modeling/feature_contract.py:150`
  `candidate_feature_columns()` 改成經過 factor registry 過濾，並將 future/target 類欄位 block。方向合理，但這會影響 LightGBM 候選特徵集合；即使不是直接訓練，也屬 model contract change。建議拆成 `factor registry / leakage guard` 小 commit，帶 `scripts/verify_model_foundation.py` 與 `scripts/build_factor_run_manifest.py`。

- [P2] Clawd timeout wrapper 可獨立收，但不能跟 ranking/model 變更混 commit - `scripts/report_stock_status.sh:11`
  新增 `NEWCLAWD_TIMEOUT_SECONDS` 與 timeout kill fallback，沒有看到正式送出開關被打開；可作小型 ops hardening。建議單獨 commit，避免和 research promotion 風險混在一起。

## Merge Risk Summary

目前 dirty tree 混在一起的主題至少有七組：

1. production ranking overlay / K9 正式排名改寫。
2. factor registry / model feature contract。
3. daily shadow monitor automation。
4. chip-flow data/readiness/warning-only research tooling。
5. portfolio replay / exit rule / gross exposure research tooling。
6. Clawd send timeout hardening。
7. 大量 research task cards 與 backlog scripts。

這些不應做大包 commit。最危險的是第 1 組，因為它已經會改正式 ranking 輸出。

新增 guard：

- `scripts/verify_research_tooling_merge_slices.py`
- `docs/tasks/2026-06-08_RESEARCH-TOOLING-SPLIT-PLAN.md`

用來檢查 workspace / staged set 是否半套拆線；`--staged` 預設也會擋多個完整 slice 同時 staged，除非明確加 `--allow-multiple-slices`。

## 建議 Stage 清單

下一個 commit 建議只收最小 review / closure 證據：

- `docs/tasks/2026-06-08_REVIEW-research-tooling-merge-risk.md`

後續可拆 commit，但需各自補驗證：

- `clawd timeout hardening`
  - `scripts/report_stock_status.sh`

- `factor registry leakage guard`
  - `app/modeling/factor_registry.py`
  - `app/modeling/__init__.py`
  - `app/modeling/feature_contract.py`
  - `scripts/build_factor_run_manifest.py`
  - `scripts/verify_model_foundation.py`

- `chip-flow research-only tooling`
  - `app/finmind_integrator.py`
  - `scripts/build_chip_data_contract.py`
  - `scripts/build_chip_flow_materialized_features.py`
  - `scripts/build_chip_flow_runtime_coverage.py`
  - `scripts/build_chip_warning_shadow_report.py`
  - `scripts/build_chip_warning_replay_aggregate.py`
  - `scripts/build_chip_composite_warning_report.py`
  - `scripts/build_chip_flow_readiness_report.py`
  - `scripts/verify_chip_data_contract.py`
  - `scripts/verify_chip_flow_materialized_features.py`
  - `scripts/verify_chip_flow_runtime_coverage.py`
  - `scripts/verify_chip_warning_shadow_report.py`
  - `scripts/verify_chip_warning_replay_aggregate.py`
  - `scripts/verify_chip_composite_warning_report.py`
  - `scripts/verify_chip_flow_readiness_report.py`
  - `scripts/build_feature_experiment_gate.py`

- `daily shadow monitor automation`
  - `config/automation.yaml`
  - `scripts/run_automation.py`
  - `scripts/build_gross55_daily_shadow_monitor.py`
  - `scripts/build_gross55_daily_shadow_monitor_batch.py`
  - `scripts/build_capital_entry_quality_daily_shadow_monitor.py`
  - `scripts/build_capital_entry_quality_daily_shadow_monitor_batch.py`
  - `scripts/build_shadow_historical_evidence_report.py`
  - `scripts/build_daily_shadow_status_report.py`
  - matching `scripts/verify_*` for those reports

- `portfolio replay / exit-rule research tooling`
  - `scripts/run_backtest_replay.py`
  - `scripts/run_portfolio_replay.py`
  - `scripts/verify_portfolio_replay.py`
  - `scripts/build_high_choppy_context_overlay.py`
  - `scripts/research_regime_family_training_candidates.py`
  - `artifacts/portfolio_replay_verification_latest.json` only if this tracked latest verifier artifact is intentionally maintained by repo policy

## 暫不 Stage 清單

暫不 stage，除非另走正式 promotion review：

- `app/agent_b_ranking.py`
- `config/signals.yaml`
- `scripts/verify_production_ranking_overlay.py`

暫不 stage 為單一大包：

- 所有 `docs/tasks/2026-06-01_*`、`docs/tasks/2026-06-03_*`、`docs/tasks/2026-06-04_*`、`docs/tasks/2026-06-05_*` untracked task cards。
- 大量 `scripts/build_*`、`scripts/research_*`、`scripts/run_*`、`scripts/verify_*` untracked backlog scripts。

不該進 git / 需避免誤加：

- `.codegraph/*.db`、`.codegraph/*.db-shm`、`.codegraph/*.db-wal`
- local cache、raw data、臨時 replay 輸出與未被 repo 明確追蹤的 `artifacts/model_experiments/*`
- 任何 API token、FinMind token、Clawd local runtime path override 或本機 credentials

## Open Questions

- `production_ranking_overlay` 是否已有正式 promotion 決策卡？若沒有，必須改回預設 off 或完全不 stage。
- `daily_shadow_status_report` 是否要納入每日 automation，還是只作手動 research closure 工具？
- `factor_registry` 是否只作 manifest/leakage guard，或會成為下一輪訓練 gate？若是後者，需要模型合約卡。

## Testing Gaps

- 尚未跑完整 `uv run` 測試或 daily automation；本次 review 只做 diff / graph / status 風險盤點。
- production ranking overlay 未見正式 promotion approval；現有 verifier 只證明 K overlay artifact 形狀，不證明可以升正式排名。
- daily automation 新增 shadow monitor 需在乾淨 checkout 上驗證「所有依賴腳本已 stage」後再跑。

## 結論

目前不建議 merge / commit 大包 dirty tree。下一個 commit 只收 review 證據最安全；其餘請按主題拆分。production ranking overlay 整組暫停，不應跟 research tooling 一起進 git。

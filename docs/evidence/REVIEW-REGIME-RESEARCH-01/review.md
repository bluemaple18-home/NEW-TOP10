# REVIEW-REGIME-RESEARCH-01 Review Evidence

## Verdict

`GO_SHADOW_ONLY`。本次範圍可用於 read-only diagnostics、research artifacts 與 shadow replay；不可據此調整 production model、`RankingPolicy`、`risk_adjusted_score` 或自動 promotion。

## Findings

### [P1][Resolved] shadow ranking 原本可覆寫 production ranking

- 原始風險：`research_regime_shadow_ranking.py` 接受任意 `--output-dir`，並直接寫入 `ranking_YYYY-MM-DD.csv`；若指到 `artifacts/` 或來源 ranking 目錄，research-only 宣告無法阻止正式 artifact 被覆寫。
- 修復：`validate_research_output_dir()` 強制輸出必須是 `artifacts/backtest/` 的子目錄，且不可等於研究根目錄或 `--dates-from-dir`。
- 回歸：`tests/test_regime_research_boundaries.py` 覆蓋安全路徑、production/data/model/root 路徑與來源目錄拒絕案例。

### [P2][Restriction] 兩類 regime 沒有專屬 shadow scoring evidence

- `build_market_regime_history.py` 的固定 taxonomy 包含 `BROAD_RISK_ON`、`CHOPPY_RANGE`。
- `apply_regime_shadow_score()` 未為這兩類定義專屬分支，會走既有 generic fallback。
- 本次不憑主觀判斷新增權重。這兩類只能算 baseline fallback，不可宣稱為 regime-specific candidate；要晉級須另開有 sealed OOS／replay 證據的實驗卡。

### [P2][Restriction] `--skip-heavy` 不會重建 strategy matrix

- `run_weekend_research_matrix.py --skip-heavy` 仍會比較既有 strategy artifacts 並產生 decision report。
- 輸出 manifest 會保留實際 step 與總狀態，但該模式只能做快速 audit／compare，不能證明 strategy matrix 是本次新鮮重跑。

## Boundary audit

| Component | Reads | Writes | Model/ranking mutation | Shadow eligibility |
|---|---|---|---|---|
| `build_market_regime_history.py` | feature/reference data | JSON/Markdown research artifact | 無 | diagnostics 可用 |
| `research_feature_group_ablation_by_regime.py` | M4 feature frame、regime、industry map | JSON/Markdown research artifact | 無 | feature screening 可用 |
| `research_regime_shadow_ranking.py` | production model/data、regime、industry map | 隔離的 backtest ranking CSV/JSON | 只改 shadow frame；guard 後不寫 production | replay 可用 |
| `audit_research_dataset_coverage.py` | clean/reference/artifact coverage | JSON/Markdown audit | 無；`can_enter_model` 只是建議欄位 | readiness audit 可用 |
| `run_weekend_research_matrix.py` | 既有 research/backtest inputs | backtest reports/manifests | command graph 無 fetch/train/live-send | orchestration 可用 |

## Verification

```text
.venv/bin/python -m pytest -q tests/test_regime_research_boundaries.py tests/test_regime_conditional_suite.py tests/test_weekend_readiness_audit.py
25 passed

.venv/bin/python scripts/verify_feature_group_ablation_by_regime.py
FEATURE_GROUP_ABLATION_BY_REGIME_OK

.venv/bin/python -m compileall -q <five reviewed scripts>
PASS

git diff --check
PASS
```

## Promotion boundary

- Shadow：允許。
- Production promotion：`NO_GO`。
- 下一步若要改善排序，需另開候選實驗卡，鎖定 sealed OOS、成熟 forward return、replay、portfolio risk 與可逆 promotion contract。

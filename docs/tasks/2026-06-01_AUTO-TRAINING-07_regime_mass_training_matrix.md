# AUTO-TRAINING-07 regime mass training matrix

## 任務ID

`AUTO-TRAINING-07`

## 卡片類型｜派工對象

Mass Training Experiment / Regime Family Tags｜Codex

## 請讀

- `docs/tasks/2026-06-01_AUTO-TRAINING-00_readiness_roadmap.md`
- `docs/architecture/MODEL_IMPROVEMENT_LOOP.md`
- `docs/architecture/MODEL_EXPERIMENT_LEDGER.md`
- `.work/TRAIN-20260531-regime-family-candidates/result.md`
- `artifacts/model_experiments/regime_family_training_candidates_2026-06-01.json`
- `artifacts/model_experiments/regime_family_sealed_stability_2026-06-01.json`
- `scripts/research_regime_family_training_candidates.py`
- `scripts/research_regime_family_sealed_replay.py`
- `scripts/research_big_bull_shadow_ranking.py`
- `scripts/run_backtest_replay.py`
- `scripts/run_portfolio_replay.py`
- `scripts/model_experiment_ledger.py`

## 任務目的

開始第一輪大量訓練候選測試，優先研究兩個 regime family tag：

- `BIG_BULL`：權值 / 主流族群帶動的高檔牛市。
- `HIGH_CHOPPY`：高檔震盪段。

本卡只做 research-only 大量測試與候選訓練矩陣，不允許 production promotion。

## 目前資料事實

以現有 artifact 看：

- market regime history：`2025-01-02 ~ 2026-05-29`，338 個交易日。
- mature label 可用到約 `2026-05-15`，因 10D horizon 需要未來出場資料。
- `BIG_BULL` family dates：168 天，範圍 `2025-01-17 ~ 2026-05-15`。
- `HIGH_CHOPPY` family dates：14 天，範圍 `2025-03-06 ~ 2026-04-30`。
- `BIG_BULL` 與 `HIGH_CHOPPY` 重疊 12 天；這代表 `HIGH_CHOPPY` 多半是「大牛市裡的高檔震盪段」，不是獨立市場 preset。

## 訓練 / 驗證區間規劃

### A. 主資料窗

使用已成熟 label 的主資料窗：

```text
2025-01-02 ~ 2026-05-15
```

原因：

- 這段已有目前可重現 features / labels。
- 包含近半年高檔牛市。
- 10D label 已成熟到 2026-05-15 左右，避免偷看未來。

### B. BIG_BULL 主測試窗

`BIG_BULL` 可進大量測試，因樣本數 168 天足夠做 walk-forward / sealed replay。

建議 outer sealed windows：

```text
40D sealed:  latest 40 mature trade days
60D sealed:  2026-02-06 ~ 2026-05-15
80D sealed:  latest 80 mature trade days
100D sealed: latest 100 mature trade days
```

固定 embargo：

```text
10 trade days
```

Walk-forward：

```text
4-fold chronological family validation
6-fold chronological family validation
```

訓練法矩陣：

- `global_baseline`
- `family_only_training`
- `family_weighted_training`
- `family_model_ranking_only`
- `family_global_blend_ranking`

評估：

- AUC / logloss。
- Top10 future return。
- Top10 uplift vs same-day universe。
- D 日 ranking、D+1 開盤進場 replay。
- 1D / 3D / 5D / 10D horizon。
- portfolio replay / max drawdown / concentration。

### C. HIGH_CHOPPY 診斷窗

`HIGH_CHOPPY` 目前只有 14 天，不可做正式訓練候選 promotion。

這一輪只能做：

- diagnostic-only ranking replay。
- 與 `BIG_BULL` 重疊日拆解。
- 是否需要擴歷史資料的 coverage audit。

若要訓練 `HIGH_CHOPPY` 候選，必須先擴資料：

```text
目標補歷史窗：2023-11-01 ~ 2024-12-31
```

要求：

- ETL 可重現。
- feature contract / data contract 通過。
- label mature。
- 新增 `HIGH_CHOPPY` family dates 後至少達 30 天，且至少 3 個 OK folds。

未達門檻前，`HIGH_CHOPPY` 只能是 `MONITOR_ONLY` 或 `DIAGNOSTIC_ONLY`。

## Mass Test Matrix

### Track 1：BIG_BULL model candidate

目的：測 family-specific training 是否能在高檔牛市中穩定改善。

輸出：

- `artifacts/model_experiments/big_bull_training_matrix_YYYY-MM-DD.json`
- `artifacts/model_experiments/big_bull_training_matrix_YYYY-MM-DD.md`

最小通過條件：

- 3+ OK folds。
- sealed AUC 不低於 global baseline。
- Top10 return delta vs global > 0。
- Top10 uplift > 0。
- 40D / 60D / 80D / 100D 不可只靠單一窗口通過。

### Track 2：BIG_BULL ranking/replay candidate

目的：即使 family model 不適合取代分類模型，也要驗證是否適合只做 Top10 ranking。

輸出：

- `artifacts/backtest/shadow_rankings_big_bull/`
- `artifacts/backtest/replay_big_bull_ranking_YYYY-MM-DD.json`
- `artifacts/backtest/portfolio_replay_big_bull_ranking_YYYY-MM-DD.json`

最小通過條件：

- replay 10D positive uplift。
- portfolio replay 不惡化 max drawdown。
- group concentration 不升高。
- input path 全部 repo-relative。

### Track 3：HIGH_CHOPPY diagnostic

目的：判斷高檔震盪到底是獨立模型問題，還是 `BIG_BULL` 裡的風險 overlay / sizing 問題。

輸出：

- `artifacts/model_experiments/high_choppy_diagnostic_YYYY-MM-DD.json`
- `artifacts/model_experiments/high_choppy_diagnostic_YYYY-MM-DD.md`

最小判定：

- 若 family dates < 30：只可 `MONITOR_ONLY`。
- 若重疊 `BIG_BULL` 比例高：優先開 ranking / sizing overlay 假設，不開正式分類模型。

### Track 4：Data extension audit

目的：確認是否值得往 2023/2024 拉資料，補足 `HIGH_CHOPPY`。

輸出：

- `artifacts/model_experiments/regime_data_extension_audit_YYYY-MM-DD.json`

要檢查：

- features 起訖日。
- OHLC coverage。
- value / volume coverage。
- industry map coverage。
- label maturity。
- 是否可重現 `HIGH_CHOPPY` family tag。

## Ledger 要求

每個 track 都要進 ledger，且 status 先是 `pending`。

建議 ledger ids：

- `training_policy:big_bull:family-training-matrix`
- `ranking:big_bull:family-model-top10-ranking`
- `ranking:high_choppy:diagnostic-ranking-risk-overlay`
- `data:regime_history:extend-2023-2024-for-high-choppy`

若實作現有 ledger type 不支援 `data` 或 `ranking`，請使用現有合法 type 中最接近者，並在 `hypothesis` 寫清楚，不得改 ledger schema 亂加 type。

## 不可做

- 不覆蓋 `models/latest_lgbm.pkl`。
- 不修改 production ranking / `risk_adjusted_score`。
- 不新增新的 base regime。
- 不把 `BIG_BULL` / `HIGH_CHOPPY` 當互斥市場 preset。
- 不把 `HIGH_CHOPPY` 14 天樣本硬拿去 promotion。
- 不因 Top10 replay 好，就回頭刪掉 AUC gate。
- 不用同輪診斷結果發明新 filter 再重算同一輪成功。
- 不把 `training_launch_ready=true` 解讀成 `promotion_ready=true`。

## 建議指令

先重建盤勢與候選：

```bash
uv run --with-requirements requirements.txt python scripts/build_market_regime_history.py \
  --output artifacts/market_regime_history_YYYY-MM-DD.json

uv run --with-requirements requirements.txt python scripts/research_regime_family_training_candidates.py \
  --date YYYY-MM-DD \
  --market-regime-history artifacts/market_regime_history_YYYY-MM-DD.json \
  --folds 4 \
  --embargo-trade-days 10 \
  --top-n 10
```

再跑 `BIG_BULL` sealed / stability：

```bash
uv run --with-requirements requirements.txt python scripts/research_regime_family_sealed_replay.py \
  --date YYYY-MM-DD \
  --market-regime-history artifacts/market_regime_history_YYYY-MM-DD.json \
  --families BIG_BULL \
  --sealed-trade-days 60 \
  --embargo-trade-days 10

uv run --with-requirements requirements.txt python scripts/build_regime_family_sealed_stability_report.py \
  --date YYYY-MM-DD \
  --family BIG_BULL \
  --artifact 40d=artifacts/model_experiments/regime_family_sealed_replay_big_bull_40d_YYYY-MM-DD.json \
  --artifact 60d=artifacts/model_experiments/regime_family_sealed_replay_YYYY-MM-DD.json \
  --artifact 80d=artifacts/model_experiments/regime_family_sealed_replay_big_bull_80d_YYYY-MM-DD.json \
  --artifact 100d=artifacts/model_experiments/regime_family_sealed_replay_big_bull_100d_YYYY-MM-DD.json
```

跑 ranking / replay：

```bash
uv run --with-requirements requirements.txt python scripts/research_big_bull_shadow_ranking.py \
  --date YYYY-MM-DD

uv run --with-requirements requirements.txt python scripts/run_backtest_replay.py \
  --rankings-dir artifacts/backtest/shadow_rankings_big_bull \
  --output artifacts/backtest/replay_big_bull_ranking_YYYY-MM-DD.json

uv run --with-requirements requirements.txt python scripts/run_portfolio_replay.py \
  --rankings-dir artifacts/backtest/shadow_rankings_big_bull \
  --output artifacts/backtest/portfolio_replay_big_bull_ranking_YYYY-MM-DD.json
```

驗證：

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --date YYYY-MM-DD --skip-model-research-flow --timeout-seconds 900
git diff --check
```

## 回報格式

```text
AUTO-TRAINING-07 status:
data window:
mature label end:
BIG_BULL family dates:
HIGH_CHOPPY family dates:
BIG_BULL training matrix:
BIG_BULL sealed stability:
BIG_BULL replay:
BIG_BULL portfolio replay:
HIGH_CHOPPY diagnostic:
data extension audit:
ledger entries:
promotion_ready:
errors:
```

## 收斂判定

- 若 `BIG_BULL` AUC 不穩但 replay 穩：只保留 ranking/replay candidate。
- 若 `BIG_BULL` AUC 與 replay 都穩：進下一張 sealed / rollback / promotion review 準備卡，但仍不自動 promotion。
- 若 `HIGH_CHOPPY` 樣本仍不足：只保留 diagnostic，先做資料擴充或風險 overlay 假設。
- 若任一 track 只在單一窗口有效：降級 `MONITOR_ONLY`。

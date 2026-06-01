# AUTO-TRAINING-03 BIG_BULL ranking replay

## 任務ID

`AUTO-TRAINING-03`

## 卡片類型｜派工對象

Ranking Replay Experiment / Regime Family Tag｜Codex

## 請讀

- `docs/architecture/MODEL_IMPROVEMENT_LOOP.md`
- `.work/TRAIN-20260531-regime-family-candidates/result.md`
- `scripts/research_regime_family_training_candidates.py`
- `scripts/research_regime_family_sealed_replay.py`
- `scripts/build_regime_family_sealed_stability_report.py`
- `scripts/run_backtest_replay.py`
- `scripts/run_portfolio_replay.py`

## 任務目的

把 `BIG_BULL` 從「模型替換候選」降回正確位置：ranking/replay follow-up candidate。驗證在 `BIG_BULL` tag 下，family model 只負責 Top10 排名時，是否能穩定勝過 global baseline。

## 背景

`BIG_BULL family_only_training` 在 Top10 return / uplift 有亮點，但 sealed AUC delta 不穩，因此不能取代正式模型。下一步只驗證 ranking / replay，不做 production promotion。

## 要做

- 使用固定 base regime + family tag taxonomy。
- 產出 `BIG_BULL` shadow ranking artifacts。
- 跑 D 日 ranking、D+1 開盤進場 replay。
- 評估 1D / 3D / 5D / 10D。
- 跑 40D / 60D / 80D / 100D window stability。
- 若結果通過，只能登記 ledger follow-up，不可 promotion。

## 不可做

- 不新增新的市場 preset。
- 不把 `BIG_BULL` 當正式分盤勢模型。
- 不改 production ranking。
- 不用 Top10 好結果回頭刪掉 AUC gate。
- 不覆蓋 `models/latest_lgbm.pkl`。

## 驗收

```bash
uv run --with-requirements requirements.txt python scripts/research_regime_family_training_candidates.py --date YYYY-MM-DD --market-regime-history artifacts/market_regime_history_YYYY-MM-DD.json
uv run --with-requirements requirements.txt python scripts/research_regime_family_sealed_replay.py --date YYYY-MM-DD --market-regime-history artifacts/market_regime_history_YYYY-MM-DD.json --families BIG_BULL
uv run --with-requirements requirements.txt python scripts/build_regime_family_sealed_stability_report.py --date YYYY-MM-DD --family BIG_BULL --artifact 40d=... --artifact 60d=... --artifact 80d=... --artifact 100d=...
uv run --with-requirements requirements.txt python scripts/run_backtest_replay.py --rankings-dir artifacts/backtest/shadow_rankings_big_bull --output artifacts/backtest/replay_big_bull_ranking_YYYY-MM-DD.json
uv run --with-requirements requirements.txt python scripts/run_portfolio_replay.py --rankings-dir artifacts/backtest/shadow_rankings_big_bull --output artifacts/backtest/portfolio_replay_big_bull_ranking_YYYY-MM-DD.json
git diff --check
```

## 回報格式

```text
AUTO-TRAINING-03 status:
family tag:
shadow rankings:
replay:
portfolio replay:
window stability:
decision:
promotion allowed:
errors:
```

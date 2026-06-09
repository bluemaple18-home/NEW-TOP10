# LONG-CANDIDATE-VALIDATION-01｜Odd-Lot Candidate Long History

## Root Question

候選 ranking 是否已經有足夠長區間證據，可以從研究候選推進到正式切換候選。

## Scope

- 補 `current_baseline_candidate_2026-06-08` 的長區間 candidate rankings。
- 比較 production ranking 與 candidate ranking。
- 使用小本金零股 portfolio 規格驗證：
  - Top7
  - 初始本金 100k / 300k / 500k
  - 最大總曝險 75%
  - 單檔上限 12%
  - 停損 12%
  - 至少持有 5 個交易日
  - 40 個交易日上限
  - `+25%` 賣出 1/3 後 runner
- 不改 production ranking。
- 不改 `models/latest_lgbm.pkl`。
- 不送推播。

## Evidence

- `artifacts/model_experiments/training_candidates/current_baseline_candidate_2026-06-08/candidate_rankings_2023-11-21_2026-05-15/manifest.json`
- `artifacts/model_experiments/candidate_historical_validation_gap_report_2026-06-10.json`
- `artifacts/model_experiments/market_regime_history_2023-11-21_2026-05-15.json`
- `artifacts/model_experiments/backtest_replay_production_top10_2023-11-21_2026-05-15_2026-06-10.json`
- `artifacts/model_experiments/backtest_replay_candidate_top10_2023-11-21_2026-05-15_2026-06-10.json`
- `artifacts/model_experiments/portfolio_replay_regime_attribution_odd_lot_candidate_top7_sl12_min5_300k_2023-11-21_2026-05-15_exit_ptp25_third_runner_2026-06-10.json`
- `artifacts/model_experiments/long_candidate_validation_report_2026-06-10.json`
- `artifacts/model_experiments/long_candidate_validation_report_verification_latest.json`

## Result

Candidate rankings 補到：

```text
production_ranking_days: 599
candidate_ranking_days: 598
comparable_days: 598
missing_candidate_dates: 2025-08-01
```

`2025-08-01` 在可用歷史 features 中不存在，因此不可硬補 ranking；長區間比較使用 598 個可比較 ranking days。

Ranking-day replay：

```text
10D avg net return delta: +0.018629
10D hit-rate delta: +0.011515
40D avg net return delta: +0.007253
40D hit-rate delta: +0.009169
```

Odd-lot portfolio replay：

| Capital | Candidate Return Delta | Candidate MaxDD Delta |
|---|---:|---:|
| 100k | +0.064604 | +0.013612 |
| 300k | +0.098802 | +0.033495 |
| 500k | +0.119586 | +0.055605 |

Candidate ranking 在三個本金級距都勝過 production，且最大回撤較小。

## Important Caveat

`+25%` 賣出 1/3 後 runner 不是已驗證定案規則。

300k candidate replay 中：

```text
candidate_exit_return_delta_vs_baseline: -0.025579
candidate_exit_drawdown_delta_vs_baseline: -0.014062
```

也就是這個 exit rule 對 candidate baseline 同時降低報酬、加深回撤。candidate ranking 本身有支持，但 `+25%` 賣 1/3 不應一起打包升正式。

同一長區間 exit matrix 顯示：

| Exit Rule | Total Return | MaxDD | Note |
|---|---:|---:|---|
| baseline | 0.527902 | -0.221876 | 40D 上限 + 12% 停損 |
| trail10 | 0.789239 | -0.145787 | 目前最佳 |
| ptp25_third_trail10 | 0.529326 | -0.144421 | 回撤接近最佳，但報酬明顯低於 trail10 |
| ptp25_third | 0.502323 | -0.235938 | 淘汰 |

trail10 在 100k / 300k / 500k candidate replay 也穩定：

| Capital | Total Return | MaxDD |
|---|---:|---:|
| 100k | 0.853544 | -0.143317 |
| 300k | 0.789239 | -0.145787 |
| 500k | 0.771425 | -0.146156 |

300k production peer 的 trail10 結果：

```text
total_return: 0.171402
max_drawdown: -0.226792
```

## Decision

```text
READY_FOR_SHADOW_WITH_TRAIL10_EXIT_CANDIDATE
```

含義：

- candidate ranking 有長區間證據支持。
- 不可直接 production switch。
- 不可宣稱 promotion ready。
- 下一步應把 candidate ranking 放入 shadow monitor / promotion review candidate。
- `+25%` 賣 1/3 exit rule 淘汰。
- `trail10` 可作為 exit rule candidate 進 shadow。
- 仍不可直接 production switch。

## Next Step

1. 固定 candidate ranking 作為單一主候選。
2. 不再新增 ranking 支線。
3. 下一階段只驗 candidate ranking + trail10：
   - production-adjacent shadow
   - 今日/每日推播不直接切
   - 累積 live shadow evidence
4. 若要進正式切換 review，需另外補「訊息/頁面如何表達 trail stop」與「非個人持倉提醒邊界」。

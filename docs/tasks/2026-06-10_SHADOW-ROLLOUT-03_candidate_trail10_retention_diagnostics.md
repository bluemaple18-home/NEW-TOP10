# SHADOW-ROLLOUT-03｜Candidate Trail10 Retention Diagnostics

## Root Question

`overlap-first` 回測失敗後，是否應該連同 `candidate ranking + trail10` 一起砍掉。

## Answer

不應該。

應砍的是 `overlap-first` 這個混合排序想法；`candidate ranking + trail10` 仍是主候選，但不能無條件替換正式版。

## Evidence

- `artifacts/model_experiments/candidate_trail10_retention_diagnostics_2026-06-10.json`
- `artifacts/model_experiments/candidate_trail10_retention_diagnostics_2026-06-10.md`
- `artifacts/model_experiments/candidate_trail10_retention_diagnostics_verification_latest.json`

## Key Numbers

Long window:

| Variant | Total Return | Max DD |
| --- | ---: | ---: |
| production trail10 | 17.14% | -22.68% |
| candidate trail10 | 78.92% | -14.58% |

Recent windows:

| Window | Production Return | Candidate Return | Candidate Delta |
| --- | ---: | ---: | ---: |
| recent_100 | 24.50% | 11.65% | -12.85% |
| recent_6m | 29.33% | 7.95% | -21.38% |

Calendar breakdown:

| Window | Production Return | Candidate Return | Delta |
| --- | ---: | ---: | ---: |
| 2024_H1 | 4.60% | 4.17% | -0.42% |
| 2024_H2 | -1.33% | -5.20% | -3.86% |
| 2025_H1 | -6.24% | 37.44% | +43.68% |
| 2025_H2 | -0.06% | 18.04% | +18.10% |
| 2026_YTD_to_0515 | 21.14% | 11.68% | -9.46% |

## Decision

```text
overlap-first: REJECTED_AS_REPLACEMENT
candidate_trail10: RETAIN_FOR_CONDITIONAL_SWITCH_RESEARCH
production_switch_ready: false
promotion_ready: false
```

## Interpretation

`candidate+trail10` 不是沒效。它在長區間明顯贏，尤其 2025 表現很好。

但它最近 100 天與近半年輸 production，代表現在不能直接替換正式每日推薦。下一步要測的是條件式切換：

- 哪些盤勢用 candidate+trail10。
- 哪些盤勢保留 production。
- 是否只把 candidate+trail10 作為候補或強勢股池，而不是整份每日榜替換。

## Boundary

- 不再救 `overlap-first` 當主排序。
- 不新增第四條排序支線。
- 不因近期 underperform 就砍掉 candidate+trail10。
- 不在 recent_100 / recent_6m 仍輸 production 時切正式推播。

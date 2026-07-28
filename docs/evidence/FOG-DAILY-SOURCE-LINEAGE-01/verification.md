---
id: FOG-DAILY-SOURCE-LINEAGE-01-VERIFICATION
status: VERIFIED_CANDIDATE_I5_BLOCKED
---

# Verification

## Red

Current main closed-regime `NO_EXECUTABLE_TOPIC` artifact沒有
`source_lineage.daily_source_date`，v3 receipt producer回
`DAILY_ARTIFACT_SCHEMA_REJECT`。

## Green

- 新 authority從 repo-contained features parquet獨立建立：
  - `features_path`
  - `features_sha256`
  - `daily_source_date`
- Producer與 verifier共用同一 module；verifier重讀 parquet並重算 hash/date。
- Hostile regressions涵蓋 path escape、hash drift、date drift、future-only與缺日期欄。
- No-work payload保留 source lineage，即使 `topic_runs=[]` 也不省略。

Live producer已成功輸出：

```json
{
  "schema_version": "fog-daily-source-lineage.v1",
  "features_path": "data/clean/features.parquet",
  "features_sha256": "057177ae3348c023ab2994ccc97a82a7228386b776e9ae65c35f2b22662d88af",
  "daily_source_date": "2026-07-27"
}
```

## Gates

- Targeted：`69 passed`
- Full suite：`576 passed, 4 warnings, 246 subtests passed`
- Live bounded probe：lineage gate已通過，但選到
  `strategy-matrix:artifacts-backtest-production_baseline_harness_smoke:long_horizon`
  後得到 `NO_COMPARISON_EVIDENCE`，daily run status `FAILED`。
- 三次 live probe停損已到；沒有第 4 次重試。
- Fog LaunchAgent保持 unloaded；retry circuit沒有直接刪除或旋轉。

## Remaining blocker

I5仍為 `NO_GO`。下一個 root question是該 closed-regime topic為何沒有 comparison
evidence，或提供不執行研究、但可證明 scheduler receipt wiring的正式 canary mode。
不得把 `NO_COMPARISON_EVIDENCE` 改成成功或繞過。

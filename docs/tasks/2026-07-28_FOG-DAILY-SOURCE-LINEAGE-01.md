---
id: FOG-DAILY-SOURCE-LINEAGE-01
status: VERIFIED_CANDIDATE_I5_BLOCKED
type: repair
---

# FOG-DAILY-SOURCE-LINEAGE-01

## Root question

Closed-regime daily run在 `NO_EXECUTABLE_TOPIC` 時，如何仍以 canonical features
產生可獨立重算的 `daily_source_date`，讓 v3 receipt fail closed但不誤擋合法
no-work scheduler round？

## RED

- Current main執行 closed-regime daily quota，inputs已正確宣告
  `closed_regime_research=true`，但 payload沒有 `source_lineage`。
- Receipt producer因此回
  `DAILY_ARTIFACT_SCHEMA_REJECT: 缺少、型別錯誤或互相衝突的 daily source lineage`。
- 不得用 `run_date`、regime `source_trade_date`或 host date補值。

## Contract

- Daily source lineage由 `args.features` 指向的 repo-contained parquet獨立建立。
- 欄位至少綁 `features_path`、`features_sha256`、`daily_source_date`。
- `daily_source_date` 是 features 中不晚於 `market_run_date` 的最大合法日期。
- Producer與 receipt verifier共用同一 authority module；verifier重讀 parquet、
  重算 hash/date，不信任 daily artifact自報值。
- Missing、path escape、hash drift、future-only、無日期欄皆 fail closed。
- `NO_EXECUTABLE_TOPIC`／空 `topic_runs` 是合法 no-work round，但 lineage不可省略。

## Exact allowlist

- 本卡
- `scripts/fog_daily_source_lineage.py`
- `scripts/run_autonomous_research.py`
- `scripts/verify_closed_regime_runtime.py`
- `tests/test_fog_daily_source_lineage.py`
- `tests/test_fog_closed_regime_runtime.py`
- `tests/test_regime_research_autonomy.py`
- `docs/evidence/FOG-DAILY-SOURCE-LINEAGE-01/**`

## Gates

- Red→green producer no-work regression。
- Verifier hostile cases：path/hash/date drift、future-only、missing date column。
- Current live bounded daily＋v3 receipt green。
- Targeted/full pytest、`git diff --check`、exact allowlist。
- 不修改 model、ranking、weights、baseline、promotion或 queue policy。

# GUARDED-TOP10-REPLAY-01A｜Candidate Pool Contract

## Root Question

`GUARDED-TOP10-REPLAY-01` 已能用既有 features 與現有模型重放 guarded Top10，但 CLI 仍允許調整 `--candidate-pool-size`。在進入 100 日 / 6 個月績效回測前，必須先鎖定候選池規格，避免同一套實驗因 TopN 漂移而得到不可比較的結果。

## Goal

把 guarded replay 的候選池固定為 `Top80` contract。

## Scope

- 更新 `scripts/replay_guarded_top10_policy.py`。
- 更新 `scripts/verify_guarded_top10_replay.py`。
- 允許新增 focused self-test 或 probe。
- 只處理 guarded replay contract，不做 performance backtest。

## Required Behavior

- `candidate_pool_size` 正式 contract 必須是 `80`。
- CLI 若保留 `--candidate-pool-size`，只能接受 `80`；`79`、`100` 等非 80 必須失敗。
- Artifact 的 `contract.candidate_pool_rule`、`inputs.candidate_pool_size`、`summary.candidate_pool_count` 必須一致。
- Verifier 必須拒絕非 Top80 artifact。
- 多日期 batch replay 也必須遵守同一個 Top80 contract。

## Out Of Scope

- 不改正式 `artifacts/ranking_YYYY-MM-DD.csv`。
- 不改 `models/latest_lgbm.pkl`。
- 不改 daily report / Clawd publish source。
- 不做 100 日或 6 個月績效比較。
- 不調整模型權重或 ranking score formula。

## Acceptance

必須通過：

```bash
.venv/bin/python scripts/replay_guarded_top10_policy.py --date 2026-06-08 --candidate-pool-size 80
.venv/bin/python scripts/verify_guarded_top10_replay.py --artifact artifacts/research/guarded_top10_replay_2026-06-08.json
.venv/bin/python -m py_compile scripts/replay_guarded_top10_policy.py scripts/verify_guarded_top10_replay.py
git diff --check
```

必須失敗：

```bash
.venv/bin/python scripts/replay_guarded_top10_policy.py --date 2026-06-08 --candidate-pool-size 79
.venv/bin/python scripts/replay_guarded_top10_policy.py --date 2026-06-08 --candidate-pool-size 100
```

## Evidence

- `artifacts/research/guarded_top10_replay_2026-06-08.json`
- `artifacts/research/guarded_top10_replay_2026-06-08.md`
- terminal output showing non-80 candidate pool rejection

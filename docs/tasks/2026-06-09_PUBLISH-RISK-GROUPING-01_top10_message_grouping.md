# PUBLISH-RISK-GROUPING-01｜Top10 推播分級與文案安全

## Root Question

`GUARDED-TOP10-REPLAY-02` 已證明 guarded Top10 不適合取代正式 Top10，但 tape / RR / chase guard 仍可用來避免推播把風險股寫成主攻股。這張卡只處理 publish/report 的呈現邊界。

## Goal

保留正式 Top10 排名，用 guard 欄位把推播拆成：

- `主攻觀察`
- `等確認`
- `只等拉回`
- `候補觀察`
- `風險警示`

## Scope

- 可保留 tape / RR 欄位在 ranking artifact 與 daily report 中，供後續解讀。
- Clawd publish message 可依 guard 欄位分組。
- 負向 tape 不得產生 `買盤累積`、`轉強`、`可觀察進場` 這類正向追價文案。
- `RankingPolicy.apply()` 預設不得套 selection guard；只有 research replay 明確傳 `apply_selection_guards=True` 才可用 guarded selection。

## Out Of Scope

- 不把 guarded Top10 切成正式 daily ranking。
- 不改 `models/latest_lgbm.pkl`。
- 不改 production ranking score 的 promotion gate。
- 不用這張卡調整 tape / RR 門檻。

## Acceptance

必須通過：

```bash
.venv/bin/python scripts/verify_daily_tape_and_rr_guard.py
.venv/bin/python scripts/build_clawd_publish_payload.py --date 2026-06-08 --channel discord --to channel:1507327845003825154
.venv/bin/python -m py_compile app/trading/tape_guard.py app/trading/ranking_policy.py scripts/build_clawd_publish_payload.py scripts/generate_daily_report.py scripts/verify_daily_tape_and_rr_guard.py
git diff --check
```

## Result｜2026-06-09

Status: `COMPLETED_WITH_ARTIFACT_CAVEAT`

Decision boundary:

- Formal daily ranking remains model/ranking-policy output without default guarded selection.
- Guarded selection remains research-only through explicit `apply_selection_guards=True`.
- Publish message can group existing Top10 into risk/action buckets.

Implementation result:

- `RankingPolicy.apply()` now defaults to `apply_selection_guards=False`.
- `GUARDED-TOP10-REPLAY` scripts explicitly pass `apply_selection_guards=True`.
- Daily report carries tape / RR fields when the ranking artifact contains them.
- Clawd publish message groups Top10 into primary / confirm / pullback / backup / risk sections.
- Publish verifier checks that tape/RR guarded names are not presented as primary bullish ideas.

Evidence:

- `artifacts/clawd_publish_payload_2026-06-08.json`
- `artifacts/clawd_publish_message_2026-06-08.md`

Observed behavior in rerun evidence:

- `1591 駿吉-KY` had `tape_guard_action=EXCLUDE` and was rendered under `風險警示`.
- Its message block says 一字跌停 is not an entry signal and does not present it as 主攻觀察.

Artifact caveat:

- The original `artifacts/ranking_2026-06-08.csv` did not contain tape / RR columns.
- Rebuilding 2026-06-08 with the current worktree produced a different Top10 than the older saved artifact, so the rerun is valid as forward-flow evidence, not as proof that the old 2026-06-08 list stayed unchanged.
- The code boundary is still explicit: publish grouping does not require guarded selection, and guarded selection is only enabled in research replay.

Validation run:

```bash
.venv/bin/python scripts/verify_publish_risk_grouping.py --date 2026-06-08
.venv/bin/python scripts/verify_daily_tape_and_rr_guard.py
.venv/bin/python -m py_compile app/trading/tape_guard.py app/trading/ranking_policy.py scripts/build_clawd_publish_payload.py scripts/generate_daily_report.py scripts/verify_daily_tape_and_rr_guard.py scripts/verify_publish_risk_grouping.py scripts/replay_guarded_top10_policy.py scripts/backtest_guarded_top10_performance.py
git diff --check
```

Validation status: `OK`

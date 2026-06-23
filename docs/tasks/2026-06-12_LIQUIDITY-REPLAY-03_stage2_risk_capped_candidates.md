# LIQUIDITY-REPLAY-03｜Stage2 Risk-Capped Liquidity Candidates

## Root Question

`LIQUIDITY-REPLAY-02` 已跑完 `144` 個 V2 active queue 組合。

結果中有一批 liquidity 組合能提高報酬，但部分是靠更高產業集中度或更差回撤換來，不能直接當 production 候選。

本卡目標是把有效組合分層：

- 報酬改善且風險沒有惡化：保留為下一輪 replay 候選。
- 報酬改善但集中度 / 回撤惡化：保留 shadow monitor，不升級。
- 沒有改善：淘汰並保留失敗原因。

## Input

- `artifacts/research_reviews/liquidity_replay_v2_batch_2026-06-12.json`
- `artifacts/research_map/research_fog_map_latest.json`

## Stage2 Gate

`STAGE2_RISK_CAPPED_CANDIDATE` 必須同時滿足：

```text
return_delta >= 0.02
drawdown_delta >= -0.005
concentration_delta <= 0.03
turnover_delta <= 0.05
```

其餘 positive-return 組合不得丟掉，但只能保留為 shadow / diagnostic。

## 禁止事項

- 不准改 production ranking。
- 不准改模型。
- 不准改 Clawd live push。
- 不准把 Stage2 candidate 宣稱 production-ready。
- 不准只看 return，不看 drawdown / concentration / turnover。

## Output

- `scripts/build_liquidity_replay_v2_stage2.py`
- `scripts/verify_liquidity_replay_v2_stage2.py`
- `artifacts/research_reviews/liquidity_replay_v2_stage2_YYYY-MM-DD.json`
- `artifacts/research_reviews/liquidity_replay_v2_stage2_YYYY-MM-DD.md`
- `artifacts/research_reviews/liquidity_replay_v2_stage2_verification_latest.json`

## 驗收

- source batch 必須是 `liquidity-replay-v2-batch.v1`。
- source batch 必須 `completed_count == 144` 且 `failed_count == 0`。
- Stage2 candidate 必須全部通過 gate。
- rejected / monitor rows 必須有 failure attribution。
- `production_impact == NO_PRODUCTION_CHANGE`。
- 報告不得包含 `PROMOTION_READY`。

## 2026-06-12 結果

狀態：`OK`

```text
source_rows: 144
source_effective_count: 78
stage2_candidate_count: 22
shadow_monitor_count: 56
rejected_count: 66
production_impact: NO_PRODUCTION_CHANGE
```

主要結論：

- 可進下一輪 replay 的乾淨訊號集中在 `group_exposure=none`、`entry_filter=LOG_GATE`。
- `group_exposure=0.55` 報酬 delta 較高，但 concentration delta 明顯偏高，保留 shadow monitor，不升級。
- 22 個 Stage2 candidates 已回寫 `run_history.jsonl`，星圖 active queue 會顯示為 `next_stage`。

驗證：

```text
.venv/bin/python scripts/build_liquidity_replay_v2_stage2.py --date 2026-06-12 --append-run-history：OK
.venv/bin/python scripts/verify_liquidity_replay_v2_stage2.py --date 2026-06-12：OK
bash scripts/refresh_research_map_from_history.sh：OK
git diff --check：OK
```

下一步：`LIQUIDITY-REPLAY-04` 只拿這 22 個 Stage2 candidates 做長窗 replay，不再重跑 144 全組合。

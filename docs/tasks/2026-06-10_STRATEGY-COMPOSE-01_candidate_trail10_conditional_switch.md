# STRATEGY-COMPOSE-01｜Candidate Ranking + Trail10 Conditional Switch

## Root Question

`candidate_ranking + trail10` 這組零件，能不能從「研究候選」變成一套可被每日推薦系統採用的條件式策略？

這張卡不是要再發明新模型，而是建立組裝台與測試台：

- 從 strategy component registry 讀取已分類零件。
- 只組合目前最有希望的候選：`candidate_ranking + trail10`。
- 用同一套資金、進場、出場、盤勢條件，和 production baseline 做公平比較。
- 給出明確結論：保留、條件採用、繼續 shadow、或淘汰。

## 請讀

- `docs/tasks/2026-06-10_STRATEGY-COMPONENT-REGISTRY-01_initial_registry.md`
- `scripts/build_strategy_component_registry.py`
- `scripts/verify_strategy_component_registry.py`
- `docs/tasks/2026-06-10_SHADOW-ROLLOUT-01_candidate_trail10_daily_monitor.md`
- `artifacts/model_experiments/long_candidate_validation_report_2026-06-10.json`
- `artifacts/model_experiments/candidate_trail10_retention_diagnostics_2026-06-10.json`

若 `strategy_component_registry_2026-06-10.json` 不存在，先執行：

```bash
.venv/bin/python scripts/build_strategy_component_registry.py --date 2026-06-10
.venv/bin/python scripts/verify_strategy_component_registry.py --artifact artifacts/model_experiments/strategy_component_registry_2026-06-10.json
```

## Scope

### A. 組合規則

建立 strategy composition artifact，至少包含：

- `production_baseline`
- `candidate_trail10_global`
- `candidate_trail10_big_bull_only`
- `candidate_trail10_regime_conditional`

每個策略必須明確記錄：

- ranking source
- entry rule
- exit rule
- capital rule
- regime gate
- sector / concentration rule
- message eligibility
- allowed production use
- blocked production use

### B. 回測規格

用既有歷史資料做 replay，不抓新資料、不重訓模型。

基本交易規格：

- 起始本金：`300_000 TWD`
- 可買零股。
- 每檔初始配置上限：`10% ~ 15%`，由回測腳本列成參數。
- 總持股曝險上限：`85% ~ 90%`，牛市不得保留過高現金。
- 每天依策略 Top10 產生可買清單。
- 進場：D+1 open。
- 最低持有天數：5 個交易日。
- 出場：
  - production baseline 用既有 production exit proxy。
  - candidate 策略用 `trail10`。
  - 若測 partial take-profit，必須是獨立 variant，不可混進主結論。
- 成本：
  - 手續費、證交稅、滑價沿用專案既有 backtest convention。

### C. 盤勢條件

盤勢條件只用當下或過去已知資料，不准開後照鏡。

必測：

- 全市場不分盤勢。
- BIG_BULL family。
- HIGH_CHOPPY rolling context。
- 非 BIG_BULL / 非 HIGH_CHOPPY。

輸出必須回答：

- candidate + trail10 是全市場有效，還是只在 BIG_BULL 有效？
- HIGH_CHOPPY 是加分、扣分，還是只能 monitor？
- 若近期輸 production，是否有可解釋的盤勢或風險條件？

### D. 切換判定

不得只用單一總報酬判斷。

至少比較：

- total return
- max drawdown
- risk-adjusted return
- turnover
- hit rate
- average holding days
- cash utilization
- sector concentration
- positive folds
- 最近 100 交易日
- 最近 6 個月
- 長區間

決策狀態只能是：

- `ADOPT_CONDITIONAL_SWITCH`
- `KEEP_SHADOW_MONITOR`
- `REJECT_COMPOSITION`
- `NEEDS_MORE_DATA_CONTRACT`

## Non-Goals

- 不改 `models/latest_lgbm.pkl`。
- 不改 production ranking。
- 不改 risk_adjusted_score。
- 不改 Clawd 推播。
- 不建立第二套 promotion gate。
- 不把 reference / diagnostic 零件直接當 alpha。
- 不把 `overlap_first` 重新包裝成正式排序。

## Expected Outputs

建議新增：

- `scripts/build_strategy_composition_replay.py`
- `scripts/verify_strategy_composition_replay.py`

建議輸出：

- `artifacts/model_experiments/strategy_composition_replay_YYYY-MM-DD.json`
- `artifacts/model_experiments/strategy_composition_replay_YYYY-MM-DD.md`
- `artifacts/model_experiments/strategy_composition_replay_verification_latest.json`

Artifact schema 至少包含：

- `schema_version`
- `contract`
- `inputs`
- `variants`
- `windows`
- `regime_slices`
- `capital_policy`
- `entry_exit_policy`
- `performance`
- `decision`
- `blocked_reasons`
- `next_recommended_action`

## Acceptance Criteria

1. Registry verifier 通過。
2. Replay artifact 明確列出每個策略 variant 的零件來源與 status。
3. 所有策略都使用相同資金、成本、進出場基準比較。
4. 不得使用未來資料決定當日是否切換。
5. 若 candidate 策略只在特定盤勢勝出，decision 必須是條件式，不可宣稱全域替換。
6. 若 recent_100 / recent_6m 明顯輸 production，必須列為 blocker 或限制條件。
7. Verifier 會擋：
   - `promotion_ready=true`
   - 改 production ranking
   - 改模型
   - 改 Clawd message
   - 使用 `overlap_first` 當正式排序
   - `REFERENCE_AVAILABLE` / `DIAGNOSTIC_ONLY` 零件直接進 alpha

## Verification

最少要跑：

```bash
.venv/bin/python -m py_compile scripts/build_strategy_composition_replay.py scripts/verify_strategy_composition_replay.py
.venv/bin/python scripts/build_strategy_component_registry.py --date 2026-06-10
.venv/bin/python scripts/verify_strategy_component_registry.py --artifact artifacts/model_experiments/strategy_component_registry_2026-06-10.json
.venv/bin/python scripts/build_strategy_composition_replay.py --date 2026-06-10
.venv/bin/python scripts/verify_strategy_composition_replay.py --artifact artifacts/model_experiments/strategy_composition_replay_2026-06-10.json
git diff --check
```

## Final Report Must Answer

請用白話回答：

1. 現在 production 比較好，還是 candidate + trail10 比較好？
2. 如果 candidate 比較好，是全市場都好，還是只在 BIG_BULL / 特定盤勢好？
3. HIGH_CHOPPY 對這套策略是加分、扣分，還是目前只能觀察？
4. 這套策略如果正式上線，會怎麼影響每日推播？
5. 還不能上線的話，卡在哪個 blocker？

## Dispatch Card

```text
任務ID：STRATEGY-COMPOSE-01
卡片類型｜派工對象：Strategy Composition Replay｜Codex
請讀：docs/tasks/2026-06-10_STRATEGY-COMPOSE-01_candidate_trail10_conditional_switch.md
任務目的：把 candidate_ranking + trail10 組成條件式策略，和 production baseline 做同資金/同成本/同進出場回測比較
證據路徑：artifacts/model_experiments/strategy_composition_replay_*.json、strategy_composition_replay_verification_latest.json
```

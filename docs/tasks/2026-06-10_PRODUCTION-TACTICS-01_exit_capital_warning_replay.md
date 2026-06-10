# PRODUCTION-TACTICS-01｜Production Ranking Exit / Capital / Warning Replay

## Root Question

既然 `candidate_ranking + trail10` 沒有證據能替換 production ranking，下一步要不要優先優化 production ranking 的操盤規則？

這張卡的目的不是換模型，也不是換 ranking source，而是回答：

- production ranking 挑股目前相對比較強，那怎麼買、怎麼抱、怎麼下車比較合理？
- exit rule、資金配置、warning policy 哪些零件能改善實際可操作性？
- 每日推播應該維持 Top10 推薦，還是拆出「推薦」與「風險提醒」兩條訊號？

## 背景結論

前置結論：

- `candidate_ranking + trail10` 不升正式、不進 promotion review。
- `candidate_ranking` 在 same-exit isolation 下沒有贏 production。
- `BIG_BULL gate` 目前沒有足夠正向證據能救 candidate ranking。
- `HIGH_CHOPPY` 樣本太少，只能 monitor，不能當正式策略 gate。

因此主線轉向：

```text
保留 production ranking，優先研究操盤規則：exit / capital / warning。
```

## 請讀

- `docs/tasks/2026-06-10_STRATEGY-COMPONENT-REGISTRY-01_initial_registry.md`
- `docs/tasks/2026-06-10_STRATEGY-COMPOSE-01_candidate_trail10_conditional_switch.md`
- `docs/tasks/2026-06-10_STRATEGY-COMPOSE-02_ranking_isolation_regime_normalization.md`
- `docs/tasks/2026-06-03_CAPITAL_EXIT_RULE_FRAMEWORK.md`
- `docs/tasks/2026-06-03_RANKING-QUALITY-06_stop_loss_execution_policy.md`
- `docs/tasks/2026-06-05_CAPITAL-REALISM-02_entry_exit_capital_matrix.md`
- `docs/tasks/2026-06-05_CAPITAL-REALISM-06_sizing_policy_matrix.md`

若 `STRATEGY-COMPOSE-02` 檔案或 artifact 不存在，請先不要猜；改用前置結論作為 input，並在 artifact 的 `input_gaps` 標示缺口。

## Scope

### A. 更新零件狀態

先產一份 registry update proposal，不直接改 production：

- `candidate_ranking`
  - 建議降級：`DIAGNOSTIC_ONLY` 或 `REJECTED_FOR_SWITCH`
  - 理由：same-exit 不贏 production，regime gate 也沒有救回來。
- `trail10`
  - 保留：`REUSABLE_CANDIDATE`
  - 理由：exit rule 還可能搭配 production ranking 測試。
- `BIG_BULL gate`
  - 保留：`NEEDS_TEST`
  - 不得用來救 candidate ranking。
- `HIGH_CHOPPY`
  - 保留：`MONITOR_ONLY`
  - 樣本不足，不進正式 gate。

### B. Production ranking 操盤規則回測

只用 production ranking 當 ranking source，測不同操作規則。

必測 variants：

1. `production_current_baseline`
2. `production_trail10_exit`
3. `production_hard_stop_then_trail10`
4. `production_partial_take_profit_runner`
5. `production_warning_only_no_forced_sell`

每個 variant 必須明確記錄：

- entry rule
- exit rule
- warning rule
- capital rule
- max position %
- max gross exposure %
- cash utilization
- average holding days
- turnover
- max drawdown
- total return
- risk-adjusted return

### C. 資金規格

這張卡必須用接近小白使用者的真實資金限制。

基本規格：

- 起始本金：`300_000 TWD`
- 可買零股。
- 單檔上限：
  - baseline：`10%`
  - aggressive：`12%`
  - max：`15%`
- 總曝險：
  - BIG_BULL / 強勢盤：`85% ~ 90%`
  - 震盪盤：`70% ~ 80%`
  - 風險盤：`50% ~ 65%`
- 不得使用「每天每檔買 100 股、資金無上限」當主結論。

### D. 出場與警告拆分

請把「推薦」與「警告」拆開測，不要混成同一件事。

推薦系統：

- 每日 Top10 只負責今日觀察清單。
- 不假設使用者一定昨天買、今天一定有持倉。

警告系統：

- 針對最近 N 天曾進 Top10 / 曾進推薦池的股票。
- 只輸出：
  - 未進場者不要追。
  - 已持有者要檢查持倉。
  - 跌破哪個區間代表走弱。
- 不輸出個人化賣出指令。

必測 warning lookback：

- 5 trading days
- 10 trading days
- 20 trading days

### E. 不開後照鏡

每日 replay 只能用當天或之前已知資料。

不得用後面才知道的最高價、最低價、未來 regime、未來入榜天數來決定當天是否買入或切換策略。

## Non-Goals

- 不改 `models/latest_lgbm.pkl`。
- 不改 production ranking score。
- 不改 Clawd live send。
- 不切正式推播。
- 不把 warning 當個人持倉賣出通知。
- 不重新救 `candidate_ranking`。
- 不用 `overlap_first` 當正式排序。

## Expected Outputs

建議新增：

- `scripts/build_production_tactics_replay.py`
- `scripts/verify_production_tactics_replay.py`

建議輸出：

- `artifacts/model_experiments/production_tactics_replay_YYYY-MM-DD.json`
- `artifacts/model_experiments/production_tactics_replay_YYYY-MM-DD.md`
- `artifacts/model_experiments/production_tactics_replay_verification_latest.json`

Artifact 至少包含：

- `schema_version`
- `contract`
- `inputs`
- `registry_update_proposal`
- `variants`
- `capital_policy`
- `entry_exit_policy`
- `warning_policy`
- `windows`
- `performance`
- `decision`
- `blocked_reasons`
- `next_recommended_action`

## Acceptance Criteria

1. production ranking source 不變。
2. 每個 variant 都用同一套資料窗口、成本、資金限制比較。
3. 回測支援零股，不得使用無限資金。
4. 推薦與警告分離。
5. warning 不產生個人持倉賣出指令。
6. `trail10` 可以被測，但不能因 candidate ranking 失敗而自動淘汰。
7. 若新 tactics 贏 production baseline，必須說明是：
   - exit 改善
   - capital 改善
   - warning 改善
   - 或只是 exposure 差異。
8. 若不能升正式，必須明確列出 blocker。

## Verification

最少要跑：

```bash
.venv/bin/python -m py_compile scripts/build_production_tactics_replay.py scripts/verify_production_tactics_replay.py
.venv/bin/python scripts/build_production_tactics_replay.py --date 2026-06-10
.venv/bin/python scripts/verify_production_tactics_replay.py --artifact artifacts/model_experiments/production_tactics_replay_2026-06-10.json
git diff --check
```

Verifier 必須擋：

- `promotion_ready=true`
- 改模型
- 改 production ranking score
- 改 Clawd live send
- warning 直接輸出個人化賣出指令
- 無限資金或固定 100 股無資金限制的主結論

## Final Report Must Answer

請用白話回答：

1. production ranking 現在最值得優化的是 exit、capital，還是 warning？
2. `trail10` 搭 production ranking 有沒有幫助？
3. 小本金 30 萬、可買零股下，策略是否仍可執行？
4. 推薦與警告要不要拆成兩條訊號？
5. 哪一個 variant 最值得進下一輪 shadow？
6. 這張卡有沒有任何理由改模型或改 ranking source？

## Dispatch Card

```text
任務ID：PRODUCTION-TACTICS-01
卡片類型｜派工對象：Production Ranking Tactics Replay｜Codex
請讀：docs/tasks/2026-06-10_PRODUCTION-TACTICS-01_exit_capital_warning_replay.md
任務目的：保留 production ranking，只測 exit / capital / warning policy 哪些能提升可操作性與風險控制
證據路徑：artifacts/model_experiments/production_tactics_replay_*.json、production_tactics_replay_verification_latest.json
```

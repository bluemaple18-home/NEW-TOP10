# PRODUCTION-TACTICS-02｜Production Trail10 Shadow Rollout

## Root Question

`production_trail10_exit` 在 PRODUCTION-TACTICS-01 回測中明顯改善報酬與回撤，下一步要怎麼安全接到每日流程旁邊觀察？

這張卡不是要直接改 live 推播，而是建立 shadow rollout：

- production ranking 照常產每日 Top10。
- 後台同時產生 trail10 shadow 持倉與出場狀態。
- 不改正式 ranking、不改 Clawd live message、不改模型。
- 每天留下可驗證 artifact，累積到可判斷是否進推播文案或頁面說明。

## 背景結論

PRODUCTION-TACTICS-01 結論：

- production ranking 不動。
- 最值得優化的是 exit，不是 capital 或 warning。
- `production_trail10_exit` 是下一輪 shadow variant。
- baseline return `66.86%`，max DD `-12.09%`。
- `production_trail10_exit` return `71.14%`，max DD `-5.74%`。
- `partial_take_profit_runner` 變差，先淘汰。
- p12 / p15 capital variants 幾乎沒改善，且回撤略差。

## 請讀

- `docs/tasks/2026-06-10_PRODUCTION-TACTICS-01_exit_capital_warning_replay.md`
- `scripts/build_production_tactics_replay.py`
- `scripts/verify_production_tactics_replay.py`
- `artifacts/model_experiments/production_tactics_replay_2026-06-10.json`
- `docs/tasks/2026-06-03_RANKING-QUALITY-06_stop_loss_execution_policy.md`
- `docs/tasks/2026-06-05_CAPITAL-REALISM-02_entry_exit_capital_matrix.md`
- `docs/tasks/2026-06-05_CAPITAL-REALISM-06_sizing_policy_matrix.md`
- `scripts/run_daily.sh`
- `scripts/run_daily_publish.sh`

若 PRODUCTION-TACTICS-01 的 script 或 artifact 尚未進 repo，請不要猜實作細節；先標 `input_gaps`，並只用任務卡摘要作為前置結論。

## Scope

### A. Shadow Artifact

新增 trail10 shadow artifact，不改正式產物：

- `artifacts/shadow/production_trail10/production_trail10_shadow_YYYY-MM-DD.json`
- `artifacts/shadow/production_trail10/production_trail10_shadow_YYYY-MM-DD.md`
- `artifacts/shadow/production_trail10/production_trail10_shadow_latest.json`

Artifact 至少包含：

- `schema_version`
- `run_date`
- `contract`
- `inputs`
- `production_top10`
- `shadow_positions`
- `shadow_events`
- `exit_policy`
- `capital_policy`
- `warning_candidates`
- `decision`
- `blocked_reasons`

### B. Shadow Position Model

建立非個人化 shadow position model：

- 假設觀察者每天依 production Top10 進入候選池。
- 不代表真實使用者持倉。
- 不輸出個人化買賣指令。
- 只追蹤「如果照 production Top10 + trail10 exit 規則，這檔目前狀態是什麼」。

狀態至少包含：

- `candidate_active`
- `min_hold_not_met`
- `hold`
- `trail_stop_zone`
- `exit_triggered`
- `expired_or_removed`

### C. Trail10 Rule

trail10 必須明確定義：

- 進場日：D+1 open proxy。
- 最低持有：5 trading days。
- trail high：只能用進場後到當日以前已知資料。
- trail threshold：自高點回落 10%。
- 若最低持有未滿，不得觸發正式 exit event，只能標 `min_hold_not_met`。

不得用未來最高價或未來低點決定當日狀態。

### D. Daily Integration

可以接進每日流程旁邊，但必須 default-off 或 shadow-only：

- `scripts/run_daily.sh` 可選擇呼叫 shadow builder。
- 若加環境變數，預設必須不影響既有 daily status。
- shadow 失敗不得讓正式 daily ranking / report / Clawd publish 失敗。
- 失敗要寫 artifact 或 log，不能靜默吞掉。

建議環境變數：

```bash
TOP10_ENABLE_PRODUCTION_TRAIL10_SHADOW=1
```

預設：

```bash
TOP10_ENABLE_PRODUCTION_TRAIL10_SHADOW=0
```

### E. 推播邊界

這張卡不改 Clawd live message。

允許產出 future payload preview，例如：

- 今日 Top10 仍照 production ranking。
- trail10 shadow 只出現在 artifact / md review。
- 若要未來放推播，只能先做 dry-run preview，不得 live send。

### F. Warning Separation

warning 不等於個人持倉賣出通知。

若產 warning candidates，只能描述：

- 這檔進入轉弱觀察區。
- 未進場者不要追。
- 已持有者自行檢查持倉。

不得輸出：

- 「你應該賣出」
- 「賣幾成」
- 「個人持倉停損」

## Non-Goals

- 不改 `models/latest_lgbm.pkl`。
- 不改 production ranking score。
- 不改正式 Clawd live message。
- 不切正式推播。
- 不做個人持倉管理。
- 不重新啟用 candidate ranking。
- 不測 partial take-profit runner。
- 不測 p12 / p15 capital variants。

## Expected Outputs

建議新增：

- `scripts/build_production_trail10_shadow.py`
- `scripts/verify_production_trail10_shadow.py`

若要接每日流程，請小心修改：

- `scripts/run_daily.sh`

建議輸出：

- `artifacts/shadow/production_trail10/production_trail10_shadow_YYYY-MM-DD.json`
- `artifacts/shadow/production_trail10/production_trail10_shadow_YYYY-MM-DD.md`
- `artifacts/shadow/production_trail10/production_trail10_shadow_verification_latest.json`

## Acceptance Criteria

1. production ranking source 不變。
2. Clawd live message 不變。
3. shadow artifact 可重跑、可驗證。
4. trail10 狀態不得使用未來資料。
5. 最低持有 5 日之前不能觸發 exit。
6. shadow 失敗不阻斷 daily 主流程。
7. artifact 明確標示這不是個人持倉建議。
8. verifier 會擋：
   - `changes_production_ranking=true`
   - `changes_clawd_live_message=true`
   - `changes_model=true`
   - `personalized_sell_instruction=true`
   - 使用未來資料決定 exit

## Verification

最少要跑：

```bash
.venv/bin/python -m py_compile scripts/build_production_trail10_shadow.py scripts/verify_production_trail10_shadow.py
.venv/bin/python scripts/build_production_trail10_shadow.py --date 2026-06-10
.venv/bin/python scripts/verify_production_trail10_shadow.py --artifact artifacts/shadow/production_trail10/production_trail10_shadow_2026-06-10.json
git diff --check
```

若修改 `scripts/run_daily.sh`，還要跑：

```bash
bash -n scripts/run_daily.sh
TOP10_ENABLE_PRODUCTION_TRAIL10_SHADOW=0 bash scripts/run_daily.sh
TOP10_ENABLE_PRODUCTION_TRAIL10_SHADOW=1 bash scripts/run_daily.sh
```

若當日資料不足或不適合實跑 daily，可用既有 artifact 做 fixture/smoke，但必須在結果中標示沒有 live daily replay。

## Final Report Must Answer

請用白話回答：

1. trail10 shadow 今天有產出嗎？
2. 它有沒有改正式 Top10 或正式推播？
3. 今天有哪些股票在 `hold`、`trail_stop_zone`、`exit_triggered`？
4. 這些狀態是否只是非個人化觀察，不是賣出指令？
5. shadow 失敗時 daily 主流程會不會被擋？
6. 下一步要不要把 trail10 狀態放到頁面或推播 dry-run？

## Dispatch Card

```text
任務ID：PRODUCTION-TACTICS-02
卡片類型｜派工對象：Production Trail10 Shadow Rollout｜Codex
請讀：docs/tasks/2026-06-10_PRODUCTION-TACTICS-02_trail10_shadow_rollout.md
任務目的：把 production_trail10_exit 接到每日流程旁邊做 shadow artifact，不改正式排名、不改 live 推播
證據路徑：artifacts/shadow/production_trail10/production_trail10_shadow_*.json、production_trail10_shadow_verification_latest.json
```

# 2026-06-12 Incident｜Daily Publish 連續漏推與 stale-send 風險

## 摘要

這是 NEW-TOP10 的重大營運失誤。

模型與研究流程模組化後，daily publish 連續兩天沒有穩定完成推播；其中 2026-06-11 的正式排程失敗，後續人工處理時又一度把 2026-06-10 訊息當作可補送候選，暴露出 stale live send 防線不足。

本事故不是單純「外部 API 慢」或「網路 timeout」，而是 daily publish 工作流缺少一鍵驗證與日期一致性硬 gate，導致問題被發現時需要靠人工追 log 才能判斷。

## 影響

- 2026-06-11 收盤後自動推播沒有準時送出。
- 使用者需要主動詢問「今日推播去哪了」，系統沒有主動 fail-loud。
- 曾出現人工補救時誤送舊日訊息的風險。
- 使用者對 daily publish 穩定性與專案治理信任下降。

## 時間線

- 2026-06-10：daily 產出後未正常 live send；流程語意與 gate 不夠清楚。
- 2026-06-11 17:30：launchd 觸發 daily publish，但 `uv` 在抓 `tzdata` 時 timeout，daily 失敗，未推播。
- 2026-06-12 凌晨：人工補跑時發現 launchd / non-login shell 環境下 `python` 指令不可用。
- 2026-06-12 凌晨：修正 runtime 後，外部資料抓取在 sandbox 內 DNS/網路失敗；改用外部授權補跑。
- 2026-06-12 03:00：2026-06-11 資料、ranking、daily report、Clawd payload/message 產出完成並補送成功。

## 根因

### 1. Runtime 依賴不穩

`scripts/run_daily.sh` 原本依賴 `uv run --with-requirements ...`。在 launchd / non-login shell 與網路不穩時，可能因套件 metadata / wheel 下載 timeout 導致 daily 主流程失敗。

修正：`scripts/run_daily.sh` 優先使用 repo `.venv/bin/python`，只在沒有 `.venv` 時才 fallback 到 `uv run --with-requirements ...`。

### 2. 模組化後內部 command 還殘留裸 `python`

`scripts/run_automation.py` 的部分子流程以 `["python", ...]` 呼叫下游腳本。launchd 環境 PATH 很短，沒有保證 `python` 存在。

修正：`run_automation.py` 會把 command 開頭的 `python` 正規化成 `sys.executable`。

### 3. 推播工作流沒有獨立 verifier

過去可以驗 ETL、validate、ranking，但沒有一支專門檢查 daily publish 的工具確認：

- launchd 是否指向正確入口
- daily status 是否 OK
- ranking / report / payload / message 日期是否一致
- send status 是否是 live OK
- stale message 是否會被擋

修正：新增 `scripts/verify_daily_publish_workflow.py`。

### 4. stale live send 防線不足

人工補救時，曾把最新存在的舊日訊息視為可送候選。這違反 daily publish 的日期一致性原則。

修正：`scripts/send_clawd_publish_message.py` 預設擋掉非今日 live send；只有明確人工 catch-up 才能加 `--allow-stale-send`。

## 已完成修補

- `scripts/run_daily.sh`
  - 優先使用 `.venv/bin/python`
  - 保留 uv fallback
  - 日誌列出實際 runtime
- `scripts/run_automation.py`
  - 子命令裸 `python` 改用 `sys.executable`
  - 支援明確 `--run-date`，避免 catch-up 被本機今日覆蓋
- `scripts/run_daily_publish.sh`
  - 支援 `TOP10_RUN_DATE` 明確 catch-up
  - 不 fallback 到 latest message
  - catch-up 時才傳 `--allow-stale-send`
  - Clawd live send 失敗時以非 0 結束
- `scripts/send_clawd_publish_message.py`
  - 新增 stale live send guard
  - 非今日訊息 live send 預設 blocked
- `scripts/verify_daily_publish_workflow.py`
  - 新增 daily publish 工作流 verifier
  - 可檢查 artifacts、send status、launchd、stale guard
- `scripts/verify_daily_publish_wrapper_guards.py`
  - 不送真訊息，驗證 send failed 會非 0、catch-up date 會傳到 sender
- `docs/AUTOMATION.md`
  - 補上 daily publish verifier 與檢查口徑

## 驗證紀錄

2026-06-11 補送後已驗：

```text
.venv/bin/python scripts/verify_daily_publish_workflow.py --date 2026-06-11 --require-send --check-launchd
DAILY_PUBLISH_WORKFLOW_OK
```

補送結果：

```text
message_date: 2026-06-11
status: OK
dry_run: false
send_attempted: true
target: channel:1507327845003825154
messageId: 1514705940740313279
Top1: 6830 汎銓
```

資料狀態：

```text
features latest: 2026-06-11
universe latest: 2026-06-11
pipeline validate: OK
```

## 新鐵則

1. Daily publish 不准用舊日期訊息當今日訊息補送。
2. 若當日資料抓不到，寧可 fail-loud 或送失敗告警，不准偷送前一交易日推薦。
3. 任何 catch-up 必須明確指定 `TOP10_RUN_DATE=YYYY-MM-DD`，且 send path 必須留下 `clawd_send_status_YYYY-MM-DD.json`。
4. Clawd live send 失敗時，publish wrapper 必須非 0，不能讓外層排程誤判成功。
5. 每次 daily publish 事故後，第一個檢查指令是：

```bash
.venv/bin/python scripts/verify_daily_publish_workflow.py --date YYYY-MM-DD --require-send --check-launchd
.venv/bin/python scripts/verify_daily_publish_wrapper_guards.py
```

6. 模組化新增腳本後，不能只驗單一模組；必須驗 daily publish 端到端 artifact chain。

## 剩餘風險

- 外部資料源或網路仍可能失敗，這不是程式能完全消除的風險。
- 目前的修正能保證「失敗時不亂送舊訊息」，不能保證「外部 API 永遠可用」。
- launchd 的 `LastExitStatus` 會保留上一次排程失敗紀錄，需等下一次正式排程成功後才會自然覆蓋。

## 後續建議

- 增加 daily failure notification：當 daily 失敗時，送出「今日資料未完成，不提供推薦」的營運告警，而不是沉默。
- 將 `verify_daily_publish_workflow.py --require-send --check-launchd` 納入每日人工巡檢或 17:30 後健康檢查。
- 針對外部資料抓取建立 degraded mode policy，但不得降低日期一致性要求。

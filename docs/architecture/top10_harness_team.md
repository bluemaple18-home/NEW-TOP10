# TOP10 穩固版 Harness Team 架構

本文件定義 TOP10 專案的穩固版 12 隻邏輯機器人。重點不是把每張流程卡都拆成一隻，而是把責任邊界、可驗證輸出、失敗回報與 dashboard 監控欄位固定下來。

## 核心原則

- 每一次完整 daily loop 都使用同一個 `run_id`、`run_date`、狀態、artifact 路徑與結論；daily、publish、external review 都寫回同一個 run。
- 報牌頻道只收通過 gate 的 Top10，不收 debug、卡關、研究過程。
- 工作進度頻道收 stop/fail、warning、外部 AI review 差異、next actions、下一輪 blocker。
- 任何 agent 失敗都不能假裝完成；必須產生 Stop Event 或明確的 degraded 狀態。
- 外部 AI review 只產生研究與風險提示，不能直接改 ranking/model。

## 兩個 Discord 頻道

| 頻道 | 寫入者 | 內容 | 禁止內容 |
| --- | --- | --- | --- |
| 報牌頻道 | Daily Push Bot | 每日 Top10、推薦理由、風險摘要、`run_id` | debug log、研究假說、外部 review 草稿 |
| 工作進度頻道 | Ops Reporter Bot | 成功/失敗狀態、卡關原因、外部 AI 反對點、後續動作、下一輪 blocker | 未通過 gate 的報牌名單 |

## 12 隻機器人

| # | Agent | 責任 | 輸入 | 輸出 | 失敗處理 |
| --- | --- | --- | --- | --- | --- |
| 1 | Harness Runner | 啟動 daily loop、建立 `run_id`、控管 lock/retry/timeout | 排程、手動觸發、前輪 blocker | run manifest、狀態事件 | 重複執行或 timeout 時 stop |
| 2 | Preflight Bot | 檢查交易日、API、設定、前輪 blocker | run manifest、設定、外部服務狀態 | preflight result | 不通過就送 Stop Event |
| 3 | Data ETL Bot | 抓 TWSE/TPEX、籌碼、基本面 | preflight OK、資料來源設定 | daily data snapshot | 抓取失敗或日期不符就 stop |
| 4 | Data Quality Gate Bot | 檢查日期、筆數、缺值、覆蓋率、股票池完整性 | daily data snapshot | quality gate result | 資料不可信就 stop |
| 5 | Ranking Bot | 產生 Top10、分數、推薦理由、feature snapshot | quality OK data | ranking result | ranking artifact 缺失就 stop |
| 6 | Anomaly / Circuit Breaker Bot | 檢查排名劇烈變動、baseline 偏離、不可解釋異常 | ranking result、baseline | anomaly decision | 可 stop/degrade/quarantine |
| 7 | Daily Push Bot | 推送通過 gate 的 Top10 到報牌頻道 | anomaly OK ranking | publish message、send receipt | 發送失敗不能算 daily 完成 |
| 8 | Outcome Tracker Bot | 追蹤命中率、報酬、誤報、人工標記 | publish result、後驗資料 | outcome artifact、fog signals | outcome 缺資料標為 pending |
| 9 | External Review Harness Bot | daily OK 後包 review packet，啟動外部 review | ranking/publish artifacts | verified packet、host runner status | daily 未 OK 就 skipped |
| 10 | AI Review Adapter Bot | 分別送 ChatGPT/Gemini，收回標準格式 | verified packet | provider responses | 單一 provider 失敗可 partial |
| 11 | Disagreement / Next Actions Bot | 找出外部 AI 跟我們完全相反之處，產生處置 | external review summary | disagreement report、next actions | 需要人工判斷就標 human_review |
| 12 | Ops Reporter Bot | 回報工作進度頻道，產生下一輪 blocker | stop events、next actions、status | ops message、blocker list | 發送失敗要留下本地 artifact |

## 主流程

```text
Harness Runner
 -> Preflight Bot
 -> Data ETL Bot
 -> Data Quality Gate Bot
 -> Ranking Bot
 -> Anomaly / Circuit Breaker Bot
 -> Daily Push Bot
 -> 報牌頻道
 -> Outcome Tracker Bot
 -> External Review Harness Bot
 -> AI Review Adapter Bot
 -> Disagreement / Next Actions Bot
 -> Ops Reporter Bot
 -> 工作進度頻道
 -> 下一輪 Harness Runner
```

## 研究回圈

研究線不是每日固定自嗨跑報表，而是由事件觸發：

- Outcome Tracker 發現命中率、報酬或誤報有後驗落差。
- Disagreement / Next Actions Bot 發現 ChatGPT 或 Gemini 明確反對我們的 Top10 結果。
- Circuit Breaker 發現 ranking 異常但不能立即解釋。

研究回圈：

```text
Fog Map
 -> Research Card
 -> Experiment
 -> Validation
 -> Decision
 -> Merge Policy
 -> Evidence Ledger
 -> Ranking Bot
```

只有 `Decision=accept` 且 Evidence Ledger 完整時，研究結果才可以回到 Ranking Bot。`reject/quarantine/needs_more_data` 都不能直接改 ranking。

## Dashboard 狀態模型

Dashboard 至少要顯示下列資訊：

| 欄位 | 說明 |
| --- | --- |
| `run_id` | 單次執行唯一 ID |
| `run_date` | 交易日或執行日期 |
| `agent_id` | 12 隻 agent 的固定 ID |
| `status` | `pending/running/ok/warning/degraded/skipped/failed/blocked` |
| `started_at` / `finished_at` | 執行時間 |
| `duration_seconds` | 執行耗時 |
| `artifact_paths` | 產出或驗證過的 artifact |
| `input_refs` | 讀取的上游 artifact |
| `decision` | gate 結論，例如 `pass/stop/degrade/quarantine/partial` |
| `failure_reason` | 失敗或 skipped 原因 |
| `next_action` | 下一步要做什麼 |
| `discord_channel` | `daily_pick_channel` 或 `ops_progress_channel` |

儀表板正式任務資料使用同一個 rollup 的兩個欄位：

| 欄位 | 說明 |
| --- | --- |
| `formal_tasks` | 12 個固定任務節點，含 `task_id`、`agent_id`、責任、輸入/輸出、status、next_action、artifact_paths |
| `flow_edges` | 流程圖連線狀態，含 `from`、`to`、`source_kind`、`target_kind`、`connected`、`edge_status` |

監控儀表板應優先讀 `/api/monitoring/top10-harness`，用 `formal_tasks` 畫任務表/卡片，用 `flow_edges` 畫流程線；不要自行從檔名或 agent index 推導。

## Status Event 落點

每隻 agent 的最新狀態事件使用 `top10-agent-status-event.v1`：

```text
artifacts/harness_status/<run_date>/<run_id>/events/<agent_id>.json
artifacts/harness_status/<run_date>/<run_id>/events.jsonl
artifacts/harness_status/<run_date>/<run_id>/rollup.json
artifacts/harness_status/<run_date>/latest_rollup.json
```

共用工具：

```text
scripts/top10_agent_status.py
scripts/record_top10_daily_status_events.py
scripts/record_top10_publish_event.py
scripts/build_top10_ops_progress_message.py
scripts/send_top10_ops_report.py
scripts/verify_top10_agent_status_event.py
scripts/build_top10_agent_status_rollup.py
```

`run_id` 預設為 `daily-<run_date>`。`scripts/run_daily.sh` 會把 `artifacts/automation_status.json` 轉成 daily lane 的 agent events；`scripts/run_daily_publish.sh` 只補 `daily_push` 的報牌頻道事件；`scripts/run_external_review_host_runner.py` 預設也寫入同一個 `daily-<run_date>`，讓 GPT/Gemini 驗證支線能接回同一張 rollup。

Ops Reporter 使用 `scripts/build_top10_ops_progress_message.py` 產生 `artifacts/ops_progress_message_<run_date>.md`，再由 `scripts/send_top10_ops_report.py --send` 送到 `notify.ops_clawd_to`。報牌頻道維持 `notify.clawd_to`；工作進度頻道使用 `notify.ops_clawd_to`，兩者不得共用訊息內容。

事件中的 `input_refs` 與 `artifact_paths` 必須是 repo-relative 或 artifacts-root-relative 路徑，不可寫入 `/Users/...`、`/private/...` 等本機絕對路徑。

## Stop Event 條件

下列情況不能繼續報牌：

- 非交易日但流程被觸發，且沒有明確允許補跑。
- API 或資料來源失敗，無法產生可信 snapshot。
- data snapshot 日期不對、筆數明顯不足、缺值/覆蓋率超過門檻。
- ranking artifact 缺少 Top10、分數、推薦理由或 feature snapshot。
- anomaly/circuit breaker 判定異常不可解釋。
- Daily Push Bot 沒有可驗證的 send receipt。

## 既有 repo 對應

| 架構位置 | 目前可對應的 repo 元件 |
| --- | --- |
| Daily publish | `scripts/run_daily_publish.sh`、`scripts/run_daily.sh` |
| Daily status | `artifacts/automation_status.json` |
| External Review Harness | `scripts/run_external_review_host_runner.py` |
| Review packet | `scripts/build_external_review_packet.py`、`scripts/verify_external_review_packet.py` |
| ChatGPT/Gemini adapter | `scripts/review_chatgpt_chrome.sh`、`scripts/review_gemini_chrome.sh` |
| External review summary | `scripts/build_external_review_summary.py`、`scripts/verify_external_review_summary.py` |
| Monitoring API | `app/services/monitoring_service.py`、`app/api/routers/monitoring.py` |
| Visual flow | `web/harness-loop.html` |

## 下一步落地順序

1. 固定 dashboard manifest：`docs/architecture/top10_harness_team.dashboard.json`。
2. 讓每個 runner 寫出同一格式的 agent status event。
3. 新增工作進度頻道 webhook 設定，與原本報牌頻道分離。
4. Ops Reporter 先讀本地 status/summary artifact，再推送到工作進度頻道。
5. Dashboard 讀取 status event，顯示每日 run 的 12 agent 狀態與卡關點。

# TOP10 穩固版 Harness Team 架構

本文件定義 TOP10 專案的穩固版 15 隻邏輯機器人。重點不是把每張流程卡都拆成一隻，而是把責任邊界、可驗證輸出、失敗回報與 dashboard 監控欄位固定下來。

## 核心原則

- 每一次完整 daily loop 都使用同一個 `run_id`、`run_date`、狀態、artifact 路徑與結論；daily、publish、external review 都寫回同一個 run。
- 報牌頻道只收通過 gate 的 Top10，不收 debug、卡關、研究過程。
- 工作進度頻道收 stop/fail、warning、外部 AI review 差異、next actions、下一輪 blocker。
- 任何 agent 失敗都不能假裝完成；必須產生 Stop Event 或明確的 degraded 狀態。
- 外部 AI review、迷霧地圖與研究 worker 只產生研究證據、風險提示與下一輪 blocker，不能直接改 ranking/model。

## 兩個 Discord 頻道

| 頻道 | 寫入者 | 內容 | 禁止內容 |
| --- | --- | --- | --- |
| 報牌頻道 | Daily Push Bot | 每日 Top10、推薦理由、風險摘要、`run_id` | debug log、研究假說、外部 review 草稿 |
| 工作進度頻道 | Ops Reporter Bot | 成功/失敗狀態、卡關原因、外部 AI 反對點、後續動作、下一輪 blocker | 未通過 gate 的報牌名單 |

## 15 隻機器人

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
| 10 | AI Review Adapter Bot | 以固定 browser conversation 分別送 ChatGPT/Gemini 並收回標準格式；官方 API 只作明確切換備援 | verified packet | provider responses | 單一 provider 失敗可 partial；全 provider 失敗就 fail-loud |
| 11 | Disagreement / Next Actions Bot | 找出外部 AI 跟我們完全相反之處，產生處置 | external review summary | disagreement report、next actions | 需要人工判斷就標 human_review |
| 12 | Fog Map Bot | 維護研究迷霧，挑下一輪研究隊列，吸收研究 worker 結果 | outcome artifact、external review summary、research cards、run history | research queue handoff、research fog map、map html、候選策略隊列、研究團隊 Console、證據閘門、需要決策區 | 迷霧刷新或驗證失敗就 fail-loud，交給 ops |
| 13 | Autonomous Research Worker Bot | 依 Fog Map queue 跑每日研究 quota | research queue、manager state、external review summary | daily research quota、run history、research evidence | 研究 quota 或驗證失敗就 stop，不改 ranking |
| 14 | PM Research Harness Bot | 只消費 PM 核准的 TOP10_STOCK 研究卡，驅動下一輪受控研究；queue 低水位時從 active topic bank 補 research-only 候選題 | PM decision state、PM review cards、manager state、active topic bank | approved work queue、research cards、PM harness status、topic discovery artifact | launchd 明確啟用研究；未核准不產新卡、不送 Discord |
| 15 | Ops Reporter Bot | 回報工作進度頻道，產生下一輪 blocker | stop events、next actions、status、research fog map、research quota、PM harness status | ops message、blocker list | 發送失敗要留下本地 artifact |

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
 -> Fog Map Bot
 -> Autonomous Research Worker Bot
 -> Fog Map Bot
 -> Ops Reporter Bot
 -> 工作進度頻道
 -> PM approval
 -> PM Research Harness Bot
 -> Autonomous Research Worker Bot
 -> 下一輪 Harness Runner
```

## 10 個 Owner Bot 與 15 個 Formal Agent 的翻譯層

`web/harness-loop.html` 畫的是 owner bot，`docs/architecture/top10_harness_team.dashboard.json` 監控的是 15 個 formal agent。兩者不是兩套流程；owner bot 是換手、lock、失敗邊界，formal agent 是 dashboard/event contract 的可觀測節點。

| Owner Bot | 包含的 formal agent | 換手邊界 |
| --- | --- | --- |
| Harness Runner | `harness_runner` | 建立 `run_id`、鎖定同一輪 daily loop |
| Daily Pipeline Bot | `preflight`、`data_etl`、`data_quality_gate` | 資料可信才交給 Ranking Bot |
| Ranking Bot | `ranking`、`anomaly_circuit_breaker` | 排名與異常 gate 一起決定可否 publish |
| Daily Push Bot | `daily_push` | 只把通過 gate 的 Top10 寫到報牌頻道 |
| Outcome Tracker Bot | `outcome_tracker` | 後驗資料成熟時回流 fog signals |
| External Review Bot | `external_review_harness`、`ai_review_adapter`、`disagreement_next_actions` | daily OK 後才包 packet，外部 AI 結果只能變成 disagreement / next actions |
| Fog Map Bot | `fog_map` | 維護研究地圖、queue、linkage 狀態；`linkage_ok` 不等於 replay drain running |
| Research Worker Bot | `research_worker` | 唯一可宣告 research quota / representative replay drain progress 的 owner |
| PM Research Harness Bot | `pm_research_harness` | PM 核准卡、approved work queue、下一輪研究卡與 PM harness status |
| Ops Reporter Bot | `ops_reporter` | 工作進度頻道、blocker、下一輪 handoff |

## 研究回圈

研究線不是每日固定自嗨跑報表，也不是另一套排程；它是 harness 的交接支線，由事件觸發：

- Outcome Tracker 發現命中率、報酬或誤報有後驗落差，交給 Fog Map Bot 變成地圖訊號。
- Disagreement / Next Actions Bot 發現 ChatGPT 或 Gemini 明確反對我們的 Top10 結果，交給 Fog Map Bot 變成研究卡與下一輪 blocker。
- Circuit Breaker 發現 ranking 異常但不能立即解釋，交給 Ops Reporter 與 Fog Map Bot 留下 stop/degrade 線索。
- Fog Map Bot 每輪把最高價值的未知區丟給 Autonomous Research Worker Bot 跑研究 quota；worker 完成後回填 run history，Fog Map Bot 再刷新地圖。地圖主星圖只呈現完成度與星星點亮，同頁底部呈現候選策略隊列、研究團隊 Console、證據閘門與需要 PM 決策的事項。
- PM Research Harness Bot 只在 PM 明確核准 TOP10_STOCK review card 後，才把核准項目轉成研究 queue 並驅動既有 research runner；正式 launchd 會明確帶 enable env 讓它持續跑研究。若既有 loop 已啟用且 queue 低於 12，會先產生 active topic bank；題目一進 queue 或完成後就不再留在 active bank，完成紀錄只留在 registry/history。

研究回圈：

```text
Fog Map
 -> Autonomous Research Worker
 -> Fog Map
 -> Research Card
 -> Experiment
 -> Validation
 -> Decision
 -> Merge Policy
 -> Evidence Ledger
 -> Ranking Bot
```

只有 `Decision=accept` 且 Evidence Ledger 完整時，研究結果才可以回到 Ranking Bot。`reject/quarantine/needs_more_data` 都不能直接改 ranking。

## 事件來源表

每個 formal agent 都必須能追到「誰寫 event、吃哪個 artifact、缺 event 時算正常等待還是異常」。目前 daily automation status 只會由 `scripts/record_top10_daily_status_events.py` 轉出 daily lane 的 8 個 event；publish、external review、fog map、research worker 與 ops send 由其他 script 補齊。

| Formal agent | Event writer | 主要來源 artifact | 正常 pending / skipped | 異常 pending / missing |
| --- | --- | --- | --- | --- |
| `harness_runner` | `scripts/record_top10_daily_status_events.py` | `artifacts/automation_status.json` | 非交易日或 dry-run 被明確標 `skipped` | daily run 已觸發但沒有 automation status |
| `preflight` | `scripts/record_top10_daily_status_events.py` | `artifacts/automation_status.json` steps | trading-day gate 明確 skipped | daily 已跑但 preflight steps 缺失 |
| `data_etl` | `scripts/record_top10_daily_status_events.py` | automation status、dataset artifacts | 上游 preflight skipped | preflight OK 但 ETL step / snapshot 缺失 |
| `data_quality_gate` | `scripts/record_top10_daily_status_events.py` | automation status、dataset artifacts | 上游 ETL skipped/failed | ETL OK 但 quality gate 缺失 |
| `ranking` | `scripts/record_top10_daily_status_events.py` | `ranking_artifact` / `expected_ranking_artifact` | 上游 quality gate 未通過 | quality OK 但 ranking artifact 缺失 |
| `anomaly_circuit_breaker` | `scripts/record_top10_daily_status_events.py` | `decision_quality_artifact` | ranking 被 stop/skipped | ranking OK 但 anomaly/circuit evidence 缺失 |
| `daily_push` | `scripts/record_top10_publish_event.py` via `scripts/run_daily_publish.sh` | publish message、send receipt、automation status | daily 未通過 gate 時 `skipped` | anomaly OK 但沒有 publish event 或 send receipt |
| `outcome_tracker` | `scripts/record_top10_daily_status_events.py` | market context、candidate persistence、weekly snapshot | 後驗尚未成熟時 `skipped/not_applicable` | 已有 send receipt 且應追蹤，但 outcome artifact 長期缺失 |
| `external_review_harness` | `scripts/run_external_review_host_runner.py` | host runner status、review packet | daily 未 OK 時 `skipped` | daily OK 但 packet/host status 缺失 |
| `ai_review_adapter` | `scripts/run_external_review_host_runner.py` | ChatGPT/Gemini raw/normalized responses | 單一 provider skipped/failed 時 `degraded/partial` | 全 provider 失敗或缺 adapter event |
| `disagreement_next_actions` | `scripts/run_external_review_host_runner.py` | `external_review_summary_{run_date}.json` | `needs_human_review` 可為 `warning` | summary verify failed 或 daily OK 後沒有 disagreement event |
| `fog_map` | `scripts/run_top10_fog_map_handoff.py` | research campaign progress、fog map、verification | external review 被 skip 時可 `skipped` | review/outcome signal 已到但 fog map event 缺失 |
| `research_worker` | `scripts/run_top10_fog_map_handoff.py` | daily quota artifact、verification、run history | `TOP10_SKIP_RESEARCH_QUOTA=1` 或 queue 空時 `skipped` | queue 存在但 quota/replay event 缺失 |
| `pm_research_harness` | `scripts/run_pm_research_harness_loop.py` | PM harness status、approved work queue、research cards | wrapper 未 enable、無 PM 核准且延續上限已到、或 research runner lock active | PM 核准卡存在且 launchd 啟用，但 PM harness status 缺失 |
| `ops_reporter` | `scripts/record_top10_daily_status_events.py`、`scripts/send_top10_ops_report.py` | rollup、ops progress message | 只建本地 artifact 尚未送出可 `warning` | stop/degraded 但沒有 ops event 或本地 message |

## Pending、Skipped 與 Missing 語意

`pending` 不是永遠等於錯，但必須有上游語意。Dashboard 可以先把缺 event 的 formal agent 顯示為 pending；判斷是否 degraded 要看該 agent 在本輪是否應該被觸發。

| 狀態 | 正常情況 | 需要注意 / 異常 |
| --- | --- | --- |
| `pending` | 上游尚未交接、後驗尚未成熟、外部 review 尚未到排程時間 | 上游已 `ok/pass` 且該 agent 應跑，卻沒有 event |
| `skipped` | 非交易日、daily 未 OK、明確 flag 跳過研究 quota、queue 空 | 用 skipped 掩蓋應跑未跑，且沒有 `failure_reason` / `next_action` |
| `warning` | partial provider、needs human review、ops send pending 但本地 artifact 存在 | warning 仍嘗試改 ranking/model |
| `degraded` | 單一非核心支線失敗，但 daily artifact 仍可追溯 | degraded 卻沒有 blocker 或下一步 |
| `failed` / `blocked` | 核心資料、ranking、publish receipt、packet verify、fog verify 或 quota verify 失敗 | 任何 failed/blocked 都不得假裝完整成功 |

## Status 對 Publish / Review / Research 的影響

| 上游狀態 | 報牌頻道 publish | External review | Fog map / research | Ops progress |
| --- | --- | --- | --- | --- |
| `ok/pass` | 可以 publish | 可以接手 | 可以接收 signals | 可回報成功摘要 |
| `warning` | 只有 warning 不影響 ranking gate 時才可 publish，且 message 要保留風險摘要 | 可以，但 summary 要標 partial/human review | 只能產生研究卡或 blocker | 必須回報 warning |
| `degraded` | 預設不可 publish；除非 degraded 只在非核心支線且 ranking/publish gate 仍完整 | 可以做 review，但不得當成成功驗證 | 可以進 fog map 作為風險訊號 | 必須回報 degraded + next action |
| `skipped` | daily skipped 不可 publish | daily 未 OK 時 external review skipped | 可記錄為等待，不跑 quota | 回報 skipped reason |
| `failed` / `blocked` | 一律不可 publish | 不啟動外部 review，除非是針對 failure 的 ops/debug review | 不進 ranking merge；只能留 blocker | 必須 fail-loud |

## 研究結果回 Ranking 的 Gate

研究回 ranking 不能只靠抽象的 `research_card / experiment / validation / decision / merge_policy / evidence_ledger` 名字，必須有 artifact 與 validator。最小契約如下：

| Gate node | 最小 artifact | Validator / gate | 允許動作 |
| --- | --- | --- | --- |
| `research_card` | `docs/tasks/<task_id>.md` 或 `artifacts/autonomous_research/research_cards_<run_date>.jsonl` | card 必須含 hypothesis、input_refs、blocked_conditions | 只排入研究 queue |
| `experiment` | `artifacts/autonomous_research/experiments/<experiment_id>/run_manifest.json` | 白名單 runner、固定 seed/config、不可改 production model | 只產 evidence |
| `validation` | `artifacts/autonomous_research/experiments/<experiment_id>/validation.json` | 驗證資料完整、無 leakage、baseline 可比較 | 產生 `passed/failed/needs_more_data` |
| `decision` | `artifacts/autonomous_research/decisions/<decision_id>.json` | decision enum 只能 `accept/reject/quarantine/needs_more_data` | 只有 `accept` 可往 merge policy |
| `merge_policy` | `artifacts/autonomous_research/merge_policy/<decision_id>.json` | 確認影響範圍、回測門檻、rollback 條件 | 只能開下一張 ranking/model 改動卡 |
| `evidence_ledger` | `artifacts/autonomous_research/evidence_ledger/<decision_id>.json` | Evidence Ledger 完整且 repo-relative paths | 才能交給 Ranking Bot 評估 |

`Decision=accept` 也不是自動改 ranking/model；它只允許開正式 implementation card 或交給 Ranking Bot 在下一輪受控改動中評估。

## Memory System 邊界

Top10 可以接既有記憶系統，但記憶系統在這條 harness 只做三件事：

- 開跑前 recall：回帶前輪 blocker、root question、handoff 摘要。
- 收尾時 milestone handoff：只在 root question、blocker、fork 或正式決策改變時寫入。
- 候選整理：`semantic_classifier`、`manual_chat_reviewer`、`full_rewash_runner` 只能產生候選或 review notes。

記憶系統不能做四件事：

- 不能宣告 `run truth`。
- 不能宣告 `ranking truth`。
- 不能宣告 `replay progress`。
- 不能直接改 ranking/model 或 canonical memory；canonical promotion 必須走記憶系統自己的 gate。

## Dashboard 狀態模型

Dashboard 至少要顯示下列資訊：

| 欄位 | 說明 |
| --- | --- |
| `run_id` | 單次執行唯一 ID |
| `run_date` | 交易日或執行日期 |
| `agent_id` | 15 隻 agent 的固定 ID |
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
| `formal_tasks` | 15 個固定任務節點，含 `task_id`、`agent_id`、責任、輸入/輸出、status、next_action、artifact_paths |
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

`run_id` 預設為 `daily-<run_date>`。`scripts/run_daily.sh` 會把 `artifacts/automation_status.json` 轉成 daily lane 的 agent events；`scripts/run_daily_publish.sh` 只補 `daily_push` 的報牌頻道事件；`scripts/run_external_review_host_runner.py` 預設也寫入同一個 `daily-<run_date>`，讓 GPT/Gemini 驗證、Fog Map Bot、Autonomous Research Worker Bot 與 Ops Reporter 都接回同一張 rollup。

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
| ChatGPT/Gemini browser adapter | `scripts/review_chatgpt_chrome.sh`、`scripts/review_gemini_chrome.sh` |
| ChatGPT/Gemini API fallback | `scripts/external_review_api_provider.py` |
| External review summary | `scripts/build_external_review_summary.py`、`scripts/verify_external_review_summary.py` |
| Fog Map Bot | `scripts/run_top10_fog_map_handoff.py`、`scripts/build_research_campaign_progress.py`、`scripts/build_research_fog_map.py`、`scripts/verify_research_fog_map.py` |
| Autonomous Research Worker Bot | `scripts/run_daily_research_quota.sh`、`scripts/run_autonomous_research.py`、`scripts/verify_daily_research_quota.py` |
| PM Research Harness Bot | `scripts/run_pm_research_harness_loop.sh`、`scripts/run_pm_research_harness_loop.py`、`scripts/verify_pm_research_harness_loop.py` |
| Monitoring API | `app/services/monitoring_service.py`、`app/api/routers/monitoring.py` |
| Visual flow | `web/harness-loop.html` |

## PM Research Harness Loop

`PM Research Harness Bot` 是 PM approval 之後的受控研究迴圈，不是迷霧面板，也不是 Fog Map burn-down worker。

- Fog Map Bot：維護完成度、星星點亮、候選策略隊列、研究團隊 Console、證據閘門與 blocker。
- Autonomous Research Worker Bot：依 queue 跑白名單研究 quota，產 evidence，不改 ranking/model。
- PM Research Harness Bot：只消費 PM 明確核准的 `TOP10_STOCK` review card，把核准項目轉成 `approved_work_queue` / `research_cards_YYYY-MM-DD.jsonl`，再驅動既有 research runner 並產下一輪 PM 決策卡。

安全邊界：

- `scripts/run_pm_research_harness_loop.sh` 本身預設 `TOP10_PM_RESEARCH_ENABLED=0`，避免人工誤跑；正式 launchd plist 會明確帶 `TOP10_PM_RESEARCH_ENABLED=1` 啟動研究 loop。
- 正式 launchd 預設 `TOP10_PM_RESEARCH_SEND_CARDS=0`、`TOP10_PM_RESEARCH_DRY_RUN_SEND=1`，不會默默送 Discord 審核卡。
- `TOP10_PM_RESEARCH_MAX_CONTINUATION_RUNS=8` 控制沒有新 PM 核准時最多延續研究幾輪；到上限後關閉 loop state，等待下一張 PM 核准卡。
- `TOP10_PM_RESEARCH_MIN_QUEUE_DEPTH=12` 與 `TOP10_PM_RESEARCH_DISCOVERY_MAX_TOPICS=30` 控制低水位補題；補題只更新 autonomous research active topic bank、manager queue、revisit action 與 discovery artifact，不改 ranking/model/publish。
- `--dry-run-send` 只限制 Discord 發卡，不限制研究 state 更新；consumed approvals、runs、連續延續次數仍會落檔。
- PM Research Harness Bot 與 Fog Map burn-down worker 使用 lock 互斥，避免兩條 loop 同時啟動 research runner。
- Python loop 只有在找到 PM approved research card，或既有 loop state 已啟用且實際跑出研究結果時，才會產生下一輪 PM review card。
- 核准只代表進下一步研究；不代表 production promotion、交易、ranking merge 或模型訓練。

## 下一步落地順序

1. 固定 dashboard manifest：`docs/architecture/top10_harness_team.dashboard.json`。
2. 讓每個 runner 寫出同一格式的 agent status event。
3. 新增工作進度頻道 webhook 設定，與原本報牌頻道分離。
4. Ops Reporter 先讀本地 status/summary artifact，再推送到工作進度頻道。
5. Dashboard 讀取 status event，顯示每日 run 的 14 agent 狀態與卡關點。

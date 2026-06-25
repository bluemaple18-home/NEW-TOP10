# ChatGPT / Gemini 外部檢核工作流

這條工作流固定由 `com.new-top10.external-review` 啟動，入口是 `scripts/run_external_review_host_runner.sh`，實際主控是 `scripts/run_external_review_host_runner.py`。ChatGPT 與 Gemini 不是兩條獨立排程，也不是兩個各跑各的 harness；它們是同一條外部檢核 harness 裡的兩個 provider adapter。

## 固定分工

| 順序 | formal agent | 負責 harness / script | 責任 | 輸出 |
| --- | --- | --- | --- | --- |
| 1 | `external_review_harness` | `run_external_review_host_runner.py` | 確認 daily OK、建立同日 `run_id`、產生並驗證 review packet、拒送 manifest | `review_packet_YYYY-MM-DD.json`、`host_runner_status_YYYY-MM-DD.json` |
| 2 | `ai_review_adapter` | 同一個 host runner 呼叫 provider adapter | 先跑 provider preflight，再固定送 ChatGPT / Gemini conversation，收 raw response，擋掉 smoke/太短回覆 | `chatgpt_raw/response/status`、`gemini_raw/response/status` |
| 3 | `disagreement_next_actions` | `build_external_review_summary.py` + `verify_external_review_summary.py` | 比較兩個外部 AI 與我們結果的分歧，產生人工複核與研究題目 | `external_review_summary_YYYY-MM-DD.json/md` |
| 4 | `fog_map` | `run_top10_fog_map_handoff.py` | 把外部檢核分歧與後驗訊號交給迷霧地圖，不直接改 ranking | `research_fog_map_latest.json`、`index.html` |
| 5 | `ops_reporter` | `build_top10_ops_progress_message.py` + `send_top10_ops_report.py` | 用中文送工作進度頻道，回報狀態、分歧、下一步 | `ops_progress_message_YYYY-MM-DD.md`、send receipt |

## Provider adapter 固定規則

| Provider | Adapter | 固定聊天框 | 成功條件 | 失敗處理 |
| --- | --- | --- | --- | --- |
| ChatGPT | `scripts/review_chatgpt_chrome.sh` | `TOP10 External Review - ChatGPT PROD` | raw response 至少 500 字、不是 smoke marker、normalize 與 contract verify 通過 | 標記 provider failed，不可補成假 OK |
| Gemini | `scripts/review_gemini_chrome.sh` | `TOP10 External Review - Gemini PROD` | raw response 至少 500 字、不是 smoke marker、normalize 與 contract verify 通過 | 標記 provider failed，不可補成假 OK |

Smoke test 只寫 `chatgpt_smoke_YYYY-MM-DD.json` 或 `gemini_smoke_YYYY-MM-DD.json`，不得覆蓋正式 raw / response artifact。

## 狀態規則

| 情況 | `ai_review_adapter` 狀態 | host runner 狀態 | 後續 |
| --- | --- | --- | --- |
| ChatGPT 與 Gemini 都成功 | `ok` | `OK` | 建立 summary，交給分歧處置與迷霧地圖 |
| 只有一個 provider 成功 | `degraded` | `PARTIAL` | 可以保留 partial summary，但工作進度必須說明缺哪一個 |
| 兩個 provider 都失敗 | `failed` | `FAILED` | 停止採信外部檢核，工作進度 fail-loud |
| daily 不是 OK | `skipped` | `SKIPPED` | 不送外部 AI，只回報等待 daily OK |

## 邊界

- ChatGPT / Gemini 只能產生外部檢核與研究假設。
- 外部 AI 結果不能直接改 ranking、模型、權重、報牌訊息。
- 任何分歧都要先變成 research card 或人工複核項目，再交給 Fog Map / Research Worker。
- 工作進度頻道只回報中文狀態與下一步，不送報牌內容。

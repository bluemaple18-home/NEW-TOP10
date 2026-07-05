# TOP10 Integration Manifest

本文件整理目前已接進 TOP10 harness 的功能域，避免 PM research、迷霧面板、外部檢核、後驗績效與 loop exporter 混成一包。

## 1. PM research approval loop

目的：PM 核准 TOP10_STOCK 研究卡後，驅動既有 research runner，產生本地研究證據與下一輪 PM 決策卡。

主要檔案：

- `scripts/run_pm_research_harness_loop.py`
- `scripts/run_pm_research_harness_loop.sh`
- `scripts/com.new-top10.pm-research-harness.plist`
- `scripts/build_pm_approved_work_queue.py`
- `scripts/verify_pm_approved_work_queue.py`
- `scripts/verify_pm_research_harness_loop.py`
- `integrations/openclaw-top10-pm-review/`
- `tests/test_pm_approved_work_queue.py`
- `tests/test_pm_research_harness_loop.py`

契約：

- launchd 明確帶 `TOP10_PM_RESEARCH_ENABLED=1`。
- Discord 發卡預設 `TOP10_PM_RESEARCH_SEND_CARDS=0`、`TOP10_PM_RESEARCH_DRY_RUN_SEND=1`。
- `--dry-run-send` 不阻止 state 更新。
- 無新 PM approval 時最多延續 `TOP10_PM_RESEARCH_MAX_CONTINUATION_RUNS=8` 輪。
- 與 Fog worker 用 lock 互斥，避免兩條 loop 同時啟動 research runner。

驗證：

```bash
.venv/bin/python scripts/verify_pm_research_harness_loop.py
.venv/bin/python -m unittest tests.test_pm_research_harness_loop tests.test_pm_approved_work_queue
```

## 2. Fog Map strategy ops UI

目的：迷霧主星圖只看完成度與星星點亮；底部承載候選策略隊列、研究團隊 Console、證據閘門與需要決策。

主要檔案：

- `scripts/build_research_fog_map.py`
- `scripts/verify_research_fog_map.py`
- `docs/AUTOMATION.md`
- `docs/architecture/top10_harness_team.md`
- `docs/architecture/top10_harness_team.dashboard.json`

驗證：

```bash
.venv/bin/python scripts/build_research_fog_map.py --date YYYY-MM-DD
.venv/bin/python scripts/verify_research_fog_map.py --date YYYY-MM-DD
```

## 3. Ops status and dashboard contract

目的：把 PM research harness status、15 formal agents、10 owner bots 與 loop exporter 收回同一套可觀測契約。

主要檔案：

- `scripts/build_top10_ops_progress_message.py`
- `scripts/record_top10_daily_status_events.py`
- `scripts/send_top10_ops_report.py`
- `scripts/export_top10_loop_status.py`
- `.work/loop-status-exporter/evidence/top10_loop_status_latest.json`
- `tests/test_top10_agent_status.py`
- `tests/test_top10_ops_report.py`
- `tests/test_top10_loop_status_exporter.py`
- `tests/test_monitoring_top10_harness_api.py`
- `tests/test_top10_status_recorders.py`

驗證：

```bash
.venv/bin/python -m unittest tests.test_top10_agent_status tests.test_top10_ops_report tests.test_top10_loop_status_exporter tests.test_monitoring_top10_harness_api tests.test_top10_status_recorders
```

## 4. External review provider contract

目的：把 ChatGPT/Gemini raw response、API/browser fallback、summary verify 與 host runner 狀態收回同一個外部檢核 contract。

主要檔案：

- `scripts/external_review_provider_contract.py`
- `scripts/external_review_api_provider.py`
- `scripts/normalize_external_review_response.py`
- `scripts/build_external_review_summary.py`
- `scripts/verify_external_review_summary.py`
- `scripts/run_external_review_host_runner.py`
- `scripts/verify_external_review_host_runner.py`
- `scripts/review_chatgpt_chrome.sh`
- `tests/test_external_review_summary_contract.py`
- `tests/test_external_review_host_runner_summary.py`

驗證：

```bash
.venv/bin/python -m unittest tests.test_external_review_summary_contract tests.test_external_review_host_runner_summary
```

## 5. Daily performance and decision quality

目的：把每日推薦後驗、performance review、decision quality 與 PM 決策卡連起來；只產研究候選與決策提示，不改 ranking。

主要檔案：

- `scripts/build_daily_recommendation_performance.py`
- `scripts/verify_daily_recommendation_performance.py`
- `scripts/build_daily_performance_review.py`
- `scripts/verify_daily_performance_review.py`
- `scripts/build_decision_quality.py`
- `scripts/verify_decision_quality.py`
- `scripts/build_research_decision_brief.py`
- `scripts/run_automation.py`

驗證：

```bash
.venv/bin/python scripts/verify_daily_recommendation_performance.py --help
.venv/bin/python scripts/verify_daily_performance_review.py --help
.venv/bin/python -m unittest tests.test_top10_ops_report
```

## 6. Market defense and research evidence map

目的：把 market defense replay、strategy archetype evidence map 與 task status ledger 收成研究證據來源。

主要檔案：

- `docs/tasks/2026-06-29_MARKET-DEFENSE-01_market_stress_guard_research.md`
- `scripts/build_market_defense_guard_replay.py`
- `scripts/build_strategy_archetype_evidence_map.py`
- `scripts/build_task_status_ledger.py`
- `tests/test_market_defense_guard_replay.py`
- `tests/test_strategy_archetype_evidence_map.py`

驗證：

```bash
.venv/bin/python -m unittest tests.test_market_defense_guard_replay tests.test_strategy_archetype_evidence_map
```

## 收口順序

1. PM research approval loop。
2. Fog Map strategy ops UI。
3. Ops status and dashboard contract。
4. External review provider contract。
5. Daily performance and decision quality。
6. Market defense and research evidence map。

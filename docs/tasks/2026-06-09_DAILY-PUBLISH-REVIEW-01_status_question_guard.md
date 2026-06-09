# DAILY-PUBLISH-REVIEW-01｜狀態詢問與每日推播修正 Review

## 背景

PM 原始問題只是詢問「今天下午會送到 Discord 的訊息為什麼沒有出現」。

本輪主機處理時先手動重跑 `scripts/run_daily.sh`，導致 daily ETL 依 `daily.pipeline_lookback_days=420` 重新抓取 rolling window。這超出原始問題需要，必須 review 並建立防呆。

## 本輪改動範圍

- `scripts/run_automation.py`
  - daily 成功後先寫出 `automation_status=OK`，再產 daily report / Clawd payload，避免 report 吃到上一輪 `FAILED`。
- `scripts/build_clawd_publish_payload.py`
  - 推播改成先列 `今日 10 檔總覽`。
  - 逐檔重點固定照原始 Top10 排名 1 到 10。
  - `主攻觀察 / 等確認 / 只等拉回 / 候補觀察 / 風險警示` 改為標籤，不再重排股票。
- `scripts/rewrite_clawd_publish_message_llm.py`
  - LLM rewrite 必須保留原始排名格式與 1 到 10 順序。
  - LLM 失敗或改壞時，還原 deterministic message。
- `scripts/verify_publish_risk_grouping.py`
  - 驗證 role / section / rank line / rank order。
  - 沒有風險股時不硬要求 `風險警示` 段落。

## Review 重點

1. 確認 `scripts/run_automation.py` 的 daily final artifact 順序不會造成 status race，也不會讓失敗流程誤產可發送 payload。
2. 確認推播訊息固定照原始 rank 1 到 10，分組只作標籤，不再改變排序。
3. 確認 LLM rewrite 不可改排名、不可改分組語意；違規時會 fallback deterministic。
4. 確認 verifier 能擋：
   - 少於 10 檔。
   - 10 檔順序錯。
   - 風險 / 等確認 / 拉回股票被寫成主攻。
   - LLM 改壞 section 或 rank line。
5. 確認沒有把 `clawd_dry_run: true` 改成 live send；本輪 live send 是手動 thin adapter，不是排程自動送。

## 防止再犯規則

以後 PM 問「狀態 / 為什麼沒出現 / 今天有沒有跑 / 有沒有送」時，主機只能先做 read-only triage：

- 可以讀：
  - `artifacts/automation_status.json`
  - `artifacts/daily_run_summary_YYYY-MM-DD.json`
  - `artifacts/ranking_YYYY-MM-DD.csv`
  - `artifacts/daily_report_YYYY-MM-DD.json`
  - `artifacts/clawd_publish_payload_YYYY-MM-DD.json`
  - `artifacts/clawd_publish_message_YYYY-MM-DD.md`
  - `logs/daily_YYYYMMDD.log`
- 不可以直接做：
  - 跑 `scripts/run_daily.sh`
  - 跑 ETL / pipeline
  - 跑 retrain
  - live send Discord
  - 修改 code / config

只有當 PM 明確說「重跑 / 補跑 / 送出 / 改掉 / 修」時，才可進入執行或改碼。

如果 read-only triage 發現 bug，先回報：

```text
我查到原因是 X。
目前還沒重跑、沒發送、沒改碼。
建議下一步是 Y。
```

再等 PM 指令，除非問題是明確低風險且 PM 已授權自主修復。

## 已跑驗證

```text
.venv/bin/python scripts/verify_publish_risk_grouping.py --date 2026-06-09
.venv/bin/python scripts/verify_daily_tape_and_rr_guard.py
.venv/bin/python -m app.pipeline_cli validate --json
.venv/bin/python -m scripts.run_automation daily --dry-run
.venv/bin/python -m py_compile scripts/run_automation.py scripts/build_clawd_publish_payload.py scripts/rewrite_clawd_publish_message_llm.py scripts/verify_publish_risk_grouping.py
git diff --check
```

## 今日事實

- 2026-06-09 daily artifact 已產生。
- 2026-06-09 Clawd live send 已手動成功。
- Discord messageId：`1513877380924444702`
- config 仍是 `clawd_dry_run: true`，排程目前不會自動 live send。

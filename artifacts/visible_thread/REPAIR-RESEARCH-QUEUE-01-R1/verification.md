---
id: REPAIR-RESEARCH-QUEUE-01-R1-verification
status: DELIVERED_CANDIDATE
type: repair-evidence
base_sha: fea9307224d3dccef28428773d09cf061491c5e0
review_sha: dddfbe3caf90f56aed37a41d7c93e10a38aa1d8a
---

# REPAIR-RESEARCH-QUEUE-01-R1 Verification

## 修復對應

- P1 queue lifecycle：queue 改依更新後的 status 與 run count 判斷未來可執行性；仍可第三次執行的 `partial_needs_followup` 保留在 queue，由 selection gate 執行 24 小時 cooldown。
- P1 history fallback：只接受 `execute=true` row；`execute=false` 與缺 `execute` 均 fail closed，明確 real-execute 的 legacy scalar `selected_topic_id` 保持相容。
- P2 契約：verifier 與架構文件改為 status／max-count／cooldown 政策，並驗證 `--rerun`／`--include-rejected` 無法 bypass。

## 驗證證據

- `.venv/bin/python -m unittest tests.test_autonomous_research_topic_bank tests.test_daily_research_quota_verifier tests.test_pm_research_harness_loop`
  - 19 tests passed。
- `.venv/bin/python scripts/verify_autonomous_research.py`
  - `AUTONOMOUS_RESEARCH_OK`。
- `.venv/bin/python -m py_compile scripts/run_autonomous_research.py scripts/verify_autonomous_research.py`
  - passed。
- `git diff --check`
  - passed。
- shell files 未變更，bash syntax 不適用。

## Lifecycle coverage

- run 1 後冷卻完成可進 run 2。
- run 2 仍 partial 時保留於 queue，立即 selection 因 24h cooldown 為空。
- cooldown 完成後可進 run 3；run count 達 3 後從 queue 移除。
- cooling、exhausted、rejected、empty queue 均有負例。
- dry-run、缺 `execute` 均不可作 fallback；`execute=true` legacy scalar 為正例。

## 邊界

- 未修改模型、ranking、promotion 或 shell worker。
- 未刪除或覆寫既有 research artifacts。
- 未 merge、push、deploy。

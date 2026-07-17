---
id: RESEARCH-QUEUE-01
status: INTEGRATED
type: implementation
ownership: implementation
risk: medium
card_thickness: standard
model: gpt-5.5
reasoning: medium
model_reason: 跨研究 manager、queue selection 與 Fog worker，但介面與失敗模式已定位且可回退。
candidate_sha: fea9307224d3dccef28428773d09cf061491c5e0
integrated_sha: d4389cf
evidence_path: artifacts/visible_thread/RESEARCH-QUEUE-01/
---

# RESEARCH-QUEUE-01：受控重跑政策

## Root question

當 `next_action_queue` 有待辦、但題目已有執行紀錄時，如何在不開放全域無條件重跑的前提下繼續處理研究佇列？

## 目標

- `partial_needs_followup` 與 `confirmed_for_next_replay` 可依明確上限與冷卻政策受控重跑。
- `rejected`、未達冷卻條件、缺少上次執行證據或超過上限者不可重跑。
- 空 queue 安全停止，不產生研究執行。
- 保留單一 queue owner、research-only、allowlisted runners 與 production promotion 禁止等 invariant。

## 政策契約

- `confirmed_for_next_replay`：總執行次數上限 2 次，距上次執行至少 24 小時。
- `partial_needs_followup`：總執行次數上限 3 次，距上次執行至少 24 小時。
- 已執行題目若無法從 registry 或 run history 證明上次執行時間，fail closed。
- `--rerun` 與 `--include-rejected` 不得繞過上述 manager 政策。

## Allowlist

- `scripts/run_autonomous_research.py`
- `scripts/run_fog_research_worker.sh`
- `tests/`
- `docs/tasks/2026-07-17_RESEARCH-QUEUE-01_controlled-rerun-policy.md`
- `artifacts/visible_thread/RESEARCH-QUEUE-01/`

## 禁止事項

- 不修改模型權重、訓練參數、production ranking 或 promotion。
- 不刪除或覆寫既有研究 artifacts。
- 不 merge、push 或 deploy。

## 驗證

- 回歸測試覆蓋可重跑、冷卻未滿、超限、rejected、缺時間與空 queue。
- bounded fixture 驗證只選出符合政策的 queue topic。
- 執行受影響測試與 `git diff --check`。
- 證據寫入 `artifacts/visible_thread/RESEARCH-QUEUE-01/`。

## 交付邊界

本卡已由主線驗收並整合為 `d4389cf`。

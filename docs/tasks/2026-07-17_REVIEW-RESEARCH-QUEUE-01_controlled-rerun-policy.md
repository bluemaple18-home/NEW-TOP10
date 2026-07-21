---
card_id: REVIEW-RESEARCH-QUEUE-01
status: REVIEW_NO_GO
ownership: independent_review
parent_card: RESEARCH-QUEUE-01
chain_id: RESEARCH-QUEUE-01
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 需獨立檢查 queue eligibility、時間冷卻、舊資料相容與防止無限重跑。
base_sha: 2ca23b2d6157e3336ae69babe81cb0cefb6800bd
candidate_sha: fea9307224d3dccef28428773d09cf061491c5e0
reviewed_commit: fea9307224d3dccef28428773d09cf061491c5e0
allowlist:
  - artifacts/visible_thread/RESEARCH-QUEUE-01/
  - docs/tasks/2026-07-17_RESEARCH-QUEUE-01_controlled-rerun-policy.md
  - scripts/run_autonomous_research.py
  - tests/test_autonomous_research_topic_bank.py
forbidden_scope:
  - 修改 candidate
  - merge、push、deploy
  - production ranking 或 promotion
evidence_path: artifacts/visible_thread/REVIEW-RESEARCH-QUEUE-01/
---

# REVIEW-RESEARCH-QUEUE-01：受控重跑政策獨立審查

1. 目標：獨立審查 candidate `fea9307224d3dccef28428773d09cf061491c5e0` 是否正確修復 queue 有待辦卻無 executable topic 的契約落差。
2. 範圍：只比較 base `2ca23b2d6157e3336ae69babe81cb0cefb6800bd` 與 candidate；檢查 correctness、regression、testing、research-only 與 queue-owner invariant。
3. 禁區：Reviewer 不得修改 candidate、不得 merge／push／deploy，不得改模型權重、production ranking 或 promotion。
4. 驗收：以具體 `path:line` findings 產生 `GO/NO-GO`；重跑關鍵測試，確認冷卻、次數上限、舊 run history fallback、rejected 與空 queue 行為。
5. 證據：寫入 `artifacts/visible_thread/REVIEW-RESEARCH-QUEUE-01/`，保留 reviewed commit、測試結果、findings 與 verdict；若 `NO-GO`，只回報 findings，由主線另開 Repair 卡。

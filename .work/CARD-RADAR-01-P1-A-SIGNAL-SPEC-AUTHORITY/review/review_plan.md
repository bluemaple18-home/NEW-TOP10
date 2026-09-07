# Review Plan

- task_id: CARD-RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY
- risk_tier: full
- task_thickness: strict
- risk_reasons: security_sensitive_files, large_diff, lifecycle_side_effect_failure_state_review

## Diff Summary

- files_total: 6
- files_reviewable: 6
- changed_lines: 1083
- added_lines: 1068
- removed_lines: 15

## Reviewers

- `coordinator`: 統整 finding、去重、校正嚴重度、輸出最終決策。
  - dispatch_card: 任務ID / review｜coordinator / 請讀 review_plan.json / 目的：統整所有 finding / 證據路徑：review_state.jsonl
- `correctness`: 檢查行為、資料流、狀態、邊界條件與錯誤處理。
  - dispatch_card: 任務ID / review｜correctness / 請讀 diff_entries.jsonl / 目的：找主要流程錯誤 / 證據路徑：finding_schema.json
- `regression`: 檢查既有 API、CLI、檔案格式、環境契約與跨機路徑。
  - dispatch_card: 任務ID / review｜regression / 請讀 diff_entries.jsonl / 目的：找回歸風險 / 證據路徑：finding_schema.json
- `test_gap`: 檢查風險點是否有足夠測試或驗收證據。
  - dispatch_card: 任務ID / review｜test_gap / 請讀 review_plan.json / 目的：找驗證缺口 / 證據路徑：finding_schema.json
- `maintainability`: 檢查重複、抽象、命名、可讀性與既有模式一致性。
  - dispatch_card: 任務ID / review｜maintainability / 請讀 diff_entries.jsonl / 目的：找非阻塞維護風險 / 證據路徑：finding_schema.json
- `security`: 只標記可利用或具體危險的安全問題。
  - dispatch_card: 任務ID / review｜security / 請讀 security_sensitive_files / 目的：找 exploit / 證據路徑：finding_schema.json
- `failure_state`: 從 trap／handler 武裝點開始，逐個副作用列舉失敗後的真實狀態、mutation、receipt 與 recovery。
  - dispatch_card: 任務ID / review｜failure_state / 請讀 lifecycle_side_effect_files 與 fixed diff / 目的：逐步驗證 failure state，不得只做靜態 fixed-diff 判讀 / 證據路徑：finding_schema.json
- `agents_md`: 檢查 AGENTS.md、skill、rules 是否因工具鏈或架構變更而需要同步。
  - dispatch_card: 任務ID / review｜agents_md / 請讀 agents_material_files / 目的：找 agent instructions drift / 證據路徑：finding_schema.json

## Side-effect Failure-state Policy

- required: true
- minimum_independent_reviewers: 2
- reviewer_independence: reviewers_must_not_read_each_others_verdict_before_submission
- disagreement_policy: preserve_disagreement_and_block_until_evidence_resolves_it
- required_method: start_at_each_trap_or_handler_arm_point
- required_method: enumerate_each_ordered_side_effect
- required_method: inject_failure_before_and_after_each_side_effect
- required_method: record_true_external_and_durable_state
- required_method: record_mutation_counts_and_receipt_state
- required_method: prove_exact_restore_or_fail_closed_terminal_state

## Outputs

- review_plan_json: /Users/mattkuo/TOP10new/.work/CARD-RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY/review/review_plan.json
- review_plan_md: /Users/mattkuo/TOP10new/.work/CARD-RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY/review/review_plan.md
- diff_entries: /Users/mattkuo/TOP10new/.work/CARD-RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY/review/diff_entries.jsonl
- finding_schema: /Users/mattkuo/TOP10new/.work/CARD-RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY/review/finding_schema.json
- review_state: /Users/mattkuo/TOP10new/.work/CARD-RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY/review/review_state.jsonl

# Review Plan

- task_id: REVIEW-FOG-CONTINUOUS-TOPIC-SUPPLY-01
- risk_tier: full
- task_thickness: strict
- risk_reasons: large_diff

## Diff Summary

- files_total: 7
- files_reviewable: 7
- changed_lines: 1264
- added_lines: 1213
- removed_lines: 51

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
- `performance`: 檢查 N+1、快取、批次、併發、I/O 與排程熱點。
  - dispatch_card: 任務ID / review｜performance / 請讀 performance_sensitive_files / 目的：找可量測效能回歸 / 證據路徑：finding_schema.json
- `agents_md`: 檢查 AGENTS.md、skill、rules 是否因工具鏈或架構變更而需要同步。
  - dispatch_card: 任務ID / review｜agents_md / 請讀 agents_material_files / 目的：找 agent instructions drift / 證據路徑：finding_schema.json

## Outputs

- review_plan_json: .work/FOG-CONTINUOUS-TOPIC-SUPPLY-01/review/review_plan.json
- review_plan_md: .work/FOG-CONTINUOUS-TOPIC-SUPPLY-01/review/review_plan.md
- diff_entries: .work/FOG-CONTINUOUS-TOPIC-SUPPLY-01/review/diff_entries.jsonl
- finding_schema: .work/FOG-CONTINUOUS-TOPIC-SUPPLY-01/review/finding_schema.json
- review_state: .work/FOG-CONTINUOUS-TOPIC-SUPPLY-01/review/review_state.jsonl

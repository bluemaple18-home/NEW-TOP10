# CLEANUP-33 Status

## Root Question
能否在完整保留 operational-rule `candidate` 與 `experiment` builder 的 old/new valid/missing 契約後，收斂成 `scripts/build_operational_rule_review.py` 具名 profile builder，並退休兩支舊入口？

## Blocker
None。canonical parity、focused tests、strict audits、daily hash gate、`git diff --check` 與 full pytest 均已通過。

## Fork
未分叉。依任務卡只做 operational-rule builder suite 收斂，不 merge、不 push。

## Current Status
已新增 `scripts/build_operational_rule_review.py`，以 `--profile candidate|experiment` 保留兩份舊 builder 契約，並完成主線整合與 canonical 驗收；已移除：

- `scripts/build_operational_rule_candidate_report.py`
- `scripts/build_operational_rule_experiment_report.py`

已新增 `tests/test_operational_rule_review_builder.py`，更新 `config/script_lifecycle.yaml` 的 reference audit baseline，並產出 `.work/CLEANUP-33/evidence/parity.json`。

## Next Step
封存任務並移除 task worktree。

## Waiting Condition
None。

## Limits
未改每日報牌、publish、模型、權重、正式 ranking、launchd、plist、automation 或既有研究 artifact。

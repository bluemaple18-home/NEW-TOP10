# CLEANUP-32 Status

## root question
能否在完整保留 training-candidate `attribution` 與 `risk_control` builder 的 old/new valid/missing 契約後，收斂成 `scripts/build_training_candidate_risk_review.py` 具名 profile builder，並退休兩支舊入口？

## blocker
None。canonical parity、focused tests、strict audits、daily hash gate、`git diff --check` 與 full pytest 均已通過。

## fork
無。只走卡片允許範圍，不 merge、不 push、不建立新環境、不下載依賴。

## 目前狀態
已新增 `scripts/build_training_candidate_risk_review.py`，以 `--profile attribution|risk_control` 保留兩份舊 builder 契約，並完成主線整合與 canonical 驗收；已移除：

- `scripts/build_training_candidate_risk_attribution.py`
- `scripts/build_training_candidate_risk_control_report.py`

已新增 `tests/test_training_candidate_risk_review_builder.py`，更新 `config/script_lifecycle.yaml` 的 reference audit baseline，並產出 `.work/CLEANUP-32/evidence/parity.json`。

## 下一步
封存任務並移除 task worktree。

## 等待條件
None。

## 限制
未改每日報牌、publish、模型、權重、正式 ranking、launchd、plist、automation 或既有研究 artifact。

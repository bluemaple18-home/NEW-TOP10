# CLEANUP-31 Status

## root question

能否在完整保留 `attribution` 與 `risk_control` verifier valid/invalid 契約的前提下，收斂成 `scripts/verify_training_candidate_risk_reports.py` 具名 profile verifier，並退休舊入口？

## blocker

None。canonical old/new parity、focused tests、strict audits、daily hash gate、`git diff --check` 與 full pytest 均已通過。

## fork

採用單一 verifier：

- `--profile attribution`
- `--profile risk_control`

payload 不新增 profile 欄位，以保留舊 verifier normalized payload parity。

## 目前狀態

已新增 `scripts/verify_training_candidate_risk_reports.py`，移除兩支舊 verifier，更新 `config/script_lifecycle.yaml`，並完成主線整合與 canonical 驗收。

## 下一步

封存任務並移除 task worktree。

## 等待條件

None。

## 限制

未改 builder 產出契約、研究 artifact、daily publish、模型、權重、正式 ranking、launchd、plist 或 automation。

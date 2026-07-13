# CLEANUP-30 Status

## root question

能否在完整保留 `hybrid_report` 與 `shadow_rankings` verifier valid/invalid 契約的前提下，收斂成 `scripts/verify_regime_conditional_research_contract.py` 具名 profile suite，並退休舊入口？

## blocker

None。canonical parity、focused tests、strict audits、daily hash gate 與 full pytest 均已通過。

## fork

採用單一 verifier：

- `--profile hybrid_report`
- `--profile shadow_rankings`

payload 不新增 profile 欄位，以保留舊 verifier normalized payload parity。

## 目前狀態

已新增 `scripts/verify_regime_conditional_research_contract.py`，移除兩支舊 verifier，更新 `config/script_lifecycle.yaml`，並完成主線整合與 canonical 驗收。

## 下一步

封存任務並移除 task worktree。

## 等待條件

None。

## 限制

未改 daily publish、模型、權重、正式 ranking、launchd、plist 或 automation。

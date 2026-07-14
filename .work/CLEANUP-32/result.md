# CLEANUP-32 Result

已完成 training-candidate risk builder 收斂：

- 新入口：`scripts/build_training_candidate_risk_review.py`
- profiles：`attribution`、`risk_control`
- retired：`scripts/build_training_candidate_risk_attribution.py`、`scripts/build_training_candidate_risk_control_report.py`
- consumer gate：`scripts/verify_training_candidate_risk_reports.py` 對兩個 valid profile 產物皆 `OK`

## Evidence
- parity：`.work/CLEANUP-32/evidence/parity.json` -> `PASS`
- focused tests：`pytest tests/test_training_candidate_risk_review_builder.py tests/test_training_candidate_risk_reports_verifier.py -q` -> `12 passed`
- py_compile：builder、verifier、兩支 audit script 通過
- lifecycle strict-new：`435 tracked scripts, 0 new unclassified` -> `PASS`
- reference strict-new：`435 tracked scripts, 0 new suspected orphans` -> `PASS`
- `git diff --cached --check` -> `PASS`

## Daily Hashes
- `scripts/run_daily.sh`: `3a0a0905a9f24f79938eb8a5d24c4c0d20bf841833ce0a5c07b078be4718f4a3`
- `scripts/run_daily_publish.sh`: `ff001af0c95d100d7e077bf1a6735f488e36234dadd4a8d73223486d747e84c3`
- `scripts/com.new-top10.daily.plist`: `eba01f79b457916608b2a2ca5c42bf61af12a2ec81b5f1901934491859155995`
- `config/automation.yaml`: `c68ca07816a859103013323214cdd47da23ee277cab54e0bd08d59839d70004a`

## Blocker
None。canonical full pytest：`246 passed, 28 subtests passed, 4 個既有依賴 warnings`。worktree 曾受 gitignored evidence 缺口影響，已由 canonical checkout 關閉。

## Boundary
未改每日報牌、publish、模型、權重、正式 ranking、launchd、plist、automation 或既有研究 artifact。

# CLEANUP-31 Result

## 結論

已把 training-candidate risk verifier 收斂為 `scripts/verify_training_candidate_risk_reports.py`，保留 `attribution` 與 `risk_control` 兩個 profile 的舊契約，並退休：

- `scripts/verify_training_candidate_risk_attribution.py`
- `scripts/verify_training_candidate_risk_control_report.py`

## 證據

- parity evidence：`.work/CLEANUP-31/evidence/parity.json`
- focused tests：`pytest tests/test_training_candidate_risk_reports_verifier.py -q` -> `8 passed`
- py_compile：`scripts/verify_training_candidate_risk_reports.py` 通過
- strict reference audit：`scripts/audit_script_references.py --strict-new` -> PASS，436 tracked scripts，0 new suspected orphans
- strict lifecycle audit：`scripts/audit_script_lifecycle.py --strict-new` -> PASS，436 tracked scripts，0 new unclassified
- full pytest（canonical）：`242 passed, 28 subtests passed, 4 個既有依賴 warnings`
- `git diff --check`：PASS
- daily 四檔 SHA-256：與 CLEANUP-30 baseline 完全相同

## blocker

None。worktree 曾受既有 gitignored evidence 缺口影響，已由 canonical checkout 完整通過並關閉。

## scope check

未改 builder 產出契約、既有研究 artifact、daily publish、模型、權重、正式 ranking、launchd、plist 或 automation。

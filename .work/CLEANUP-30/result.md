# CLEANUP-30 Result

## 結論

已把 regime conditional research verifier 收斂為 `scripts/verify_regime_conditional_research_contract.py`，保留 `hybrid_report` 與 `shadow_rankings` 兩個 profile 的舊契約，並退休：

- `scripts/verify_regime_conditional_hybrid_report.py`
- `scripts/verify_regime_conditional_shadow_rankings.py`

## 證據

- parity evidence：`.work/CLEANUP-30/evidence/parity.json`
- focused tests：`pytest -q -p no:cacheprovider tests/test_regime_conditional_suite.py` -> `15 passed`
- strict reference audit：`scripts/audit_script_references.py --strict-new` -> PASS，437 tracked scripts，0 new suspected orphans
- strict lifecycle audit：`scripts/audit_script_lifecycle.py --strict-new` -> PASS，437 tracked scripts，0 new unclassified
- full pytest（canonical）：`234 passed, 28 subtests passed, 4 個既有依賴 warnings`
- `git diff --check`：PASS
- daily 四檔 SHA-256：與 CLEANUP-29 baseline 完全相同

## blocker

None。worktree 曾受既有 gitignored evidence 缺口影響，已由 canonical checkout 完整通過並關閉。

## scope check

未改 builder 產出契約、研究 artifact、daily publish、模型、權重、正式 ranking、launchd、plist 或 automation。

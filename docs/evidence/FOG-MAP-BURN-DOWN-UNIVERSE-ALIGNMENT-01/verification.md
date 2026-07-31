---
id: FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01-verification
status: ready_for_independent_review
type: evidence
---

# Verification evidence

## Phase 0 RED

Command：

```text
.venv/bin/python -m pytest -q tests/test_research_fog_map_burn_down.py
```

Result：exit `1`，`2 failed, 2 passed, 4 subtests passed`。

- Producer failure：historical `full_universe_total=2,866,752` 被誤當成 current total，預期為 `2,921,184`。
- Verifier failure：合法 partial classification（classified `2,866,752`、pending `54,432`）仍被 `burn_down_counts_classify_full_universe` 拒絕。
- Negative guards：over-classified、negative pending、category sum mismatch 與 missing source scope fixtures 均保持 `FAILED`。

首次測試收集曾因 verifier module path 未設而在 collection 階段失敗；該次不是合格 RED，修正測試載入方式後才取得上述 target-symptom RED。

## GREEN

### Requirement mapping

- `FR-MAP-01`：producer 輸出的 `full_universe_total` 固定取 current `expanded_total`。
- `FR-MAP-02/03`：另存 `source_full_universe_total=2,866,752`；current total `2,921,184`；classified `2,866,752`；pending `54,432`；category sum 守恆。
- `FR-MAP-04`：合法 partial 轉綠；over-classified、negative／missing pending、count mismatch、missing／mismatched source scope 全部維持 fail closed。
- `FR-MAP-05`：322-topic generated map 的完整 verifier report 為 `OK`，不會只因 stale-smaller rollup exit `1`。
- `SC-MAP-01`：same-scope full classification 的 pending 為 `0`、progress 為 `1.0`。
- `SC-MAP-02`：未更動 topic supply、dimension contract、expanded／executed progress、ranking、model 或 promotion 路徑。

### Commands

- Targeted GREEN：`.venv/bin/python -m pytest -q tests/test_research_fog_map_burn_down.py` → `7 passed, 6 subtests passed`。
- Affected GREEN：`.venv/bin/python -m pytest -q tests/test_research_fog_map_burn_down.py tests/test_research_fog_map_refactor.py` → `11 passed, 6 subtests passed`。
- Full：`.venv/bin/python -m pytest` → `624 passed, 2 failed, 4 warnings`；Fog Map suites 全綠。
- Compile：changed Python files 通過 `.venv/bin/python -m py_compile`。
- DBG audit：`DBG_AUDIT_OK`。
- Exact allowlist audit：`ALLOWLIST_OK`。
- `git diff --check`：通過。

### Full-suite non-target failures

1. `tests/test_feature_promotion_decision.py::FeaturePromotionDecisionTests::test_complete_versioned_evidence_is_a_synthetic_go_only`：測試使用 local `2026-08-01`，production freshness authority 使用 UTC `2026-07-31`；synthetic evidence 被判定 future。此路徑不依賴 Fog Map changed files。
2. `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`：獨立 worktree 未 materialize ledger 所列 historical artifact／data evidence，失敗檢查為 `evidence_exists`。此路徑不依賴 Fog Map changed files。

兩項皆在 changed-file allowlist 外；依 strict scope 契約未修改。主線／Reviewer 可在具備相同 live artifacts 且越過 UTC 日界後重跑確認。

## Remaining risk

- 未執行人工 live Fog、daily quota、circuit recovery 或自然排程 runtime acceptance；依卡片契約留給整合後主線自然排程驗證。
- Full suite 有上述兩項既有環境／時區 failure，因此本卡僅交付 candidate，不宣稱全 repo GO。

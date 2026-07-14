---
id: CLEANUP-35-F1-EVIDENCE
status: complete
type: repair-evidence
---

# CLEANUP-35-F1 Verification Evidence

## Reproducible Commands

```bash
cd <repo-root>
uv run python scripts/verify_shadow_research_campaign_parity.py
uv run python -m pytest -q tests/test_shadow_research_campaign.py
uv run python scripts/audit_script_references.py --strict-new
uv run python scripts/audit_script_lifecycle.py --strict-new
uv run python -m py_compile scripts/run_shadow_research_campaign.py scripts/verify_shadow_research_campaign_parity.py
uv run python -m pytest -q
shasum -a 256 scripts/run_daily.sh scripts/run_daily_publish.sh scripts/com.new-top10.daily.plist config/automation.yaml
git diff --check
```

## Results

| Check | Result |
|---|---|
| old/new parity | `PASS`；4 stages × 3 fixtures；6 comparison axes 全通過 |
| mutation sensitivity | `PASS`；`A1_SCHEMA_VERSION` mutation 使 parity 成為 `FAIL` |
| focused pytest | `15 passed in 0.28s` |
| reference strict-new | `430 tracked scripts`；`0 new suspected orphans`；PASS |
| lifecycle strict-new | `430 tracked scripts`；PASS |
| py_compile | PASS |
| full pytest | `267 passed, 1 failed, 28 subtests passed, 4 warnings` |
| diff check | PASS |
| real replay / shadow ranking / training | `0` |

Full pytest 唯一 failure：

```text
tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
AssertionError: 'FAILED' != 'OK'
```

此 failure 與 R1 記錄相同，來源是乾淨 worktree 缺少 gitignored historical research/data evidence；本 repair diff 未修改 ledger builder/verifier，依 bounded scope 不處理。

## Daily Hashes

```text
3a0a0905a9f24f79938eb8a5d24c4c0d20bf841833ce0a5c07b078be4718f4a3  scripts/run_daily.sh
ff001af0c95d100d7e077bf1a6735f488e36234dadd4a8d73223486d747e84c3  scripts/run_daily_publish.sh
eba01f79b457916608b2a2ca5c42bf61af12a2ec81b5f1901934491859155995  scripts/com.new-top10.daily.plist
c68ca07816a859103013323214cdd47da23ee277cab54e0bd08d59839d70004a  config/automation.yaml
```

## Boundary

Parity harness 只執行 Git source loading、synthetic fixture I/O 與 mocked in-process subprocess；沒有執行任何 replay、ranking、training、deploy、merge 或 push。

---
id: CLEANUP-35-R1-RE-REVIEW-EVIDENCE
status: complete
type: independent-re-review-evidence
candidate_commit: f9b4a71
repair_commit: ef0f7c3
verdict: GO
---

# CLEANUP-35-R1 Re-review Evidence

## Scope

- chain_id：`CLEANUP-35`
- original findings：`C35-R1-F1`、`C35-R1-F2`
- repair diff：`e00919b..ef0f7c3`
- reviewer responsibility line：`codex/cleanup-35-r1`
- repair source worktree 只作 commit 來源；驗證在原 R1 worktree 暫時 detached 到 `ef0f7c3` 執行

## Reproducible Commands

```bash
cd <repo-root>
uv run python scripts/verify_shadow_research_campaign_parity.py
uv run python -m pytest -q tests/test_shadow_research_campaign.py
uv run python scripts/audit_script_references.py --strict-new
uv run python scripts/audit_script_lifecycle.py --strict-new
uv run python -m py_compile scripts/run_shadow_research_campaign.py scripts/verify_shadow_research_campaign_parity.py
uv run python -m pytest -q
git diff --check e00919b ef0f7c3
git diff --name-only e00919b ef0f7c3 -- scripts/run_shadow_research_campaign.py config/script_lifecycle.yaml scripts/run_daily.sh scripts/run_daily_publish.sh scripts/com.new-top10.daily.plist config/automation.yaml
sha256sum scripts/run_daily.sh scripts/run_daily_publish.sh scripts/com.new-top10.daily.plist config/automation.yaml
```

Reviewer 實際使用 card 允許的既有 borrowed `.venv` 執行等價 Python commands；上列使用 `uv run python` 作跨機可重跑入口。

## Results

| Check | Independent result |
|---|---|
| parity command | exit 0；`PASS`；重建後 worktree clean |
| parity matrix | 4 stages × 3 cases；12/12 PASS |
| comparison axes | normalized JSON / exact Markdown / normalized TSV / console JSON / exit code / command order 全 true |
| old/new bundle hash | 12/12 相等 |
| mutation sensitivity | `A1_SCHEMA_VERSION` mutation → observed parity `FAIL` |
| focused pytest | `15 passed in 0.31s` |
| reference strict-new | `430 tracked scripts`；0 new suspected orphans；PASS |
| lifecycle strict-new | `430 tracked scripts`；PASS |
| py_compile | PASS |
| repair diff check | PASS |
| protected-file diff | 無輸出；candidate runner、lifecycle、daily/publish/automation 未改 |
| full pytest | `267 passed, 1 failed, 28 subtests passed, 4 warnings` |
| real replay / ranking / training | `0` |

## Parity Matrix Summary

| Stage | Valid | Missing | Failure | Executed command counts |
|---|---|---|---|---|
| `a1-forward` | PASS | PASS | PASS | `4 / 4 / 4` |
| `candidate-stress` | PASS | PASS | PASS | `60 / 0 / 2` |
| `overnight-training` | PASS | PASS | PASS | `11 / 11 / 11` |
| `risk-matrix-summary` | PASS | PASS | PASS | `0 / 0 / 0` |

每一格的 old/new normalized bundle SHA-256 相等，六個 comparisons 全為 `true`。

## Full Pytest Remaining Risk

唯一 failure：

```text
tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
AssertionError: 'FAILED' != 'OK'
```

原因仍是乾淨 worktree 缺少 gitignored historical research/data evidence；與原 R1 記錄一致，且 repair diff 未修改 ledger builder/verifier。

## Daily Hashes

```text
3a0a0905a9f24f79938eb8a5d24c4c0d20bf841833ce0a5c07b078be4718f4a3  scripts/run_daily.sh
ff001af0c95d100d7e077bf1a6735f488e36234dadd4a8d73223486d747e84c3  scripts/run_daily_publish.sh
eba01f79b457916608b2a2ca5c42bf61af12a2ec81b5f1901934491859155995  scripts/com.new-top10.daily.plist
c68ca07816a859103013323214cdd47da23ee277cab54e0bd08d59839d70004a  config/automation.yaml
```

## Acceptance Mapping

- `C35-R1-F1`：可重跑 parity、六軸比較、mutation sensitivity 與零真實 subprocess 邊界均具證據，`RESOLVED`。
- `C35-R1-F2`：兩支 strict audit 與文件 count 都是 430，`RESOLVED`。
- verdict：`GO`。

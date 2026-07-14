---
id: CLEANUP-35-R1-EVIDENCE
status: complete
type: review-evidence
candidate_commit: f9b4a71
---

# CLEANUP-35-R1 Verification Evidence

## Environment

- review branch：`codex/cleanup-35-r1`
- base：`9748b95`
- candidate：`f9b4a71`
- reviewer HEAD before evidence commit：`956a83b`
- Python：依 card 借用既有 `.venv`；下列重現指令以 `uv run python` 表示跨機入口

## Reproducible Commands

```bash
cd <repo-root>
uv run python -m pytest -q tests/test_shadow_research_campaign.py
uv run python -m pytest --collect-only -q tests/test_shadow_research_campaign.py
uv run python scripts/audit_script_references.py --strict-new
uv run python scripts/audit_script_lifecycle.py --strict-new
uv run python -m py_compile scripts/run_shadow_research_campaign.py
uv run python -m pytest -q
git diff --check 9748b95 f9b4a71
sha256sum scripts/run_daily.sh scripts/run_daily_publish.sh scripts/com.new-top10.daily.plist config/automation.yaml
rg -n "importlib|spec_from_file_location|git show|9748b95|run_a1_forward|run_candidate_stress|run_overnight_shadow|build_overnight_risk" tests/test_shadow_research_campaign.py .work/CLEANUP-35/evidence/parity.json
```

Global dry-run（每個 `--output` 都是 local-only `/tmp` evidence，不可跨機照抄）：

```bash
uv run python scripts/run_shadow_research_campaign.py --dry-run --output /tmp/CLEANUP-35-R1_a1.json a1-forward --date 2026-06-18
uv run python scripts/run_shadow_research_campaign.py --dry-run --output /tmp/CLEANUP-35-R1_stress.json candidate-stress --date 2026-06-18
uv run python scripts/run_shadow_research_campaign.py --dry-run --output /tmp/CLEANUP-35-R1_training.json overnight-training --date 2026-06-18 --model-hash-before dummy
uv run python scripts/run_shadow_research_campaign.py --dry-run --output /tmp/CLEANUP-35-R1_risk.json risk-matrix-summary --date 2026-06-18 --model-hash-before dummy
```

## Results

| Check | Result |
|---|---|
| focused pytest | `13 passed in 0.16s` |
| collected focused cases | `13`；只 import 新 runner |
| global dry-run | 四 stage exit 0；`SKIPPED`；command count `4 / 60 / 23 / 0` |
| reference strict-new | `429 tracked scripts`；PASS |
| lifecycle strict-new | `429 tracked scripts`；PASS |
| py_compile | PASS |
| candidate diff check | PASS |
| full pytest | `265 passed, 1 failed, 28 subtests passed, 4 warnings` |
| stale old entry references in scripts/tests/config | 0 |
| optional devflow completion gate | 未執行；此 checkout 無 `scripts/devflow_completion_gate.sh` |
| real replay/training | 0 |

Full pytest 唯一失敗：

```text
tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
AssertionError: 'FAILED' != 'OK'
```

失敗 check 為 `evidence_exists`，缺少 gitignored historical research/data artifacts；candidate result 已揭露同類環境缺口，與 `9748b95..f9b4a71` diff 無直接關聯。

## Daily Hashes

```text
3a0a0905a9f24f79938eb8a5d24c4c0d20bf841833ce0a5c07b078be4718f4a3  scripts/run_daily.sh
ff001af0c95d100d7e077bf1a6735f488e36234dadd4a8d73223486d747e84c3  scripts/run_daily_publish.sh
eba01f79b457916608b2a2ca5c42bf61af12a2ec81b5f1901934491859155995  scripts/com.new-top10.daily.plist
c68ca07816a859103013323214cdd47da23ee277cab54e0bd08d59839d70004a  config/automation.yaml
```

## Finding Reproduction

`rg` 對 focused test 與 parity artifact 的結果只有 `.work/CLEANUP-35/evidence/parity.json:6` 命中 `9748b95`；沒有 old module loader 或 parity generator。`tests/test_shadow_research_campaign.py:16` 唯一被測 runner import 是新入口，因此現有 13 cases 無法重建 old/new parity hash。

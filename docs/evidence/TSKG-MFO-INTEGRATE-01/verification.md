---
id: TSKG-MFO-INTEGRATE-01-VERIFICATION
status: GO
type: verification
verified_on: 2026-07-21
source_commit: dfc30dc4a8466b914c642c1b38ea206dd388aa7c
target_branch: main
---

# TSKG-MFO-INTEGRATE-01 Verification

## Status

```text
status: GO
mainline_integration: PASS
observation_contract: PASS
read_model: PASS
t86_snapshot: PASS
daily_orchestrator_wiring: PASS
market_context_single_fetch_reuse: PASS
invalid_artifact_fail_soft: PASS
ranking_or_model_change: NONE
```

## Evidence

- Full unittest discovery：`287 tests / PASS`。
- Targeted automation／TSKG regression：`41 tests / PASS`。
- T86／orchestrator／market-context targeted：`14 tests / PASS`。
- `scripts/verify_market_context_fetcher.py`：`MARKET_CONTEXT_FETCHER_OK`。
- `scripts/verify_daily_market_coverage_gate.py`：`DAILY_MARKET_COVERAGE_GATE_OK`。
- `scripts/verify_daily_pipeline_window_override.py`：`DAILY_PIPELINE_WINDOW_OVERRIDE_OK`。
- `scripts/verify_resource_guard.py`：`RESOURCE_GUARD_OK`。
- `python -m compileall -q app scripts`：PASS。
- `git diff --check`：PASS；另檢查 19 個 untracked 新檔，無 whitespace error。

## Live read-only smoke

```text
trade_date: 2026-07-17
endpoint: https://www.twse.com.tw/rwd/zh/fund/T86
request_count: 1
credentials: none
row_count: 1337
unit: SHARE
canonical_sha256: b8a89322e7e2c4514a562c70fe9fd7d3351d31c54099659294a4b639902dd49a
artifact: artifacts/tskg/t86/twse_t86_2026-07-17.json
artifact_policy: ignored runtime output
```

## Acceptance mapping

- 來源分支未直接 merge；有效能力以目前 `main` 的 public contracts 與 orchestrator 重新接線。
- T86 snapshot 與 MFO TWD observation 維持獨立單位契約，沒有偽造換算。
- fetch 失敗且同日 artifact 損壞時，runner 回傳 `None` 並讓 market-context 使用既有 fallback，不把損壞檔傳入 CLI。
- production ranking、模型權重、API／LLM redistribution、Theme aggregation、graph diffusion 與 UI 不在本次變更內。

## Remaining limits

- 正式 rate／長期 retention／redistribution governance 仍未核准。
- TPEx 上櫃法人來源、Theme aggregation 與 Top10 feature 仍屬後續獨立工作。

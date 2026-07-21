---
id: TSKG-MFO-INTEGRATE-01
status: COMPLETE
type: implementation
source_branch: codex/tskg-mfo-daily-01
source_commit: dfc30dc4a8466b914c642c1b38ea206dd388aa7c
target_branch: main
---

# TSKG-MFO-INTEGRATE-01：市場法人流主線整合

## Root question

如何以目前 `main` 為唯一主線，吸收 TSKG market-flow candidate 的有效能力，同時保留新版 daily orchestrator、資料單位與 production ranking 邊界？

## Scope

- 整合 `SecurityFlowObservation` closed contract 與 source-neutral read model。
- 整合 TWSE T86 單日逐證券 `SHARE` snapshot、fetch CLI、atomic artifact 與 checksum。
- daily automation 每個交易日最多抓取一次 T86，market-context 重用同一 artifact。
- T86 失敗或既有 artifact 無效時，保留 market-context 原本的 fail-soft fallback。
- 整合本卡直接相關的 task／verification 文件。

## Do not touch

- 不改 `RankingPolicy`、`risk_adjusted_score`、模型權重或 production ranking。
- 不把 T86 `_shares` 欄位映射成 MFO observation 的 TWD value。
- 不提交 `artifacts/tskg/t86/*.json`。
- 不開 API／LLM redistribution、Theme aggregation、graph diffusion 或 UI。
- 不以來源分支的 `.work/current/*` 覆蓋目前主線狀態。

## Slices

1. `S1 observation/read-model`
   - Blocking edges：無。
   - Acceptance：closed schema、deterministic projection、partial/stale warning、defensive copy 測試通過。
2. `S2 T86 snapshot`
   - Blocking edges：main 的 TSKG identity timestamp parser 可用。
   - Acceptance：19 欄、整數 SHARE、算術、日期、checksum、atomic round-trip 與單次 GET 測試通過。
3. `S3 daily integration`
   - Blocking edges：S2。
   - Acceptance：目前 orchestrator 先跑 T86 再跑 market-context；有效 artifact 被重用；無效 artifact 不阻斷 fallback。
4. `S4 docs and acceptance`
   - Blocking edges：S1–S3。
   - Acceptance：受影響 verifiers、full tests、compileall、`git diff --check` 全部通過，且 diff 僅含本卡範圍。

## Verification

```bash
<repo-root>/.venv/bin/python -m unittest tests.test_tskg_mfo01 tests.test_tskg_flow_read_model tests.test_tskg_twse_t86 tests.test_tskg_t86_automation tests.test_daily_automation_orchestrator
<repo-root>/.venv/bin/python scripts/verify_market_context_fetcher.py
<repo-root>/.venv/bin/python scripts/verify_daily_market_coverage_gate.py
<repo-root>/.venv/bin/python scripts/verify_daily_pipeline_window_override.py
<repo-root>/.venv/bin/python scripts/verify_resource_guard.py
<repo-root>/.venv/bin/python -m unittest discover -s tests -p 'test*.py'
<repo-root>/.venv/bin/python -m compileall -q app scripts
git diff --check
```

## Current frontier

全部 slice 已完成。驗證證據：`docs/evidence/TSKG-MFO-INTEGRATE-01/verification.md`。

## Result

`COMPLETE / MAINLINE INTEGRATED`

- observation contract、read model、T86 snapshot 與 fetch CLI 已整合。
- T86 已接入目前 canonical daily orchestrator，沒有帶回來源分支的舊式流程。
- market-context 正常路徑重用同一 snapshot；fetch 失敗時只允許重用已重新驗證的同日 artifact。
- `.work/current`、ranking、模型權重、API／LLM redistribution 與 UI 均未修改。

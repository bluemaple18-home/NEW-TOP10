---
card_id: TSKG-MFO-THEME-01
chain_id: TOP10-NEXT-WAVE-20260722
status: CARD_DRAFTED
type: implementation
owner: receiving Mini
model: receiving Mini
reasoning: medium
model_reason: 使用者指定 Mini；聚合公式與 membership provenance 由 deterministic tests 固定。
thickness: strict
depends_on: [TSKG-MFO-TPEX-01_decision]
worktree: receiving_host_must_provision
---

# TSKG-MFO-THEME-01 Theme Flow Aggregation

任務ID：TSKG-MFO-THEME-01
卡片類型｜派工對象：Theme Contract + Aggregation｜Mini
請讀：app/tskg/flow_observation.py、app/tskg/flow_read_model.py、data/reference/stock_concept_membership.csv、docs/tasks/2026-07-20_UI-MFR-00_market_flow_radar_backlog.md
任務目的：建立具版本、evidence、coverage 與 freshness 的 Theme membership snapshot，並對法人 observation 做可重算聚合
證據路徑：docs/evidence/TSKG-MFO-THEME-01/、.work/TSKG-MFO-THEME-01/evidence/

## Allowlist

- app/tskg/theme_*.py
- app/tskg/flow_read_model.py
- data/fixtures/tskg/theme_*.json
- scripts/build_tskg_theme_*.py
- scripts/verify_tskg_theme_*.py
- tests/test_tskg_theme*.py
- docs/tasks/、docs/evidence/、.work/ 本卡路徑

## Contract

- membership snapshot 必須有 as_of_date、source、version/hash、effective interval 與 evidence locator。
- 聚合公式固定法人買進、賣出、淨額、coverage、missing count；不得引入價格、報酬、預測或買賣建議。
- 多重 Theme membership 的 allocation policy 必須明示並測試，禁止無聲 double count。
- observation、Theme aggregation 與 graph truth 分離。
- TWSE-only 時明示 venue coverage；TPEx blocked 不得假裝全市場。

## Verification

```bash
uv run pytest tests/test_tskg_theme*.py tests/test_tskg_mfo01.py tests/test_tskg_flow_read_model.py
uv run python scripts/verify_tskg_theme_flow.py
git diff --check
```

Acceptance 需涵蓋 stale/missing membership、重複 membership、零 coverage、跨日期與 deterministic rerun。

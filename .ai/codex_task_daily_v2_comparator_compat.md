---
id: REPAIR-05A
status: completed
type: repair
priority: P0
model: gpt-5.6-terra
---

# Daily v2 comparator 舊 schema 相容修復

## 目標

修正 real shadow comparison 的假 NO-GO，同時維持嚴格 schema 防線。正式 2026-07-09 證據已證明 Top10 10／10、順序相同、8 個核心分數差異皆為 0。

## 必須修改

- baseline 與 shadow 都沒有 `rank` 時，以 CSV row position 1..10 作為 rank，並在 comparison 明示 `rank_source=position`。
- 只有一邊缺 `rank`，或現有 rank 非 1..10，仍判 NO-GO。
- `missing_in_shadow` 一律 blocking。
- shadow 新增欄位只有以下 allowlist 可視為 additive non-blocking：
  - `strategy_route_regime`
  - `strategy_route_production`
  - `strategy_route_shadow`
  - `strategy_route_report_only`
  - `strategy_route_blocked`
  - `strategy_route_mutates_production_score`
- 任意其他 extra column 仍判 blocking；comparison 要分開列出 allowlisted 與 unexpected extra。

## 可改範圍

- `app/contracts/daily_v2_comparison.py`
- `tests/test_daily_v2_real_shadow.py`
- 本卡 status／result。

## 不可改範圍

- ranking engine、model、features、live daily scripts/config/plist、正式 artifacts。
- 不得放寬 Top10、順序或核心分數 tolerance。
- 不得切 production 或發送訊息。

## 驗收

- 雙方無 rank 且順序相同可 GO，comparison 明示 positional rank。
- 單邊缺 rank NO-GO。
- allowlisted additive columns 不阻塞；未知 extra 仍 NO-GO。
- 原本 wrong order、wrong score、wrong schema 測試保持有效。
- 主線整合後重跑 2026-07-09 real shadow；comparison 應只剩 model version blocker 影響 production switch。
- `git diff --check` 通過；不 commit、不 merge、不 push。

## Result

- 雙方都沒有 `rank` 時改採 CSV row position，comparison 明示 `rank_source=position`。
- 六個 strategy-route additive 欄位不阻塞；未知 extra、missing 欄位、單邊缺 rank、非法 rank 仍為 `NO-GO`。
- 定向測試 16 個通過；整合後正式 2026-07-09 comparison 為 `GO`，Top10 10／10且順序相同。
- 整合 commit：`25ade5d`。

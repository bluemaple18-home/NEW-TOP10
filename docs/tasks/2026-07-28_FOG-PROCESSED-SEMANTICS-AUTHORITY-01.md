---
id: FOG-PROCESSED-SEMANTICS-AUTHORITY-01
status: VERIFIED_CANDIDATE
type: repair
root_question: 如何讓 research map 與 weekend inventory 使用同一 processed-combination 定義，以解除 I5 live acceptance blocker？
---

# FOG-PROCESSED-SEMANTICS-AUTHORITY-01

## 已知 RED

- Live worker 的 map 為 `expanded_processed=33358`，inventory 為
  `current_processed_count=33360`，兩次 bounded rebuild 固定差 2。
- 差異不是 race：兩筆皆為 v2 default-coordinate completed rows；research-map
  completion predicate刻意不把 default coordinate重複算成 expansion，inventory
  卻把任何 exact record直接算成 processed。
- Retry circuit 目前正確維持 open；修復驗證完成前不得旋轉或刪除 state。

## 契約

- Inventory 必須重用 `is_completed_v2_expansion_record()`，不得另寫近似判斷。
- 合法 non-default completed v2 row 仍為 processed。
- Default-coordinate、incomplete、missing artifact、非 v2 completion row 不得由
  expansion path算 processed；default coordinate只可走既有 base-scenario folding。
- 修後 map／inventory processed count一致，symmetric difference為空。
- 不得容忍差 2、硬編碼補值、sleep、增加 retry或放寬 verifier。

## Exact changed-file allowlist

- `docs/tasks/2026-07-28_FOG-PROCESSED-SEMANTICS-AUTHORITY-01.md`
- `scripts/build_weekend_universe_inventory.py`
- `tests/test_weekend_universe_inventory_snapshot.py`
- `docs/evidence/FOG-PROCESSED-SEMANTICS-AUTHORITY-01/**`

## 驗證

- Red→green regression：default-coordinate／incomplete／missing artifact不計入
  expansion processed；合法 non-default completed仍計入。
- `tests/test_weekend_universe_inventory_snapshot.py`
- 受影響 Fog／weekend targeted tests。
- Full pytest、`git diff --check`、exact allowlist。
- Live frozen snapshot重算須由 `33360/33358` 變為 `33358/33358`。

## Production boundary

- 本修復不修改 model、ranking、weights、baseline、promotion或 queue。
- 修復 Review／整合完成前不恢復 circuit。
- 完成後回原 I5 流程，依 verified recovery path旋轉 state並做三輪 scheduler
  acceptance；任何 gate失敗回 safe stopped state。

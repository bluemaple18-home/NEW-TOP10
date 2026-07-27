---
id: REPAIR-FOG-RECOVERY-01-02
chain_id: FOG-RECOVERY-01
repair_generation: 2
status: REPAIR_READY
type: implementation
owner: repair-thread
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 主線 live acceptance 發現跨 host-runner 階段順序的 P1，需補 public seam 回歸測試與最小流程修正。
reviewed_candidate_sha: 9ce4d80a22a01c79a25368d30cfb77859d0f83ec
re_review_evidence_sha: b381e769a0beb644cdc897ab88555f03c4697c89
findings:
  - FOG-RECOVERY-R02
---

# REPAIR-FOG-RECOVERY-01-02

## Finding FOG-RECOVERY-R02（P1）

主線 live acceptance 執行 linkage-only host runner 後，`build_weekend_universe_inventory.py` 連續兩次得到：

- current snapshot：`33360 / 2833392`
- fog map snapshot：`33358 / 2833394`

bounded rebuild 正確 fail-loud，但 `run_controlled_grid_drain_host_runner.py` 先建 inventory，成功後才刷新 research progress／fog map；因此持久 stale map 無法靠 bounded rebuild 自癒，circuit recovery 永遠無法通過。

## 允許範圍

- `scripts/run_controlled_grid_drain_host_runner.py`
- `scripts/build_weekend_universe_inventory.py`（僅在證據證明必要時）
- 直接相關 `tests/test_*.py`
- `docs/evidence/REPAIR-FOG-RECOVERY-01-02/repair.md`

## 禁止範圍

- 不得放寬 inventory verifier 或移除 bounded fail-loud。
- 不得直接清除 live circuit、改 production ranking／模型／promotion。
- 不得執行 cleanup、replay、外部服務、publish 或 push。
- 不得修改 FOG-RECOVERY-R01 以外的歷史 review evidence。

## 驗收

- 先建立 red-capable host-runner order test：持久 stale fog map + fresh run history 在舊順序失敗，新順序能刷新 authoritative progress/map 後建立一致 inventory。
- 任一 progress/map refresh 失敗時，inventory 不得執行或不得產生假 OK。
- linkage-only contract 保持：不 replay、不 train、不改 production ranking。
- targeted tests、兩個 circuit shell regressions、`bash -n`、完整 `pytest -q`、固定範圍 `git diff --check` 通過。
- 原子 Repair-2 commit；若 re-review 仍 NO-GO，整條 chain 必須 BLOCKED，不得建立 Repair-3。

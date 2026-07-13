# CLEANUP-22｜登記保留的 survivor artifact builder

- status: done
- priority: P1
- task thickness: standard

## 目標

修復 CLEANUP-21 刪除唯一靜態 consumer 後揭露的 reference-audit 缺口。保留 `scripts/build_mass_candidate_survivor_replay_extension.py`，並把它登記為有明確 artifact consumer 的核准無引用工具。

## 可改檔案

- `config/script_lifecycle.yaml`（新增單一 approved-unreferenced 項目）
- `.work/CLEANUP-22/evidence/verification.txt`（新增）
- 本卡 status/result

## 不可改

- `scripts/build_mass_candidate_survivor_replay_extension.py`
- 其他 code/config/scripts、每日控制面、artifacts
- 不執行 production daily/retrain/send

## 保留證據

- CLEANUP-21 刪除的 `scripts/build_mass_candidate_sector_cap_extension.py` 原為唯一靜態 import consumer。
- `scripts/build_mass_candidate_shadow_dry_run.py` 的 `--survivor-extension` 預設讀取其產物 `artifacts/model_experiments/mass_candidate_survivor_replay_extension_2026-06-02.json`。
- 因 artifact producer 仍具有可重建性價值，判定 `retain`，不得連鎖刪除。

## 驗收

- script reference audit `--strict-new` 通過。
- script lifecycle audit `--strict-new` 通過。
- audit 單元測試與完整 pytest 通過。
- `git diff --check` 通過；四個每日控制檔 SHA-256 維持 CLEANUP-21 卡片基準。

## 回報

主線 review repair；建立單一 atomic commit，不 push。

## 結果

- 已保留 `scripts/build_mass_candidate_survivor_replay_extension.py`，並新增單一 reference-audit 例外。
- reference/lifecycle strict audit、audit 單元測試與完整 pytest 均通過。
- 詳細證據：`.work/CLEANUP-22/evidence/verification.txt`。

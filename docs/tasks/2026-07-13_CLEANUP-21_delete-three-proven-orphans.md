# CLEANUP-21｜刪除三支已證實孤兒研究腳本

- status: ready
- priority: P1
- task thickness: standard

## 目標

刪除 CLEANUP-17 已判定為 `delete_candidate/high` 的三支一次性研究腳本，並移除其 lifecycle 例外；不得擴大到其他 `archive_candidate` 或 `unknown`。

## 可改檔案

- `scripts/analyze_fixed_share_persistence.py`（刪除）
- `scripts/build_mainline_a_regime_validation.py`（刪除）
- `scripts/build_mass_candidate_sector_cap_extension.py`（刪除）
- `config/script_lifecycle.yaml`（只移除上述三項）
- `.work/CLEANUP-21/evidence/verification.txt`（新增）
- 本卡 status/result

## 不可改

- 每日報牌、發送、訓練、launchd、plist 與 automation 控制面
- 其他 `scripts/`、測試、artifact、歷史任務文件
- 不執行 production daily/retrain/send，不刪歷史 artifacts

## 依據

- `.work/CLEANUP-17/evidence/orphan-triage.json`
- 三支腳本均為 `delete_candidate/high`、無 tracked consumer、無外部 runtime 證據、無唯一 artifact consumer。
- 主線交叉檢查只找到 `config/script_lifecycle.yaml` 的 approved-unreferenced 例外。

## 驗收

- 三支腳本不存在，lifecycle 例外同步移除；其他檔案不變。
- `rg` 不再找到 active code/config reference；歷史卡片與 evidence 可保留。
- 執行 script lifecycle/reference audit、受影響測試與完整 pytest。
- `git diff --check` 通過，並檢查四個每日控制檔 SHA-256 不變：
  - `scripts/run_daily.sh`: `3a0a0905a9f24f79938eb8a5d24c4c0d20bf841833ce0a5c07b078be4718f4a3`
  - `scripts/run_daily_publish.sh`: `ff001af0c95d100d7e077bf1a6735f488e36234dadd4a8d73223486d747e84c3`
  - `scripts/com.new-top10.daily.plist`: `eba01f79b457916608b2a2ca5c42bf61af12a2ec81b5f1901934491859155995`
  - `config/automation.yaml`: `c68ca07816a859103013323214cdd47da23ee277cab54e0bd08d59839d70004a`

## 回報

建立單一 atomic commit；回報刪除清單、測試結果、控制檔 hashes 與剩餘風險，不 merge、不 push。

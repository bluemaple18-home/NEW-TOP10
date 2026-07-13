# CLEANUP-26｜刪除四支已證實孤兒工具

- status: ready
- priority: P1
- task thickness: standard

## 目標

刪除 CLEANUP-23／24 已判定為高信心退休候選的四支工具，並移除其 script reference audit 例外；不得擴大到其他 archive／merge／unknown 項目。

## 可改檔案

- `scripts/run_controlled_grid_drain_host_runner.sh`（刪除；保留同名 `.py` runner）
- `scripts/sync_from_remote.sh`（刪除）
- `scripts/compare_portfolio_replay_variants.py`（刪除）
- `scripts/research_ranking_score_shadow.py`（刪除）
- `config/script_lifecycle.yaml`（只移除上述四項）
- `.work/CLEANUP-26/evidence/verification.txt`（新增）
- 本卡 status/result

## 不可改

- 其他 scripts、artifact、歷史任務文件與測試契約
- 每日報牌、publish、模型、正式排名、launchd、plist、automation 控制面
- 不執行 sync、push、daily、retrain、send，不刪歷史 artifacts

## 依據

- `.work/CLEANUP-23/evidence/unknown-resolution.json`
- `.work/CLEANUP-24/evidence/retirement-plan.json`
- shell wrapper 無外部 runtime/SOP consumer，底層 Python runner仍保留。
- 另外三支無 active consumer、無唯一契約；歷史 artifact 與 Git history足以保留 provenance。

## 驗收

- 四支目標不存在，lifecycle 例外只移除四筆；同名 Python runner仍存在。
- active code/config reference 掃描無目標路徑。
- script reference/lifecycle strict audit、audit 單元測試與完整 pytest 通過。
- `git diff --check` 通過；四個每日控制檔 SHA-256 維持：
  - `scripts/run_daily.sh`: `3a0a0905a9f24f79938eb8a5d24c4c0d20bf841833ce0a5c07b078be4718f4a3`
  - `scripts/run_daily_publish.sh`: `ff001af0c95d100d7e077bf1a6735f488e36234dadd4a8d73223486d747e84c3`
  - `scripts/com.new-top10.daily.plist`: `eba01f79b457916608b2a2ca5c42bf61af12a2ec81b5f1901934491859155995`
  - `config/automation.yaml`: `c68ca07816a859103013323214cdd47da23ee277cab54e0bd08d59839d70004a`

## 回報

建立單一 atomic commit；回報刪除清單、測試、hash 與剩餘風險，不 merge、不 push。

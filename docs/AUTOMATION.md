# NEW-TOP10 自動化系統使用手冊

## 📚 概覽

本系統提供完整的自動化功能，讓選股系統能夠無人值守運作：

- 📊 **每日自動執行** (22:00): ETL 資料更新 + Agent B 選股
- 🔧 **每日漂移監控** (02:00): PSI 檢查；模型重訓改為手動或週期任務
- 🔎 **每月 reference 維護** (每月 1 日 03:30): 概念股 / 產業 / 供應鏈來源 probe + import
- 📈 **PSI 漂移監控**: 自動偵測特徵分佈變化
- 🔔 **通知推播** (可選): Line Notify 整合

---

## 🚀 快速開始

### 1. 安裝自動排程 (macOS 推薦)

```bash
cd /Users/matt/TOP10new
bash scripts/setup_launchd.sh
```

**說明**: macOS 上 launchd 比 cron 更可靠，開機後會自動載入。

### 2. 手動測試腳本

在安裝排程前，建議先手動測試：

```bash
# 測試每日執行流程
bash scripts/run_daily.sh

# 測試每日 PSI 監控流程
bash scripts/daily_retrain.sh monitor

# 手動重訓模型
bash scripts/daily_retrain.sh retrain
```

### 3. 檢查排程狀態

```bash
# 查看已載入的排程
launchctl list | grep new-top10

# 查看日誌
tail -f logs/launchd_daily.log
tail -f logs/launchd_retrain.log
```

---

## 📋 腳本說明

### `scripts/run_daily.sh`
**功能**: 每日自動執行 (22:00)
**流程**:
1. 執行 daily preflight：交易日 gate、模型檔存在、資料 freshness。
2. 執行 ETL 更新當日資料。
3. 執行資料契約驗證與 ETL 後 freshness 檢查。
4. 呼叫 Agent B 選股。
5. 產出 `artifacts/ranking_YYYY-MM-DD.csv`。
6. 產出 `artifacts/weekly_candidate_snapshot_YYYY-MM-DD.json`，固定本週模型初選池 / 每日快照 contract。
7. 產出 `artifacts/daily_report_YYYY-MM-DD.json/md`。
8. 產出 `artifacts/clawd_publish_payload_YYYY-MM-DD.json` 與 `artifacts/clawd_publish_message_YYYY-MM-DD.md`，只作為 Clawd 接手 payload，不實際發送。
9. 更新 `artifacts/automation_status.json` 與 `artifacts/daily_run_summary_YYYY-MM-DD.json`。
10. 若 `daily.postcheck_enabled=true`，執行可選 postcheck，輸出 `artifacts/daily_postcheck_YYYY-MM-DD.json`。
11. 記錄日誌至 `logs/daily_YYYYMMDD.log`。

### `scripts/daily_retrain.sh`
**功能**: 每日 PSI 監控 (02:00)，可手動傳入 `retrain` 執行模型重訓
**流程**:
1. 預設執行 PSI 漂移監控、factor monitor、M13 產業動能 shadow monitor 與 model health report，不覆蓋模型
2. 傳入 `retrain` 時先檢查舊模型存在、資料 freshness 與 pipeline contract
3. 備份 `models/latest_lgbm.pkl` 到 `models/backup/`
4. 執行 LightGBM 訓練後，驗證新模型格式、mtime、feature count 與 metadata
5. 跑 ranking smoke，確認新模型可產出當期 `ranking_YYYY-MM-DD.csv`
6. 跑 PSI / factor / industry monitor 與 model health report
7. `--trigger auto|scheduled` 時套用 promotion gate；若 PSI `CRITICAL` 或 factor `WARN` 超門檻，拒絕 promote 並回滾
8. 任一訓練後驗證失敗時，從備份回滾 `models/latest_lgbm.pkl`
9. 清理 30 天前的舊備份
10. 更新 `artifacts/automation_status.json`；重訓模式另產出 `artifacts/retrain_run_summary_YYYY-MM-DD.json`

### `scripts/run_automation.py`
**功能**: 自動化統一入口，shell、launchd、cron 都只呼叫它
**模式**:
```bash
uv run --with-requirements requirements.txt python -m scripts.run_automation daily --dry-run
uv run --with-requirements requirements.txt python -m scripts.run_automation monitor --dry-run
uv run --with-requirements requirements.txt python -m scripts.run_automation retrain --dry-run
uv run --with-requirements requirements.txt python -m scripts.run_automation retrain --trigger scheduled --dry-run
uv run --with-requirements requirements.txt python -m scripts.run_automation reference --dry-run
uv run --with-requirements requirements.txt python -m scripts.run_automation status
```

每日流程會在 ETL 後執行 `python -m app.pipeline_cli validate`，確認 `features/events/universe` 符合資料契約後才跑排名。

ranking 後會執行 weekly snapshot：

```bash
uv run --with-requirements requirements.txt python scripts/build_weekly_candidate_snapshot.py --ranking artifacts/ranking_YYYY-MM-DD.csv
```

這個 artifact 只固定「模型初選池 / 每日快照」來源資料，不套用前台全域投資設定；`/api/weekly-candidates` 會優先讀最新 `weekly_candidate_snapshot_*.json`，沒有 snapshot 才 fallback 到 latest ranking。

ranking 後也會產生日報與 Clawd-ready payload：

```bash
uv run --with-requirements requirements.txt python scripts/generate_daily_report.py --ranking artifacts/ranking_YYYY-MM-DD.csv
uv run --with-requirements requirements.txt python scripts/build_clawd_publish_payload.py --report artifacts/daily_report_YYYY-MM-DD.json
```

`build_clawd_publish_payload.py` 只寫 artifact，不會呼叫 Clawd、不會讀 token、不會送出訊息。未設定 `notify.clawd_channel` / `notify.clawd_to` 時，payload 會標記為 `PENDING_TARGET`；實際發送仍受 `notify.clawd_enabled=false` 保護，後續需另開發送卡才會接上 Clawd。

每日後驗收可手動執行：

```bash
uv run --with-requirements requirements.txt python scripts/run_daily_postcheck.py --skip-api
uv run --with-requirements requirements.txt python scripts/run_daily_postcheck.py --ranking artifacts/ranking_YYYY-MM-DD.csv --skip-api
uv run --with-requirements requirements.txt python scripts/run_daily_postcheck.py --include-frontend
```

`--skip-api` 只驗 ranking artifact；若最近一次 `automation_status.json` 來自 dry-run，請明確傳入 `--ranking artifacts/ranking_YYYY-MM-DD.csv`，避免把 `expected_ranking_artifact` 誤當成正式 daily 產物。`--include-frontend` 會呼叫既有 frontend smoke，確認候補列表、個股頁、K 線 30D 與交易計畫 rail badge 載入。自動化 daily 預設不啟用 postcheck，避免 launchd 被前端或 Chrome 環境影響。

每日狀態 schema：

- `schema_version`: 目前為 `daily-run-status.v1`。
- `run_date`: 以 `config/automation.yaml` 的 `timezone` 計算，預設 `Asia/Taipei`。
- `status`: `OK` / `FAILED` / `SKIPPED`。
- `skip_reason`: 非交易日或設定停用時必填。
- `metadata.model`: `models/latest_lgbm.pkl` 是否存在與 mtime。
- `metadata.data_freshness`: `features.parquet`、`events.parquet`、`universe.parquet` 的最新日期與 lag days。
- `metadata.ranking_artifact`: daily ranking 產物路徑。
- `metadata.expected_ranking_artifact`: dry-run 或缺檔診斷時的預期 ranking 路徑；dry-run 不會把既有舊檔當正式成功產物。
- `metadata.daily_report_artifact`: 每日決策日報 JSON 路徑。
- `metadata.clawd_publish_payload`: Clawd-ready payload JSON 路徑；只代表可交接，不代表已發送。
- `metadata.clawd_publish_message`: Clawd-ready Markdown 訊息路徑。

重訓狀態會額外寫入：

- `metadata.retrain.previous_model`: 重訓前正式模型 path / mtime / sha256。
- `metadata.retrain.backup_model`: 本次備份模型 path / mtime / sha256。
- `metadata.retrain.new_model`: 新模型 path / mtime / sha256 / feature_count / sha256_changed。
- `metadata.retrain.promotion_gate`: auto/scheduled retrain 的 PSI / factor gate 判定與 blocked reasons。
- `metadata.retrain.rollback`: 若訓練後驗證失敗，記錄回滾來源與原因。

測試指定日期 gate 可用：

```bash
TOP10_RUN_DATE=2026-05-23 uv run --with-requirements requirements.txt python -m scripts.run_automation daily --dry-run
```

### `scripts/run_reference_update.sh`
**功能**: 每月 reference sources 更新 (每月 1 日 03:30)
**流程**:
1. `scripts/probe_reference_sources.py` 檢查 Yahoo / Goodinfo / PChome / WantGoo / MoneyDJ / 財報狗 / 櫃買中心來源是否可抓。
2. `scripts/import_reference_sources.py --allow-partial` 抓取成功來源、保留 raw HTML 到 `data/raw/reference/YYYY-MM-DD/`。
3. 產出標準化 CSV：
   - `data/reference/stock_concept_membership.csv`
   - `data/reference/concept_taxonomy.csv`
   - `data/reference/concept_alias_map.csv`
   - `data/reference/reference_source_audit.csv`
4. 產出 audit artifact：
   - `artifacts/reference_source_probe.json`
   - `artifacts/reference_import_summary.json`

此流程不即時影響 ranking score；產業/概念/ETF 維度先作為 UI 與風險揭露資料。

### `app.pipeline_cli`
**功能**: ETL 與資料產物維護入口
```bash
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate --json
uv run --with-requirements requirements.txt python -m app.pipeline_cli repair-local
```

`repair-local` 只使用既有 `data/clean/features.parquet` 重建衍生產物，不會抓外部 API；適合在缺 `events.parquet` 或 `universe.parquet` 時快速修復本地狀態。

### `app/model_monitor.py`
**功能**: PSI 漂移監控
**用法**:
```bash
# 手動執行監控
python app/model_monitor.py

# 查看結果
cat artifacts/psi_report.json
```

**說明**: PSI (Population Stability Index) 用於偵測特徵分佈變化
- PSI < 0.1: 穩定
- 0.1 < PSI < 0.25: 輕微變化
- PSI > 0.25: 需注意 ⚠️
- PSI > 0.5: 嚴重漂移 🚨 (建議重訓)

### `scripts/monitor_industry_momentum.py`
**功能**: M13 產業動能 shadow monitor

```bash
uv run --with-requirements requirements.txt python scripts/monitor_industry_momentum.py
```

此腳本會重跑 `scripts/research_industry_momentum_walkforward.py`，更新：

- `artifacts/industry_momentum_walkforward_shadow.json`
- `artifacts/industry_momentum_walkforward_shadow.md`

輸出只作為離線監控與研究證據，不會修改 production ranking、LightGBM feature list、API contract 或 weekly 推薦文案。

### `scripts/generate_model_health_report.py`
**功能**: M11 模型健康總覽
**用法**:
```bash
uv run --with-requirements requirements.txt python scripts/generate_model_health_report.py
```

只讀 `models/latest_lgbm.pkl`、`artifacts/ranking_*.csv`、PSI / factor / industry monitor artifact 與 `data/clean/features.parquet`，輸出：

- `artifacts/model_health_report_YYYY-MM-DD.json`
- `artifacts/model_health_report_latest.json`

此報告會標記模型檔、ranking artifact、monitor 狀態與已成熟 ranking 的 realized outcome。若 latest ranking 尚未滿足 horizon，會列為 pending，不當作流程失敗。

模型組總驗收可用：

```bash
uv run --with-requirements requirements.txt python scripts/verify_model_group_acceptance.py
```

它會重跑模型底座、review regression、data contracts、model health、rollback gate 等只讀驗證，並輸出 `artifacts/model_group_acceptance_YYYY-MM-DD.json`。`status=OK` 代表模型組驗收入口可營運；`auto_retrain_readiness=BLOCKED` 代表仍不可開啟自動重訓。

---

## ⚙️ 設定檔

### `config/automation.yaml`

```yaml
daily:
  run_time: "22:00"
  weekend_enabled: false
  max_data_lag_days: 7
  
retrain:
  schedule: "manual"
  time: "02:00"
  backup_keep_days: 30
  rollback_on_failure: true
  ranking_smoke_enabled: true
  monitor_after_train_enabled: true
  promotion_gate_enabled: true
  promotion_gate_block_triggers: ["auto", "scheduled"]
  promotion_gate_block_psi_statuses: ["CRITICAL"]
  promotion_gate_block_factor_statuses: ["WARN"]
  promotion_gate_max_factor_warn_count: 0
  min_feature_count: 50
  
monitor:
  psi_warning: 0.25
  psi_critical: 0.5
```

**修改後需重新載入排程**:
```bash
bash scripts/setup_launchd.sh
```

---

## 🔧 管理指令

### 停用排程
```bash
launchctl unload ~/Library/LaunchAgents/com.new-top10.daily.plist
launchctl unload ~/Library/LaunchAgents/com.new-top10.retrain.plist
```

### 重新啟用排程
```bash
launchctl load ~/Library/LaunchAgents/com.new-top10.daily.plist
launchctl load ~/Library/LaunchAgents/com.new-top10.retrain.plist
```

### 查看排程狀態
```bash
launchctl list | grep new-top10
```

### 手動觸發執行（測試用）
```bash
launchctl start com.new-top10.daily
launchctl start com.new-top10.retrain
```

---

## 📂 檔案結構

```
NEW-TOP10/
├── scripts/
│   ├── run_daily.sh              # 每日執行腳本
│   ├── daily_retrain.sh          # PSI 監控/手動重訓腳本
│   ├── run_automation.py         # 自動化統一入口
│   ├── setup_launchd.sh          # launchd 安裝
│   ├── setup_cron.sh             # cron 安裝 (備選)
│   ├── com.new-top10.daily.plist  # launchd 設定
│   └── com.new-top10.retrain.plist
│
├── app/
│   └── model_monitor.py          # PSI 監控模組
│
├── config/
│   └── automation.yaml           # 自動化設定
│
├── logs/                         # 日誌目錄
│   ├── daily_20260120.log
│   ├── retrain_20260120.log
│   ├── launchd_daily.log
│   └── launchd_retrain.log
│
└── models/
    ├── latest_lgbm.pkl           # 最新模型
    └── backup/                   # 模型備份
        └── lgbm_20260120_020000.pkl
```

`artifacts/automation_status.json` 會保留最近一次自動化執行狀態，適合 API 或 UI 顯示健康狀態。

---

## ❓ 常見問題

### Q: 如何確認排程是否正常執行？
查看日誌檔案：
```bash
ls -lh logs/
tail -50 logs/daily_$(date +%Y%m%d).log
```

### Q: 如何停止自動化？
```bash
launchctl unload ~/Library/LaunchAgents/com.new-top10.*.plist
```

### Q: 電腦關機後排程會失效嗎？
不會。launchd 會在開機後自動載入排程。

### Q: 如何改變執行時間？
1. 修改 `config/automation.yaml`
2. 重新執行 `bash scripts/setup_launchd.sh`

### Q: 模型備份存放在哪？
`models/backup/`，自動保留最近 30 天。

---

## 🔐 安全建議

1. **定期檢查日誌**: 確保執行正常
2. **備份重要檔案**: `models/`, `data/clean/`
3. **監控 PSI 報告**: 若持續漂移，需人工介入

---

## 📞 支援

若遇到問題，請檢查：
1. 日誌檔案 (`logs/`)
2. PSI 監控報告 (`artifacts/psi_report.json`)
3. 自動化狀態檔 (`artifacts/automation_status.json`)
4. 確認 `uv run --with-requirements requirements.txt ...` 可正常建立執行環境

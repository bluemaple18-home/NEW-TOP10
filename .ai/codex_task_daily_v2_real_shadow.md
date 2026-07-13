---
id: INTEGRATE-05
status: completed
type: integration
priority: P0
model: gpt-5.6-sol
---

# 每日報牌 v2 正式資料 shadow 對照

## 目標

把既有 v2 shadow workflow 接到 `StockRanker` 的正式資料／模型讀取路徑，產生完全隔離的排名與新舊比較證據。這張卡只建立 real-data adapter 與測試，不切換 production entrypoint。

## 最小成功條件

- 可指定交易日、正式 features／model 來源、baseline ranking 與 shadow workspace。
- `StockRanker` 必須以 shadow `artifact_dir` 執行，正式 features／model 只讀。
- 模型載入失敗必須終止；禁止沿用 `app/agent_b_ranking.py` 主程式捕捉後繼續的行為。
- 輸出 shadow ranking、run manifest、comparison JSON；所有新產物只能位於指定 shadow run 目錄。
- comparison 至少記錄：input SHA-256、schema 差異、Top10 overlap、逐股 rank 變化、共同數值欄位差異與結論。

## 可改檔案

- `app/workflows/` 的 real-data adapter／comparison 新模組。
- `app/contracts/` 的 comparison 契約新模組。
- `scripts/run_daily_v2.py` 的 real-data 參數與薄入口。
- `tests/test_daily_v2_real_shadow.py` 與必要 fixture。
- 本任務檔的 status／result。

除非測試證明無法安全注入 shadow `artifact_dir`，否則不得修改 `app/agent_b_ranking.py`。若真的必須修改，先停止並在原對話框回報理由，不自行擴權。

## 不可改檔案與行為

- `scripts/run_daily.sh`
- `scripts/run_daily_publish.sh`
- `scripts/com.new-top10.daily.plist`
- `config/automation.yaml`
- `data/clean/`、`models/`、既有 `artifacts/ranking_*.csv`、`artifacts/daily_report_*.json`
- 不得跑 ETL、不得發送 Clawd／Discord、不得 reload launchd、不得切換正式排程。

## 正式資料主線驗收契約

主線會在 canonical checkout 使用最近同時具有 features 與 baseline ranking 的日期執行。第一個目標日期為 `2026-07-09`：

```bash
.venv/bin/python scripts/run_daily_v2.py \
  --dry-run \
  --source real \
  --run-date 2026-07-09 \
  --data-dir data/clean \
  --model-dir models \
  --baseline-ranking artifacts/ranking_2026-07-09.csv \
  --workspace artifacts/shadow/daily_v2
```

worktree 沒有 ignored 正式資料時，只做 fixture 實作與測試；不得複製、修改或生成假正式證據。真正 real-data 執行由主線整合後完成。

## GO／NO-GO

- `GO`：Top10 stock IDs 10/10 相同且順序完全相同；共同核心分數欄位在明確 tolerance 內；schema 沒有阻塞差異；production 檔案執行前後 hash／mtime 不變。
- `NO-GO`：模型不可載入、指定日期不存在、Top10 不完整、順序不同、核心分數超出 tolerance、comparison 缺證據，或任何 production artifact 被修改。
- 即使 `GO`，本卡也不得切換 production；正式切換另開 acceptance／rollout 卡。

## Runtime 相容限制

- 正式主機目前 daily runtime 為 Python 3.12.12、scikit-learn 1.9.0；`latest_lgbm.pkl` 的 calibrator 是由 scikit-learn 1.8.0 保存，載入會產生 `InconsistentVersionWarning`。
- real-data adapter 必須捕捉並寫入這類 model compatibility warning、runtime 套件版本與 comparison 結論；不得靜默忽略。
- 本卡禁止執行會自動同步／改寫 canonical `.venv` 的 `uv run` 或 `uv sync`。主線 real-data 驗收固定使用既有 `.venv/bin/python`。
- 版本不一致時允許產生 shadow 比較證據，但 production switch 一律維持 `NO-GO`，直到另卡完成模型／runtime 對齊。

## 必跑測試

- 真模型載入失敗 fail-loud。
- 指定交易日不存在 fail-loud。
- shadow output 不得逃出 workspace。
- baseline schema／Top10 不一致時 comparison 明確 NO-GO。
- 完全一致 fixture 回傳 GO。
- `git diff --check` 與 diff 範圍檢查。

## 回報

- 變更檔案與設計邊界。
- 測試證據與未驗證原因。
- 交給主線執行的精確 real-data 指令。
- 不 commit、不 merge、不 push。

## 主線真資料結果

- run date：`2026-07-09`
- shadow comparison：`NO-GO`
- Top10：10／10 相同、順序完全相同。
- 核心分數：8 個共同核心欄位最大 absolute difference 全為 `0.0`。
- production inputs 與 live daily 控制檔 hash／mtime：執行前後不變。
- blockers：legacy ranking 無 `rank` 欄、6 個 allowlisted strategy-route 新欄、sklearn 1.8→1.9 model compatibility warning。
- production switch：未執行。

## 最終主線驗收

- comparator 修復後重跑：`artifacts/shadow/daily_v2/daily-v2-20260709-real-shadow-v2/`。
- 舊正式模型的 comparison 為 `GO`：Top10 10／10、順序完全一致、29 個共同數值欄位皆在 tolerance 內；production switch 只因 sklearn 版本 warning 維持 `NO-GO`。
- runtime migration candidate 重跑：`artifacts/shadow/daily_v2/daily-v2-20260709-candidate-v3/`。
- candidate comparison 與 production-switch gate 皆為 `GO`；8 個核心分數欄位最大 absolute difference 全為 `0.0`，模型相容警告為 0。
- `scripts/run_daily.sh`、`scripts/run_daily_publish.sh`、launchd plist、automation config、正式 model／features／baseline ranking 的 hash／mtime 全程不變。
- 本卡仍未切換 production；正式替換由 `MODEL-PROMOTE-07` 負責。

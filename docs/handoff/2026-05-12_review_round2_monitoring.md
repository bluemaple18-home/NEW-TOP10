# 2026-05-12 Review Round 2：資料修補 + M11 Factor Monitor

## Root Question

請針對上一輪 code review 後的修補，以及新增的 M11 factor monitor 做 code review。

重點：

- Automation 是否能正確 fail fast。
- Ranking 是否不再被 timestamp 不一致影響。
- Walk-forward/Optuna 是否避免 label leakage。
- Latest ranking 是否按交易日排序。
- Fundamental cache 是否防 path traversal。
- Factor monitor 的 IC / coverage / turnover 是否有 look-ahead 或定義問題。

## 上一輪 Findings 已修

### P1 Automation 誤判成功

修補：

- `app/agent_b_ranking.py`：`run_ranking()` catch 後 re-raise；缺 `features.parquet` 會 exit code `1`。
- `app/agent_b_modeling.py`：`main()` 失敗會 `return 1`，`__main__` 用 `SystemExit(main())`。

驗證：

- 缺 features 的 ranking smoke 已確認 exit code `1`。
- `scripts.run_automation daily --dry-run` 仍通過。

### P2 Ranking timestamp 掉股票

修補：

- `app/agent_b_ranking.py`：features/events/universe 全部建立 `trade_date = date.dt.normalize()`。
- 選日、events merge、universe filter、輸出檔名都改用 `trade_date`。

驗證：

- `scripts/verify_review_fixes.py` 建立同交易日不同 timestamp 的兩檔股票，確認兩檔都保留且 event merge 正確。

### P2 Walk-forward purge/embargo

修補：

- `app/agent_b_modeling.py`：新增 `_purge_train_dates()`，排除 train fold 最後 `horizon` 個交易日期。
- `walk_forward_train()` 使用 purge 後的 train dates。
- `optimize_params()` 可傳入 `dates`，80/20 split 後也會 purge train 尾端與 validation overlap。

請 reviewer 特別看：

- `_purge_train_dates()` 目前用「交易日期數」而不是自然日，是否符合預期。
- `optimize_params()` 仍是簡化 80/20，雖有 purge，但是否要長期改成 walk-forward objective。

### P2 latest ranking mtime

修補：

- `app/data/market_repository.py`：`load_latest_ranking()` 改用 `ranking_YYYY-MM-DD.csv` 檔名日期排序，mtime 只作 tie-breaker。

驗證：

- `scripts/verify_review_fixes.py` 人工製造 mtime 反向案例，確認會選檔名較新的交易日。

### P3 fundamental cache path traversal

修補：

- `app/data/fundamental_repository.py`：stock_id 加 regex 白名單 `[0-9A-Za-z._-]{1,20}`。
- cache path resolve 後確認在 `data/fundamentals` 底下。

驗證：

- `scripts/verify_review_fixes.py` 確認 `../evil` 被拒絕。

## 新增 M11 Factor Monitor

新增檔案：

- `app/monitoring/factor_monitor.py`
- `app/monitoring/__init__.py`
- `scripts/monitor_factors.py`
- `app/contracts/monitoring.py`
- `app/data/monitoring_repository.py`
- `app/services/monitoring_service.py`
- `app/api/routers/monitoring.py`

接線：

- `scripts/run_automation.py` 的 `monitor` 模式現在會跑：
  - `python -m app.model_monitor`
  - `python scripts/monitor_factors.py`
- `app/api/main.py` 新增 `/api/monitoring/factors`

設計：

- Factor monitor 是離線計算，輸出 `artifacts/factor_monitor_report.json`。
- API 只讀 artifact，不同步重算。
- 計算項目：
  - `coverage`
  - `latest_coverage`
  - Spearman `ic`
  - `recent_ic`
  - `turnover`
  - `observations`
  - `status`

目前 smoke 結果：

- `scripts/monitor_factors.py` → `FACTOR_MONITOR_WARN factors=38 warns=17`
- `/api/monitoring/factors` → `available=True, status=WARN, factor_count=38`

## Reviewer 建議優先看

### 1. `app/monitoring/factor_monitor.py`

請看：

- `LabelGenerator` 產生 future return 後，IC 是否只用當日 factor 對未來 return，沒有 accidental future feature。
- `events.parquet` merge 使用 `trade_date + stock_id` 是否可能造成重複列。
- `_factor_turnover()` 對 binary event 與 continuous factor 的 turnover 定義是否合理。
- `status` 門檻是否太鬆或太嚴。
- 目前只取最多 60 個 factors，是否需要明確白名單。

### 2. `app/agent_b_modeling.py`

請看：

- purge 邏輯是否足以消除 D+1/D+N label leakage。
- `optimize_params()` 的 dates 對齊 `X.index` 是否可靠。
- 若 purge 後 X_t empty，objective 回 `0` 是否合理。

### 3. `app/agent_b_ranking.py`

請看：

- `trade_date` merge 是否會在同 stock 同 trade_date 有多筆 features 時 duplicated。
- `run_ranking()` re-raise 是否會影響互動式手動執行體驗，但對 automation 是必要的。

### 4. `scripts/run_automation.py`

請看：

- `factor.monitor` fail 時整個 `monitor` 是否應 fail。現在是 yes。
- daily/retrain/status 的狀態檔是否符合預期。

### 5. `app/data/fundamental_repository.py`

請看：

- regex 是否應只允許台股數字代號，或保留 ETF/特殊代號彈性。

## 已驗證指令

```bash
uv run --with-requirements requirements.txt python scripts/verify_review_fixes.py
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate
uv run --with-requirements requirements.txt python -m scripts.run_automation daily --dry-run
uv run --with-requirements requirements.txt python -m app.agent_b_ranking
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
uv run --with-requirements requirements.txt python scripts/monitor_factors.py
uv run --with-requirements requirements.txt python -c "from fastapi.testclient import TestClient; from app.api.main import app; c=TestClient(app); print(c.get('/api/monitoring/factors').status_code)"
```

結果摘要：

- `verify_review_fixes.py` → `REVIEW_FIXES_OK`
- `app.pipeline_cli validate` → features/events/universe 全 OK
- `app.agent_b_ranking` → OK，產出 `artifacts/ranking_2026-01-20.csv`
- `verify_model_foundation.py` → `MODEL_FOUNDATION_OK specs=11`
- `monitor_factors.py` → `FACTOR_MONITOR_WARN factors=38 warns=17`
- `/api/monitoring/factors` → `200`

## 尚未做

- 尚未把 factor monitor 結果接 UI。
- 尚未把 factor IC 自動反映到 ranking 權重。
- 尚未建立近期 hit rate / realized performance monitor。
- 尚未對 Goodinfo 做真實網站抓取驗證。
- 尚未跑真實模型重訓。
- 尚未跑真實外部 ETL。

## Known Risks

- Factor IC 是全樣本 Spearman，目前沒有分 market regime 或產業中性化。
- Recent IC 使用最近 60 日自然日，不是最近 N 個交易日。
- Turnover 定義是初版，binary event 與 continuous factor 都可能需要更嚴謹。
- `optimize_params()` 還不是完整 walk-forward objective，只是 80/20 + purge。
- `repair-local` 仍會改寫 `data/clean/features.parquet`，上一輪已列為可 review 風險。

## 下一步建議

若 reviewer 同意目前修補：

1. 做 M11 phase 2：近期 hit rate、factor by regime、factor by market cap/liquidity bucket。
2. 再做 M9 投組配置模型：Top10 權重、總曝險、單股上限。
3. 最後再回到 UI，呈現 ranking、factor evidence、trade plan、fundamentals。

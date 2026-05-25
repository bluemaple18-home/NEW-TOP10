# TOP10new 快速啟動

## 1. 安裝環境

```bash
cd /Users/matt/TOP10new
uv sync
pnpm --dir web/frontend install
```

## 2. 重建資料

資料不放進 Git；新主機 clone 後請重新跑 daily 或 ETL。

```bash
uv run --with-requirements requirements.txt python -m app.pipeline_cli run
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate
```

## 3. 正式每日篩選

```bash
bash scripts/run_daily.sh
```

成功後會產出：

- `artifacts/ranking_YYYY-MM-DD.csv`
- `artifacts/weekly_candidate_snapshot_YYYY-MM-DD.json`
- `artifacts/daily_report_YYYY-MM-DD.json`
- `artifacts/clawd_publish_payload_YYYY-MM-DD.json`

## 4. 啟動本機 UI

```bash
bash scripts/start_ui.sh
```

瀏覽器開啟：

```text
http://127.0.0.1:5173
```

## 5. Clawd 發送狀態

預設安全狀態是不自動發送：

```yaml
notify:
  clawd_enabled: false
  clawd_dry_run: true
```

手動測試 dry-run：

```bash
uv run --with-requirements requirements.txt python scripts/send_clawd_publish_message.py --date YYYY-MM-DD
```

正式送出必須另外打開 config gate 並加 `--send`，不要接成自動每日發送，除非另開卡驗收。

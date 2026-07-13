# TOP10new 快速啟動

## 1. 安裝環境

```bash
# 在 clone 後的專案根目錄執行
uv sync --all-groups
pnpm --dir web/frontend install
```

`pyproject.toml` 與 `uv.lock` 是 Python 相依的唯一來源；`requirements.txt` 只供舊版外部工具相容使用。

## 2. 重建資料

資料不放進 Git；新主機 clone 後請重新跑 daily 或 ETL。

```bash
uv run python -m app.pipeline_cli run
uv run python -m app.pipeline_cli validate
```

## 3. 每日流程與 live send 狀態

```bash
# 僅跑 daily 資料、排名與 payload，不發送訊息
bash scripts/run_daily.sh
```

成功後會產出：

- `artifacts/ranking_YYYY-MM-DD.csv`
- `artifacts/weekly_candidate_snapshot_YYYY-MM-DD.json`
- `artifacts/daily_report_YYYY-MM-DD.json`
- `artifacts/clawd_publish_payload_YYYY-MM-DD.json`

目前 `config/automation.yaml` 的 `notify.clawd_enabled` 為 `true`，
且 `notify.clawd_dry_run` 為 `false`。因此 `scripts/run_daily_publish.sh` 會在 daily 成功後嘗試正式發送，
本機 dry-run 或驗證時不可使用該 wrapper。本卡不變更此設定。

## 4. 啟動本機 UI

```bash
bash scripts/start_ui.sh
```

瀏覽器開啟：

```text
http://127.0.0.1:5173
```

## 5. Clawd payload dry-run

不送出的 payload 檢查可用：

```bash
uv run python scripts/send_clawd_publish_message.py --date YYYY-MM-DD
```

它沒有 `--send`，不會觸發正式送出；實際 send 仍受目前設定與 `--send` 雙重控制。

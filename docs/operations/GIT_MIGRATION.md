# Git Migration Notes

## 目的

這個 repo 用來搬移 Top10 主程式、設定、文件與目前的小型模型檔。資料可在新主機重抓或重建，因此 `data/*` 不放進 Git。

## 會進 Git

- `app/`
- `scripts/`
- `config/`
- `docs/`
- `web/frontend/src` 與前端設定檔
- `models/latest_lgbm.pkl`
- `models/baseline_stats.json`

## 不進 Git

- `.venv/`
- `web/frontend/node_modules/`
- `web/frontend/dist/`
- `data/clean/`
- `data/raw/`
- `data/reference/`
- `data/fundamentals/`
- `data/test/`
- `artifacts/`
- `logs/`
- `mlruns/`
- `mlflow.db`

## 新主機恢復順序

1. `uv sync`
2. `pnpm --dir web/frontend install`
3. 確認 `models/latest_lgbm.pkl` 存在
4. 重跑 daily 或 ETL 產生 `data/clean/*`
5. 需要看 UI 時執行 `bash scripts/start_ui.sh`

## Clawd 發送安全狀態

目前 `config/automation.yaml` 保持：

```yaml
notify:
  clawd_enabled: false
  clawd_dry_run: true
```

搬家後預設不會自動發 Discord。正式發送仍需手動打開 gate 並執行 `scripts/send_clawd_publish_message.py --send`。

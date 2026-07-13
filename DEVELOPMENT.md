# 雙機協作開發規則

## 分工說明

本專案由兩台電腦共同開發：
- **主電腦**：負責 UI/UX 介面設計
- **Mini**：負責 ML 演算法與模型訓練

---

## 檔案所有權

### 🎨 主電腦專屬 (UI/UX)
```
web/frontend/                ← React + KLineCharts 看盤介面
app/api/                     ← FastAPI 看盤資料 API
app/reason_generator.py      ← 理由生成
app/glossary.py              ← 名詞解釋
app/dashboard_renderer.py    ← 圖表渲染
app/etl_pipeline.py          ← 資料管線 (共用區主導)
app/data_fetcher.py          ← 資料抓取 (共用區主導)
app/publish_daily.py         ← 每日發布 (共用區主導)
static/*                     ← 靜態資源
templates/*                  ← 模板
```

### 🤖 Mini 專屬 (ML/演算法)
```
app/indicators.py            ← 技術指標
app/agent_b_modeling.py      ← 模型訓練
app/agent_b_ranking.py       ← 排名邏輯
app/fundamental_data.py      ← 基本面資料
app/event_detector.py        ← 事件偵測
app/risk_filter.py           ← 風險過濾
app/volume_indicators.py     ← 量能指標
models/*                     ← 訓練模型
run_agent_b.py               ← 訓練腳本
```

---

## 本機開發流程

### 建立環境

```bash
uv sync --all-groups
pnpm --dir web/frontend install
```

Python 相依以 `pyproject.toml` 與 `uv.lock` 為準；`requirements.txt` 只保留給舊版外部工具。

### 常用驗證入口

```bash
uv run python -m app.pipeline_cli validate
uv run python -m app.agent_b_ranking
uv run --group training python -c "import app.agent_b_modeling"
```

每日流程排定於 17:30。`bash scripts/run_daily.sh` 只產生 daily 結果與 payload；
`scripts/run_daily_publish.sh` 會依目前通知設定處理正式發送，非本機開發預設入口。

---

## 衝突處理

如果遇到衝突：
1. 先溝通確認誰的版本為準
2. 手動解決衝突後執行 `git add .` 和 `git rebase --continue`
3. 再次推送

---

## 重要提醒

⚠️ **不要修改不屬於你的檔案！**

如需跨區域修改，請先在 GitHub Issues 或訊息中討論。

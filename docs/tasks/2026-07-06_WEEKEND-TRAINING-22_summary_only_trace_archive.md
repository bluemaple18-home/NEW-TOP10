# WEEKEND-TRAINING-22｜Summary-Only 主線與逐筆追溯封存

## 目的

把 weekend training burn-down artifacts 分成兩層：

- 主線層：summary / rollup / gates / fog map verifier，用於日常研究與驗證。
- 追溯層：完整 records 冷封存，只在人工 debug 歷史日期時使用。

這個切分避免每次研究都產生或讀取 1GB+ JSON，同時保留必要的歷史逐筆追查能力。

## 主線契約

日常流程預設使用 summary-only inventory：

```bash
.venv/bin/python scripts/build_weekend_universe_inventory.py --date <YYYY-MM-DD>
.venv/bin/python scripts/verify_weekend_universe_inventory.py --date <YYYY-MM-DD>
.venv/bin/python scripts/run_controlled_grid_drain_host_runner.py --date <YYYY-MM-DD>
.venv/bin/python scripts/verify_research_fog_map.py --date <YYYY-MM-DD>
```

`weekend_universe_inventory_<date>.json` 預設不內嵌 `records`，並以：

```json
{"contract": {"records_inline": false}}
```

宣告該 artifact 是主線 summary artifact。

## 追溯契約

只有需要人工查歷史單筆 combo/topic 時，才使用完整 records artifact：

- `weekend_universe_inventory_<date>.json.gz`
- `weekend_frontier_queue_<date>.json.gz`
- 或臨時用 `--include-records` 重建完整 JSON

追溯工具：

```bash
.venv/bin/python scripts/trace_weekend_training_artifact.py --date <YYYY-MM-DD> --combo-id <combo_id>
.venv/bin/python scripts/trace_weekend_training_artifact.py --date <YYYY-MM-DD> --topic-id <topic_id> --limit 5
```

這支工具串流讀取 `.json` / `.json.gz` / `.json.zst`，不需要先把冷封存解壓回 1GB+ 原檔。

## 封存政策

大型 full records JSON 不應長期留在主線 artifact 目錄中。若需要保留追溯能力，使用：

```bash
.venv/bin/python scripts/cleanup_weekend_training_full_artifacts.py \
  --keep-latest-dates 1 \
  --keep-date <YYYY-MM-DD> \
  --action compress \
  --compression gzip \
  --no-delete-expired-archives \
  --execute
```

注意：

- `--keep-date` 用來保護當天主線 summary artifact。
- 壓縮封存不代表 production change。
- 解壓或重建 full records 只能作人工排查，不得成為 fog map verifier 的必要依賴。

## 驗收

- 主線 verifier 不依賴 full records。
- `controlled_grid_drain_gates_<date>.json` 可從 summary inventory 產生。
- 大型 full JSON 可壓縮封存，且封存後 `verify_research_fog_map.py` 仍為 OK。
- 需要查單筆時，用 `trace_weekend_training_artifact.py` 從封存檔串流追溯。


# 寫入盤點、主機基線與 provisional budget

## 2026-08-03 唯讀主機基線

- `/System/Volumes/Data`：239,362,496 KiB total、62,765,400 KiB available、71% used。
- swap：2,048.00 MiB total、653.25 MiB used、1,394.75 MiB free。
- live checkout 的 `logs + artifacts + data + models`：2,597,997,449 apparent bytes、
  32,495 regular files。
- allocated blocks：`logs` 16,636 KiB、`artifacts` 1,755,440 KiB、`data` 833,284 KiB、
  `models` 17,728 KiB；`.venv` 726,176 KiB（不列入 job 產物 meter）。
- 較大現況路徑：`data/fundamental_xbrl` 604,956 KiB、`artifacts/archive` 335,332 KiB、
  `artifacts/autonomous_research` 325,020 KiB、`artifacts/backtest` 323,068 KiB、
  `artifacts/model_experiments` 264,848 KiB、`artifacts/weekend_training` 205,060 KiB。
- `artifacts/autonomous_research/run_history.jsonl` 為 37,840,014 bytes，屬另一個需要在
  代表性週期量測的單檔增長點；本卡未在無實測下臆測其 retention。
- 八個 `com.new-top10.*` launchd job 全部 disabled；`pgrep` 沒有匹配的 TOP10 排程程序。
- `lsof +L1` 過濾 TOP10new 沒有匹配，未見本專案 open-deleted file。

主機目前已高於啟動空間門檻，但禁止 live 的理由不是空間不足，而是八個 job 尚未完成
本修復版兩個代表性完整週期，policy 的 `launch_verified` 仍為 false。

## 八入口與主要寫入面

| job | 原入口／子流程 | 主要 meter／寫入 |
|---|---|---|
| daily | `run_daily_publish.sh` → `run_daily.sh` → automation／shadow／status | `logs/`、`data/`、`artifacts/`、`models/` |
| retrain | `daily_retrain.sh monitor --trigger scheduled` → retrain automation | `logs/`、`data/`、`models/`、`artifacts/model_experiments/` |
| reference | `run_reference_update.sh` → reference automation | `logs/`、`data/reference/`、`data/raw/reference/`、reference artifacts |
| fog-research-worker | fog batches → handoff → daily quota；完成後可進 replay drain | autonomous research、harness status、weekend replay、research map／reviews、logs |
| pm-research-harness | PM loop、continuations、discovery／cards | autonomous research、harness status、weekend training、PM cards／decisions、logs |
| external-review | host runner → provider workflow／fog handoff | external review、autonomous research、weekend training、harness、research map、logs |
| external-review-preflight | provider preflight | external review artifacts、logs；瀏覽器資料明確不在本卡 scope |
| baseline-harness | baseline host runner | weekend training、backtest、harness status、logs |

每條排程另有 job-specific `logs/storage_safety/runtime/<job>/`，容納 temp 與下載型 cache，
避免使用者層 cache 成為未量測寫入。

## Provisional ceilings（不是 live 核准值）

| job | max bytes | max files | expected growth/hour | spike | stabilize | reclaim | retention |
|---|---:|---:|---:|---:|---:|---:|---:|
| daily | 6 GiB | 60,000 | 512 MiB | 2 h | 4 h | 24 h | 14 d |
| retrain | 8 GiB | 75,000 | 1 GiB | 4 h | 6 h | 24 h | 14 d |
| reference | 4 GiB | 45,000 | 256 MiB | 2 h | 4 h | 24 h | 30 d |
| fog-research-worker | 2 GiB | 30,000 | 16 MiB | 4 h | 5 h | 24 h | 14 d |
| pm-research-harness | 2 GiB | 30,000 | 32 MiB | 4 h | 5 h | 24 h | 14 d |
| external-review | 2.5 GiB | 35,000 | 64 MiB | 4 h | 5 h | 24 h | 30 d |
| external-review-preflight | 512 MiB | 5,000 | 8 MiB | 1 h | 2 h | 24 h | 30 d |
| baseline-harness | 2 GiB | 25,000 | 256 MiB | 4 h | 5 h | 24 h | 14 d |

這些 ceiling 只用於 fail closed 與 bounded test contract。真正的 normal growth、一天／保留期
峰值與回收時間必須由每個 job 的兩個代表性週期產生；在此之前 policy 內逐 job 的
`verification_basis` 會保留缺口，所有 job 都是 `NO-GO`。

## 回收 allowlist

允許回收的只有 policy JSON 明列的 rebuildable paths：job runtime workspace、`.log`／`.err`、
research snapshots／run dirs、PM research outputs、harness status、weekend replay、baseline 與
external review outputs。`data/`、`models/`、archive、未知檔、瀏覽器與其他專案都不在刪除
allowlist。

fixture 回收演練建立兩個過期檔、一個最新檔與 scope 外 protected file；execute 後 bytes／
file count 下降，最新檔保留，protected file hash 不變。沒有對 live checkout 執行清理。

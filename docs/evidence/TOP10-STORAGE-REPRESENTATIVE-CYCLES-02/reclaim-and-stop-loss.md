# Reclaim 與隔離停損

## Allowlisted reclaim

Fog validation sandbox 在 child 啟動前實際執行 policy allowlist reclaim：

- bytes：`288277126 → 136592922`，實際回收 `151684204` bytes。
- files：`8808 → 2844`，實際移除 `5964` files。
- scope：只在本卡專屬、無 `.git` 的 sandbox 內；沒有對 main checkout 的
  `data/`、`artifacts/`、`models/` 執行清理。
- receipt：`receipts/fog-research-worker/cycle-1-stopped.json`。

Baseline 第一個嘗試另發現原 `baseline_outputs: baseline_*` 會把 unlock policy 一起回收。
已將規則限縮為 `baseline_harness_medium_window_replay_*` 並補 regression test；unlock policy、
review 與 verification control artifacts 不再匹配 reclaim。

## Hard-RSS stop-loss drill

在獨立 stop-loss sandbox 將 daily fixture hard RSS ceiling 設為 `16777216` bytes，以同一
validation guard 啟動只配置 64 MiB 的 child：

- guard 觀測 peak process-tree RSS `82853888` bytes。
- 觸發 `PROCESS_TREE_RSS_BUDGET_EXCEEDED`，child exit `-15`，guard exit `70`。
- persistent marker 為 `automatic_clear_allowed=false`。
- 第二次嘗試沒有啟動 child，exit `75 / RESTART_DENIED`。
- unrelated `sleep` 位於另一個 exec process group；停損前後 `kill -0` 都為成功，證明 target
  stop 沒有掃到獨立程序。驗證完成後才由本卡明確 TERM 該 unrelated fixture。

Machine evidence：

- `stop-loss/hard-rss-trigger.json`
- `stop-loss/restart-denied-marker.json`

## Protected state 與收尾

Main checkout 三個既存 dirty files 的 SHA-256 在 preflight 與 runtime 後完全相同：

- `c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`
- `ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`
- `f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`

收尾 process scan 與 `lsof +L1` 都沒有 TOP10 validation process/open-deleted file；八個
launchd labels 仍全部 disabled 且未出現在 `launchctl list`。

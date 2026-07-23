# RESEARCH-FUNDAMENTAL-READINESS-01 Result

## Decision

`BLOCKED_DATA_COVERAGE`

Fundamental 並非已證明無效。既有低覆蓋樣本呈現正向 IC／spread，但 cache 並非隨機樣本，不能外推成完整 universe 的選股加分依據。

## Evidence

- as of：`2026-07-23`
- feature universe：`1967` 檔
- usable fundamental stocks：`23` 檔（`1.17%`）
- latest point-in-time liquidity Top200：`3/200`（`1.50%`）
- 最近 252 個已成熟交易日：
  - 每日可用檔數：`3–5`，中位數 `4`
  - 每日 coverage：`1.50%–2.50%`，中位數 `2.00%`
  - 通過 research gate：`0/252`
- artifact SHA-256：`a5cb995aa58fec8ef527040793213aa14497f557e5c1c5628e6bc36d6bfacbc3`

## Acceptance

- builder：PASS
- independent recomputation verifier：PASS
- `git diff --check`：PASS
- production model／ranking／feature／權重：未修改
- 外部資料抓取：未執行

## Next authorized boundary

若要把基本面推進到正式研究，下一步不是跑更多組合，而是先取得合法、可持續、point-in-time 的批次資料來源，使最近 252 個成熟交易日每天至少 30 檔且 coverage 至少 70%，並使 cache stock coverage 達 80%。完成後才能重跑 walk-forward 與組合搜尋。

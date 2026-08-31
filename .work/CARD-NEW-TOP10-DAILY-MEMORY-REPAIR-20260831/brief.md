---
id: CARD-NEW-TOP10-DAILY-MEMORY-REPAIR-20260831
status: COMPLETE
type: implementation
---

# Daily Memory Repair

## Root question

能否在不改變 daily 排名、模型、資料契約、publish eligibility 與 storage guard 上限的前提下，將代表性 2026-08-31 daily 流程峰值 RSS 從 4,548,247,552 bytes 降到 4,026,531,840 bytes（3.75 GiB）以下？

## 已知失敗證據

- local-only receipt：`<main-checkout>/logs/storage_safety/daily_latest.json`
- status：`STOPPED`
- reason：`PROCESS_TREE_RSS_BUDGET_EXCEEDED`
- guard limit：`4,294,967,296 bytes`
- observed peak：`4,548,247,552 bytes`
- process group：`final_quiescent=true`
- ETL、features、universe 與 ranking 已產生；`automation_status` 未封口，message／payload／send receipt 未產生，Discord 未發送。

## 假說與 red-capable loop

先用 CodeGraph＋原始碼確認 daily ranking／explanation 的 public seam，再建立一個可重跑的 memory regression harness。至少比較下列可證偽假說：

1. ranking／SHAP explanation 同時保留全量 feature frame、轉換矩陣或解釋矩陣，造成峰值重疊。
2. post-ranking 報告／analysis 在 ranking heavy objects 尚未釋放時啟動，造成跨階段 lifetime overlap。
3. 其他 subprocess／worker fan-out 才是 RSS 加總來源；若是，修正應限制 fan-out 或縮短 object lifetime，不得提高 guard 上限。

RED 必須能對應「代表性 ranking path 的峰值或同一個 lifetime overlap 超過門檻」，不能只測函式有跑完。

## 允許範圍

- 經量測定位後，修改最小必要的 daily ranking／explanation／report memory lifetime seam。
- 補 memory regression test／harness 與本卡 evidence。
- 可讀 `<main-checkout>/data`、`artifacts/ranking_2026-08-31.csv` 與 guard receipt 作 local-only evidence；不得寫入 main checkout。

## 禁止範圍

- 不修改 `docs/operations/top10-storage-policy.json` 的任何 budget／threshold。
- 不繞過 guard、不直接發送 Discord、不跑 production publish。
- 不改模型、權重、特徵定義、ranking semantics、provider、scheduler、publish destination 或 Issue。
- 不碰 Research A4–A6、`.work/current`、main branch、push 或 merge。
- 不把部分 ranking 當可發布結果。

## 驗收

1. 已跑過一個可穩定 RED 的 memory regression loop。
2. 修復後同一 loop GREEN，且至少有一個 falsified hypothesis 記錄。
3. candidate ranking schema、row count、Top10 identity/order 與 key score fields 對修復前 golden evidence一致。
4. 代表性 profile／harness peak RSS ≤ 4,026,531,840 bytes；若本 worktree 無法安全執行完整代表性 cycle，明確回報 `FULL_GUARD_VALIDATION_PENDING`，不得宣稱完成。
5. 受影響測試通過，`git diff --check` 通過，無 `[DBG-` 殘留。
6. 單一 local candidate commit；回報 SHA、變更檔、RED/GREEN 命令與剩餘風險。

## Stop conditions

- 需要改 guard budget／policy 才能通過。
- 需要改 ranking semantics、模型、特徵或 production publish。
- 無法建立能對應原始 RSS 症狀的 red-capable loop。
- 來源顯示是跨模組架構問題，超出 bounded repair。

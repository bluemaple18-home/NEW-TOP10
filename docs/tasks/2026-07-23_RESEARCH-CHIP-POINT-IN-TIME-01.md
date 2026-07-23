---
id: RESEARCH-CHIP-POINT-IN-TIME-01
status: COMPLETED
type: evaluation
---

# Chip flow point-in-time restricted-universe 研究

## Root question

在每日只用當時 trailing 20D 成交額選出的 top-200 流動性股票中，法人籌碼訊號是否仍能通過嚴格 walk-forward？

## 已確認資料事實

- 全市場 `institutional_available` 約 10.45%，不可作全市場 chip-flow 研究。
- 2025-06-02～2026-06-24 的每日 point-in-time top-200 平均覆蓋約 80.1%。
- 243 日中有 231 日覆蓋至少 70%；不足日必須由現有 coverage gate 排除。
- `data/raw/chip/cache/` 有 60 日、221 檔、10,005 個唯一 institutional keys；與 features 同鍵且 available 時數值 100% 一致。
- raw cache 不能把日期延長到 100-day train window，也不能單獨解決完整歷史問題。

## 契約

- 先在完整股票歷史生成 10D label，再做每日 universe filter，禁止因進出 top-200 改變 horizon。
- universe 只能依該日已存在的 `avg_value_20d` 排序；禁止全期間平均成交額 cohort。
- chip-flow 衍生欄位仍必須服從 `institutional_available`，每日有效覆蓋至少 70%。
- 使用既有 append-only regime history、expanding folds 與 10-day embargo。
- 僅研究輸出；不改模型、production ranking、feature 或權重。

## Acceptance

- verifier 證明每日 universe 會依當日 rolling liquidity 重排。
- restricted universe 每日最多 200 檔，且 coverage receipt 可稽核。
- 若產生 candidate，仍只能進 portfolio replay，不能直接 promotion。
- 若沒有 candidate，輸出明確 NO-GO，停止 chip-flow replay。

## Portfolio replay 預註冊

- baseline：只用各 fold／regime 的 train-only `liquidity_activity` composite。
- overlay：只測固定 `10%` 與 `20%` chip rank；不依結果追加權重。
- 交易代理：每日 Top10、D+1 open 進場、D+10 close 出場，扣手續費、交易稅與滑價。
- 每個 overlay 必須同時滿足：平均 net return delta > 0、至少 3 個正 fold、turnover delta <= 0.10、平均最大產業曝險不惡化、每個 bucket 10 筆交易完整。
- 本 replay 與 IC gate 共用 OOS window，只是成本化診斷；即使通過也不得宣稱獨立驗證或直接 promotion。
- 若任一 baseline／overlay bucket 因市場級 OHLC 缺口不足 10 筆，該 ranking date 必須對所有 variant 成對排除並留下 receipt；禁止補值或單邊排除。
- baseline 與 overlay 都只在 chip score 有效的成對樣本上比較，避免兩邊股票池不同。

## 已發現資料缺口

- `2026-04-13` features 有 1,069 檔 TWSE、但 TPEX 為 0 筆，屬市場級來源缺口。
- 10D holding window 跨過該日的 8 個 ranking dates 必須成對排除，不能把缺檔當成策略失敗。

## Result

- point-in-time Top200 institutional coverage：平均 `80.1393%`。
- chip vs liquidity partial IC：`0.01109`，8 個穩定 fold/regime buckets 中 5 個為正。
- 成本化 replay：122 個可評分日中，8 日因已驗證 TPEX 市場級缺口成對排除，114 日納入。
- `10%` chip overlay：`SHADOW_CANDIDATE`；net return delta `+0.002740`、3/5 正 fold、turnover delta `+0.073451`、平均最大產業曝險 delta `-0.011404`。
- `20%` chip overlay：`REJECTED`；僅 2/5 正 fold且 turnover delta `+0.148672`。
- production：未修改；下一步只能累積新的獨立 shadow 日期，不能直接 promotion。

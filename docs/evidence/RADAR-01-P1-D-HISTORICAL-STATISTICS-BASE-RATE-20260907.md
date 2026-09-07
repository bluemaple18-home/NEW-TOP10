# RADAR-01 P1-D Historical Statistics / Base Rate 驗收證據

日期：2026-09-07
狀態：`MAINLINE_ACCEPTED_LOCAL / RE-REVIEW_GO / VALIDATION_REPLAY_VERIFIED / NON_RUNTIME`

## 驗收範圍

本卡建立一個 in-memory、read-only、content-addressed 的 signal historical statistics projection。它只消費 exact finalized Daily Close manifest、不可變 feature parquet、indicator semantics reference 與 `RADAR_ELIGIBLE` SignalSpec；不修改 Research Spine、Research Matrix、Existing Backtest Engine、ranking、writer、scheduler 或 production runtime。

## 資料與計算契約

- 代表性來源：`data/clean/features.parquet`。
- grain：每個 `date × stock_id` 一列；量測為 516,169 rows、1,967 stocks、2025-07-08 至 2026-09-01、TWSE/TPEX，duplicate=0、close null=0、close non-positive=0。
- price return：`UNADJUSTED_PRICE_RETURN`，不含股息、費用、稅與公司行動調整，不得解讀為 total return。
- outcome：依個股 observed sessions 取第 H 個後續 session；尾端不足明確排除。
- comparator：同 snapshot／universe／window／horizon／direction 的 unconditional complete-outcome baseline，caller 無法注入 comparator。
- dependence：`PER_INSTRUMENT_NON_OVERLAPPING_FORWARD_WINDOWS_V1`，同時保留 raw/effective/overlap counts；不宣稱獨立、顯著或因果。
- public error contract：malformed path、spec container 與 signal-column collision 均回穩定 `HIST_*` reason code，不洩漏 pandas／numpy native exception。

## 代表性重播

驗證用 snapshot 是從現有 parquet 暫時 materialize 的 local validation fixture，不是 official materialized Daily Close runtime receipt。為覆蓋計算路徑，只使用四個 initial specs 的 validation-only eligible clones；default catalog 未被修改。

- input snapshot id：`sha256:744ef762130d78e3606138b1dbbdc3ec073088eb73d75bf0a059458aada7c8e2`
- feature content id：`sha256:aab60603280ae3d2a603b705ab02c5b19f518dcf178080482b2500b221f954ce`
- result content id：`sha256:f583c279cc5c8e23e5b9c1755197f2a3dafe5020d07e0005e07a68220e7fec63`
- deterministic replay：相同 result content id，`true`。
- invariants：四個 signals 的 coverage count closure、raw/effective/overlap closure、incremental-rate-edge recomputation 與 result-id recomputation 全為 `true`。
- default catalog：`NO_RADAR_ELIGIBLE_SIGNAL_SPEC`，eligible=0、statistics=0。

| Signal | Direction | H | Conditional raw/effective/overlap | Conditional positive rate | Baseline positive rate | Rate edge |
|---|---:|---:|---:|---:|---:|---:|
| `ma5_cross_ma20_down` | BEARISH | 5 | 7,816 / 7,614 / 202 | 46.244% | 51.436% | -5.192 pp |
| `ma5_cross_ma20_up` | BULLISH | 5 | 8,331 / 8,123 / 208 | 42.201% | 45.474% | -3.272 pp |
| `rsi_break_below_50` | BEARISH | 5 | 26,003 / 21,284 / 4,719 | 48.877% | 51.436% | -2.558 pp |
| `rsi_rebound_from_40` | BULLISH | 5 | 19,627 / 16,275 / 3,352 | 44.406% | 45.474% | -1.068 pp |

這些數字是 contract replay，不是 signal promotion 或投資績效主張；四個 validation-only cases 的 rate edge 均未取得研究 authority。

原始可重跑證據：

- `docs/evidence/RADAR-01-P1-D-HISTORICAL-STATISTICS-BASE-RATE-20260907/representative_probe.py`
- `docs/evidence/RADAR-01-P1-D-HISTORICAL-STATISTICS-BASE-RATE-20260907/representative_result.json`

## Review / Repair chain

- strict candidate digest：`sha256:0a917c4e46c4179daf9649d524602fba126800b7e5ea90c335045ce8c39ad6cf`。
- 獨立 Reviewer 首輪：`REVIEW_NO_GO`；finding `RADAR-P1D-STRICT-001` 指出 public builder 可能洩漏 native exceptions。
- Repair 1：加入 signal-column collision、path type 與外部 iterable materialization 的 bounded validation；沒有 broad catch，也沒有更動 statistics／baseline／effective-N／MAE／scanner／eligibility／authority。
- 原 Reviewer targeted re-review：四個反例都得到 exact stable reason code；`RE_REVIEW_GO`，未解 P0/P1=0。
- finding ledger：`.work/RADAR-01-P1-D/review/review_state.jsonl`。

## 驗證結果

- task traceability：0 critical／0 warning。
- targeted＋P1-A～P1-C／Daily Close regression：98 passed。
- `python -m compileall app/signals`：PASS。
- `git diff --check`：PASS。
- representative replay：PASS。

## 限制與權限

- `VALIDATION_ONLY / NOT_OOS / NOT_SEALED`。
- `NO_ELIGIBILITY_OR_RANKING_AUTHORITY`；default eligible count=0。
- 沒有 official materialized runtime Daily Close snapshot，因此不得稱 live／production acceptance。
- 沒有顯著性、因果、regime robustness、transaction-cost 或 total-return claim。
- Matrix dimension delta=0；runtime／provider／publish／push／deploy impact=`NONE`。
- P1-D admission 已用畢並關閉；P1-E 需要新的 Owner 明確 admission。

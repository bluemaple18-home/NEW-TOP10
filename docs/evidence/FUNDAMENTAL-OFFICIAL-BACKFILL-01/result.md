---
id: FUNDAMENTAL-OFFICIAL-BACKFILL-01
status: completed
type: result
---

# FUNDAMENTAL-OFFICIAL-BACKFILL-01 Result

## 結果

- 來源：MOPS 官方季度 XBRL 整批檔。
- 回填期間：`2024Q4`–`2026Q1`，共 6 季。
- feature universe：`1,967` 檔。
- 可用 Fundamental：`1,963` 檔，coverage `99.80%`。
- 最新 Top200：`200/200`。
- 最近 252 個成熟交易日：`252/252` 通過 research gate。
- readiness：`READY_FOR_POINT_IN_TIME_RESEARCH`。

九個既有欄位的 feature-row coverage：

- ROE：`99.31%`
- 毛利率：`97.47%`
- 負債比：`99.78%`
- 營業利益率：`98.26%`
- 淨利率：`98.26%`
- 流動比率：`98.27%`
- ROA：`99.78%`
- 自由現金流：`99.78%`
- EPS：`99.78%`

## 完整 Universe Shadow

- 股票分數 coverage：`99.80%`
- feature score coverage：`99.78%`
- 10 日 IC：`0.0148`
- IC median：`0.0159`
- Top–Bottom spread：`-0.000413`
- ranking Top10 sensitivity overlap：`10/10`

結論：資料覆蓋 blocker 已解除，可以進行完整 point-in-time 研究；目前合成 Fundamental score 沒有足夠證據進 production ranking，不調權重。

## Point-in-time 限制

- 可用日採較晚保守政策：Q1 `6/1`、Q2 `8/30`、Q3 `11/30`、Q4 次年 `5/1`。
- 官方整批 XBRL 可能包含後續更補正後的目前版本，不是逐次申報版本快照。
- 因此適合作研究篩選，不得把本次 readiness 誤寫成 production promotion。

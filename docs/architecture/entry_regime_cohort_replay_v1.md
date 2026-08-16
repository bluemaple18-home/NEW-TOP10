# Entry-Regime Cohort Replay V1

## 決策

`SELECT_ENTRY_REGIME_COHORT_FOR_FEASIBILITY`

本架構只授權下一張 outcome-free、唯讀 feasibility audit。它不授權 replay、sealed outcome 開封、promotion、production 或 runtime cutover。

## 為何需要新契約

既有 exact-holding-regime 契約要求 ranking date、D+1 entry 與全部 h20 holding dates 位於同一 immutable episode。Current 與 legacy evidence 均為 0 個 h20-safe exact identity，因此該階段已正式關閉。

本契約把問題改成：

> 在 ranking date 當下可知的 exact entry regime cohort 條件下，h20 portfolio outcome呈現何種關聯？

這不是「持倉全程處於相同 regime」的證據，也不是 regime 對報酬的因果效果。

## 四案裁決

| 候選 | 決策 | 理由 |
|---|---|---|
| Entire-holding exact regime | 維持 NO-GO | 已有 committed closure evidence。 |
| 縮短 horizon | REJECT | 改變固定 h20 產品問題，不得默認。 |
| 合併 episode／base-only／忽略 transition | REJECT | 隱藏語意放寬，可能形成 false causal claim。 |
| Entry-regime cohort | SELECT FOR FEASIBILITY | 唯一同時保留 h20、D+1 與 as-of identity 的候選。 |

## 估計單位

- Primary grain：`ranking_date × scenario × top-N portfolio`。
- 個股 trade 是 portfolio outcome 的組成與診斷，不是獨立統計樣本。
- `entry_cohort_id` 只由 ranking date `D` 的 canonical regime row產生。
- 正式文案只能使用「entry cohort 條件下的 h20 關聯結果」。

## Selection eligibility

1. Ranking date固定為 `D`。
2. 只接受 `trade_date == as_of_date == D` 的 canonical regime row。
3. Exact identity維持 `base_regime + exact family tag set`。
4. `UNKNOWN`、`is_transition=true`、缺 row、taxonomy不合法、latest-row fallback全部 fail closed。
5. Selection只能讀 D 當下資料；D+1或 holding-period identity、price、outcome、path都不得改變 selection。
6. Ranking corpus、model/config、universe、top-N與 portfolio fingerprint必須在看 outcome 前 hash-bound。

## Entry 與 h20 outcome

- Entry：D 後第一個 market trade day開盤；`entry_delay_trade_days=1`。
- Horizon：從 entry 起算共 20 個 market trade bars，沿用 canonical replay helper 的 off-by-one語意。
- Primary endpoint候選：paired portfolio net excess return。
- Fee、tax、slippage、停牌、下市與缺 OHLC規則必須在 preregistration固定。
- 未來 bars不足或 OHLC缺失不得反向刪除 selection row；必須保留 selection並記錄結構化 exclusion。

## Holding regime path diagnostics

每個 outcome window記錄：

- 20 日逐日 exact identity或缺失狀態；
- `path_hash`；
- transition count與 first transition offset；
- days-by-identity；
- terminal identity；
- UNKNOWN／missing count。

Future path只能在 outcome完成後作描述性診斷。它不得：

- 改 cohort；
- 改 eligibility或 exclusion；
- 選參數、停止研究或加權；
- 形成 hypothesis、promotion或因果宣稱。

## 全域 calendar split

新 split schema：`entry-cohort-calendar-split.v1`。

禁止沿用：

- `regime-episode-split.v1`；
- 舊 episode role／split ID／sealed hash；
- 舊 registry reuse或 multiple-testing authority。

新 split 必須：

1. 所有 cohort共用單一全域 chronological cut。
2. Development、validation、sealed cut在 outcome開封前固定。
3. Development→validation與 validation→sealed兩個邊界都執行 outcome-interval purge。
4. 任何 observation 的 `[ranking_date, entry_date, exit_date]` 不得跨 role。
5. 每個邊界 embargo至少 20 個 market trade days；若 power／label policy要求更長則取較大值。
6. Ranking date、holding date、portfolio fingerprint或 outcome interval跨 role重疊即 fail closed。
7. Sealed slice hash綁定 dataset、ranking inventory、calendar、contract與 cutoffs。
8. Sealed只允許一次開封；任何 outcome-driven契約更動使該 sealed set失效，必須等待新資料。

## 相依性與有效樣本

- Holding interval相交的 portfolio observations必須合併成 overlap component。
- 統計單位是 component aggregate，不是 daily entry、個股或 raw trade count。
- 每個 cohort與 role同時回報 raw count、完整 outcome count與 independent component count。
- 不得把高度重疊日期當作獨立 n。

## Multiple testing

- Family grain：`scenario × entry_cohort × primary_endpoint`。
- 唯一 primary endpoint建議為 paired portfolio net excess return 的 one-sided component sign test。
- Family size `M` 包含全部實際測試的 cohort、scenario與 endpoint。
- Bonferroni：`corrected_alpha = 0.05 / M`。
- 最低獨立 component數：`n_min = max(20, ceil(log2(M / 0.05)))`；若正式 power analysis要求更高則取較高值。
- 新增 family member、偷看 sealed、或 outcome後改契約，舊 preregistration與結果全部失效。
- 禁止挑最佳 cohort後才定 family。

## Feasibility successor

唯一 successor：`CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1`。

該卡只能：

- 使用 current reconciled authority；legacy未 admission前不得 pooling。
- outcome-free建立 entry identity、D+1/h20 calendar、path availability、global split、embargo與 overlap components。
- 輸出各 cohort × role 的 selection count、window/path completeness、independent component count與 exclusions。
- 輸出 source／contract／split／family hashes與 sealed freshness receipt。

該卡不得：

- 計算 return、挑最佳 cohort或執行 replay；
- 開封 sealed outcomes；
- 改 runtime、ranking、model、queue或 scheduler。

唯一 GO：`FEASIBLE_FOR_PREREGISTRATION`。至少一個事前固定 cohort在 development、validation、sealed capacity都達 `n_min`，且雙 embargo、purge、freshness全通過。

其餘狀態：

- `NO_GO_INSUFFICIENT_ENTRY_COHORT_CAPACITY`
- `BLOCKED_EVIDENCE_OR_CONTRACT_CONFLICT`

## Fail-closed verifier

Verifier至少拒絕：

- closure/current authority、ranking、features/prices、regime、taxonomy/helper、calendar或 contract hash漂移；
- D row缺失、UNKNOWN、transition、as-of不等於 D；
- D+1/h20 off-by-one、bars/path不完整卻被靜默刪除；
- future-derived欄位進入 selection、cohort或權重；
- outcome interval跨 role、embargo小於20、sealed reuse；
- portfolio/component alias overlap、stock-level pseudo replication；
- family新增但 family hash／M／alpha未變；
- causal或 entire-holding exact-regime完成宣稱。

## Production boundary

- `research_only=true`
- `replay_ready=false`
- `promotion_ready=false`
- `production_ready=false`
- `runtime_change_allowed=false`

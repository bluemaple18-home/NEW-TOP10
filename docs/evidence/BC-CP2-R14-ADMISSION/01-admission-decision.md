# BC-CP2 R14 admission decision

👉 [假設與目標確認] 目標是判定已註冊的單一 R13 forward bundle 後，是否存在能在有限邊界內接近 Entry-Regime h20 feasibility capacity gate 的 R14；邊界是純唯讀、outcome-free，不執行 capture／replay，capacity／split／registration，不建立 scheduler／registry／runtime；驗收是從任務卡的 candidate forks 選出唯一 verdict，並給出可重算的最小下界。

## Verdict

`NO_GO_R14_INSUFFICIENT_DECISION_VALUE`

下一個交易日的單次 capture 不會解除新的 authority gap：R13 已經證明一次 create→capture→COMPLETE bundle→committed-byte verification，而相鄰 h20 holding intervals 會互相重疊，下一日的 observation 不會新增 independent component。

有界自然累積也不能在合理時間內接近 gate。在對 R14 最有利的假設下，仍至少需要 `60` 個合格、同一事前固定 cohort 的 independent components；目前 R13 最多只是第一個尚待 h20 calendar completion 的 prospective observation。加入 h20 不重疊間隔、三角色與雙邊界 embargo 後，從第一 ranking date 到最後一筆 h20 window 可完成的保守理論下界是 `1,280` 個 trading-day advances（含起點為 `1,281` 個 trade-date positions），約為五個交易年，而且還假設每筆都屬同一 cohort、沒有 transition／missing／exclusion，且正式 power analysis 不會提高 `n_min`。這不是一張有清楚終點與近期 decision value 的執行卡，而是把多年等待包裝成 active work。

## Mainline snapshot

### Root question

單一 next-date capture 或一個不增加 scheduler／registry／new runtime 的 bounded accumulation contract，是否能實質推進 Entry-Regime feasibility？

答案是否定。單次 capture 只會在現有重疊 component 中增加 raw observation；有界累積若不修改既有 h20／split／embargo／component 契約，也無法在合理時間內達到三角色各 `n_min`。

### Current blocker

目前 blocker 不是只缺一個 fresh completed date，而是結構性 capacity economics：

- h20 closed holding intervals 以可傳遞相交關係合併 component。
- development／validation／sealed 各自至少需 `n_min` independent components。
- 兩個 role boundary 都需 outcome-interval purge 與至少 `20` 個 market trade days embargo。
- R13 只有一個固定 bundle，且 `downstream_authority=NONE`；它不證明 cohort eligibility、h20 calendar completion、global split 或 capacity。

現場同時沒有晚於 `2026-09-01` 的 completed-date authority，但這只是次要現狀，不是選擇 defer 的充分理由。

### Candidate forks

| Candidate fork | Decision | Reason |
| --- | --- | --- |
| `GO_R14_SINGLE_NEXT_DATE_FORWARD_CAPTURE_CARD` | REJECT | R13 已證明單次 seam；相鄰 next-date h20 interval 與 R13 相交，independent component 不增加。 |
| `GO_R14_BOUNDED_FORWARD_ACCUMULATION_CONTRACT_CARD` | REJECT | 最佳情形仍需約五個交易年；沒有合理的單卡上限與近期停止點，且自動化累積會需要本卡明文禁止的 scheduler／registry／runtime。 |
| `DEFER_R14_FRESH_COMPLETED_DATE_NOT_AVAILABLE` | REJECT | 雖然沒有新 completed date，但它不是唯一 blocker；即使明日有新 authority，單次 capture 仍無新 decision value。 |
| `NO_GO_R14_INSUFFICIENT_DECISION_VALUE` | **SELECT** | 單次或有界累積都無法在合理邊界內接近 capacity gate。 |
| `BLOCKED_R14_AUTHORITY_CONFLICT` | REJECT | R13 verifier、R13 re-review、V2 contract 與 architecture 的邊界一致；沒有 material authority conflict。 |

### Current state

- BC-CP2 forward authority：單一 `2026-09-01 / regime_shadow_research / r13-r2-20260901-af9c32b` committed bundle 已註冊並通過驗證。
- Historical ranking corpus：永久 `NON_ADMISSION`。
- Entry-Regime feasibility：`NOT_ADMITTED / NOT_RUN`。
- R14 execution：`NO_GO / NOT_ADMITTED`。
- R14 之後的 preregistration、B0 Phase 2、B1、C1、production：`NOT_ADMITTED`。

### Next step

關閉 `BC-CP2 R14 forward accumulation` 作為 active frontier，不開 R15，不建立定期 capture 或等待卡。主線應回到 `MAINLINE_CURRENT_STATE_RECONCILIATION_FOR_NON_BC_CP2_FRONTIER`這個可裁決 frontier：以當前 fixed tip 重新盤點已整合的 B0／C0／Forecast 與現行 canonical backlog，只從其中另行 Owner-admitted 且未被現行 authority 阻擋的工作選下一 frontier。本卡不代為准入其中任何一條。

### Waiting condition

`NONE_FOR_R14`。此 verdict 不要求 Mainline 等下一個日期；自然產生新 daily data 不會自動翻轉 R14 verdict。未來只有 Owner 另行批准修改產品問題或統計契約的新 mission，才能重開；不得在 R14 內暗改 h20、roles、embargo、component grain 或 `n_min`。

### Limits

本裁決只固定 R14 admission boundary，不證明結果品質，不讀取 outcome／target／performance，不產生 ranking，receipt／manifest／split／capacity／replay／benchmark／training，不修改 runtime／production，不 commit／push／merge／deploy／external write。

## Confirmed facts

### R13 解除與未解除的 blocker

| Boundary | R13 effect | Evidence |
| --- | --- | --- |
| Exact forward bundle identity | 解除 | R13 authority CLI 於 fixed `HEAD=0e39b550a3b1df502bef350447521037a54254af` 回 `REGISTERED_FORWARD_BUNDLE_VERIFIED`，`errors=[]`，四檔 `commit_status=MATCHED`。 |
| Single-date create→capture→verify seam | 解除 | Committed R13-R2 bundle 固定 scenario／date／run／manifest／receipt／model／ranking bytes。 |
| Receipt registration vs downstream authority | 未解除 | Verifier 明文 `authority_scope=R13_R2_COMMITTED_EVIDENCE_ONLY` 且 `downstream_authority=NONE`。 |
| Entry cohort eligibility | 未解除 | R13 沒有執行 ranking-date as-of exact identity eligibility audit。 |
| h20 calendar/path completion | 未解除 | `2026-09-01` 只是 ranking/capture date；本裁決未執行 h20 calendar/path audit。 |
| Independent component capacity | 未解除 | R13 未執行 component census；單日 raw ranking 不等於三角色 capacity。 |
| Global chronological split／purge／embargo | 未解除 | R13 不產生 `entry-cohort-calendar-split.v1`。 |
| Historical corpus | 未解除且禁止升格 | Historical corpus 維持 `NON_ADMISSION`；forward registration 不可回填 contemporaneous provenance。 |
| Preregistration／production／下游 phases | 未解除且未准入 | R13 re-review 與 authority reader 都明文不授權。 |

### Local date/status/schema/hash metadata

本次只讀 date/status/schema/hash metadata，沒有讀取 outcome-bearing columns 的 values：

| Source | Metadata receipt | Decision |
| --- | --- | --- |
| `data/clean/features.parquet` | `516,169` rows；date schema `timestamp[ns]`；max date `2026-09-01`；sha256 `aab60603280ae3d2a603b705ab02c5b19f518dcf178080482b2500b221f954ce` | 沒有新 date |
| `data/clean/events.parquet` | `516,169` rows；date schema `timestamp[ns]`；max date `2026-09-01`；sha256 `7a6f85beff13bc82ed1ce9d29fe81ab916f841118b69b981042d663fec800e34` | 沒有新 date |
| `data/clean/universe.parquet` | `274,016` rows；date schema `timestamp[ns]`；max date `2026-09-01`；sha256 `f658800012a8f8072e62aad053fe984b9c2a5d70c370b00b6f74c795fc81c109` | 沒有新 date |
| `artifacts/automation_status_2026-09-01.json` | schema `daily-run-status.v1`；mode `daily`；status `OK`；dry-run `false`；run date `2026-09-01`；features/events/universe latest dates 皆 `2026-09-01`；sha256 `0211252a3aa28676a42f9ecdf7c03b675a56ad215d98b240c381d8e5540b6400` | 已使用的 R13 date authority，不是 next date |
| `artifacts/automation_status.json` | sha256 同上，run date `2026-09-01` | canonical current status 仍是同一 date |
| Dated non-dry-run status inventory | 最新檔名與最新 successful run date皆為 `2026-09-01` | 未找到晚於 R13 的 completed-date authority |

## Derived lower bounds

### Contract constants

- Architecture：`horizon_trade_bars = 20`，entry 為 `D+1`，holding interval 以 closed interval 計算，相交者作可傳遞合併。
- Roles：`R = 3`，分別是 development／validation／sealed。
- Boundaries：`B = 2`，每個都需 purge 與至少 `E = 20` trade-day embargo。
- `n_min = max(20, ceil(log2(M / 0.05)))`。Prior-art family 固定 `M=10`，所以 `ceil(log2(10/0.05)) = ceil(log2(200)) = 8`，`n_min=20`。V2 並未授權永久沿用舊 family，所以 `20` 只是對 R14 最有利的 lower bound；正式 family 或 power analysis 只可維持或提高它。

### Minimum independent observations and captures

至少一個事前固定 cohort 必須在三個 roles 都達到 `n_min`，因此：

```text
minimum_independent_components = R × n_min
                               = 3 × 20
                               = 60
```

每個 forward ranking date 對同一 cohort 最多貢獻一個新 independent component；同日多 scenario 的 holding interval 也相交，不會變成多個 independent components。所以 best-case minimum 是 `60` 個合格 capture dates。若將現有 R13 慷慨視為一個未來會 calendar-complete 且通過 cohort eligibility 的 prospective component，仍需至少 `59` 個新的合格 capture dates。

這是不可達的理想下界：任一 capture 若落在不同 cohort，或因 transition、UNKNOWN、as-of mismatch、calendar/path incomplete 被排除，實際需求都只會上升。

### Minimum trading-day span

將 ranking date `D_i` 放在 market trade-day index `t_i`。其 h20 holding interval 是 entry `t_i+1` 到 exit `t_i+20` 的 closed interval。要讓下一筆不相交，必須：

```text
entry_(i+1) > exit_i
t_(i+1) + 1 > t_i + 20
t_(i+1) - t_i >= 20
```

因此單一 role 的 `20` 個 components 至少橫跨：

```text
(n_min - 1) × h20 = 19 × 20 = 380 trading-day advances
```

在不計 role boundaries 時，`60` 個 components 的 ranking-date span 下界是：

```text
(R × n_min - 1) × h20
= (60 - 1) × 20
= 1,180
```

若只把 architecture 的「每個 boundary 至少 `20` trade days embargo」當成單側／總量下界，不套用現有 fail-closed split seam，則 contract-only 的絕對最佳下界為：

```text
contract_only_elapsed_floor
= 1,180 + B × E + final_h20
= 1,180 + 2 × 20 + 20
= 1,240 trading-day advances
```

這個 `1,240` 是對 R14 更有利的鬆弛解讀，本身已約為五個交易年，也足以否定近期 decision value。

但現有 `entry-cohort-calendar-split.v1` 的 fail-closed 實作對每個 role boundary 使用雙側 h20 embargo：邊界前最後一個 exit 必須早於 `cut-20`，邊界後第一個 entry 必須不早於 `cut+20`。相比一般非重疊相鄰 components，每個 boundary 至少再增加 `40` 個 trading-day advances：

```text
minimum_ranking_date_span
= (60 - 1) × 20 + B × (2 × E)
= 1,180 + 2 × 40
= 1,260 trading-day advances
```

最後一個 ranking date 之後還需 `20` 個 market trade bars 才能得到 calendar-complete h20 window，所以從第一 ranking date 到可執行 outcome-free feasibility capacity audit 的保守理論下界是：

```text
minimum_elapsed_trade_day_advances = 1,260 + 20 = 1,280
inclusive_trade_date_positions      = 1,281
```

以每年約 `250` 個交易日只作尺度估算，`1,280 / 250 ≈ 5.12` 個交易年。這不是日曆日期預測，而是忽略所有 exclusion 與 cohort drift 後的最佳情形下界。

現有 split allocator 還可能因 cut 附近的 selection dates 被 purge 而需要額外 captures；本裁決沒有執行 split，也沒有把這個額外成本計入 `60` 個理論 minimum，所以實際需求只可能更高。

### Why daily capture does not linearly add capacity

若每個交易日連續 capture，相鄰 windows 的 entry/exit 必然相交；而且相交關係是可傳遞的，所以一整段連續 daily observations 會合併成一個 overlap component，不是 daily count 幾筆就增加幾個 independent n。

要得到新 component，至少需要前後 ranking dates 間隔 `20` 個 trade-day indices；在 role boundary 還需額外 embargo。將 daily data 收齊後再事後挑間隔日期，會引入目前契約未准入的 thinning/selection rule，不能當成 R14 的默認修復。

## Assumptions and uncertainty

- 下界以 `n_min=20` 計算；若正式 family `M` 或 power analysis 使 `n_min>20`，數量與時間皆成比例上升。
- 慷慨假設 R13 在未來可成為一個 calendar-complete、eligible component；現在它只是已註冊 ranking provenance bundle，不是已完成的 feasibility observation。
- 慷慨假設後續每筆都是同一事前固定 cohort 且零 exclusion；實際 regime transitions 與 eligibility failures 會拉長時間。
- `1,280` 是 contract-conservative best-case lower bound，不是建議的 capture schedule，更不是 R14 執行授權。
- 本卡沒有經由 outcome 挑 cohort、scenario、cutoff 或 stopping rule。

## Absorption boundary

### Why not less

- 必須重跑 R13 authority verifier，才能區分 committed bundle authority 與文件敘述。
- 必須同時納入 `n_min`、三 roles、h20 closed overlap 與雙 embargo；只算 raw capture dates 會得到虛假的 capacity 結論。
- 必須單獨驗本機 date/status/schema/hash metadata，才能說明「現在無新 date」但「date 不是唯一 blocker」。

### Why not more

- 下界已足以否定單次與有界累積的近期 decision value；不需要執行 capacity/split 或讀取 outcome。
- 把五年累積做成 automation 需要 scheduler／registry／retention/runtime contract，這是新 subsystem 與 futureware，超過 R14 admission decision。
- 不需要修改 h20、cohort、roles、split、embargo 或 `n_min`來「製造 GO」。

### Do not absorb

- 不吸收 outcome、return、PnL、win rate、Sharpe、alpha、target、promotion score 或 sealed data。
- 不吸收 historical corpus admission，不用 forward receipt 回填舊 ranking provenance。
- 不吸收 capture execution、ranking generation、registration writer、scheduler、registry、ledger、database、queue 或 production runtime。
- 不吸收 Entry-Regime feasibility execution、preregistration、B0 Phase 2、B1、C1 或 production admission。

### Stop and rollback path

- Stop：本文一旦選擇 `NO_GO_R14_INSUFFICIENT_DECISION_VALUE`，R14 鏈即停止；不排定下次 capture，不建立等待任務。
- Rollback：本次沒有 runtime/data/config 變更可回滾；若 Mainline 不接受本裁決，可移除單一 evidence 檔回到原狀，R13 的 `downstream_authority=NONE` 不變。

## Verification receipt

- CodeGraph-first：已對 R14／R13／Entry-Regime／n_min／h20／overlap／split／embargo／status authority 做 semantic context query；索引未直接提供 Entry-Regime 關鍵實作，後續才限域讀取 governing docs 與 `entry_regime_cohort_feasibility.py`。
- Fixed HEAD：`0e39b550a3b1df502bef350447521037a54254af`。
- R13 verifier：`.venv/bin/python -m app.research.r13_forward_receipt_authority --verify`，exit `0`，`REGISTERED_FORWARD_BUNDLE_VERIFIED`，四檔 `MATCHED`，`errors=[]`，`downstream_authority=NONE`。
- Local authority inventory：只讀 parquet schema/date column 與 JSON date/status/freshness metadata；沒有讀取 outcome/target/performance values。
- Execution guard：capture／registration／ranking generation／replay／capacity／split／benchmark／training／outcome／sealed 皆 `NOT_RUN`。
- Diff guard：`git diff --check` exit `0`；對本未追蹤新檔執行 `git diff --no-index --check /dev/null <evidence>` 無 whitespace diagnostics（exit `1` 只代表內容有差異）。
- Changed-file allowlist：本 worker 只新增 `docs/evidence/BC-CP2-R14-ADMISSION/01-admission-decision.md`；開工前已存在的未追蹤 task/handoff 檔全數保留、未修改。
- Temporary artifacts：`NONE`。External writes：`NONE`。

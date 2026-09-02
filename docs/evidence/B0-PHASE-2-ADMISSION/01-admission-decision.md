# B0 Phase 2 admission decision

## Verdict

`NO_GO_B0_PHASE_2_INSUFFICIENT_DECISION_VALUE`

## Evidence synthesis

| Required B0-P2 decision input | Current evidence | Gate |
|---|---|---|
| Authoritative candidate space | formal executable `720` generation／identity／partition已證明；larger product dimension／constraint authority缺失 | PARTIAL |
| Full-scan cost | synthetic capacity-only 720 run recorded `8.114s / 88.73 candidate/sec`，但明列`NOT_RESEARCH_EVIDENCE / NOT_ADMISSION` | DIAGNOSTIC_ONLY |
| Full-scan vs adaptive measured gap | 沒有同一research-valid workload上的quality、cost與evidence-eligibility comparison | MISSING |
| E2 reusable evaluator | input可load-once，但full candidate evaluator reuse未證明 | NOT_PROVEN |
| E3 current evaluator | 每個candidate仍是path-dependent replay | CONFIRMED |
| E4 forward shadow | funnel需要，但統一path與cadence未characterize | REQUIRED_BUT_UNCHARACTERIZED |
| Outcome／overfit evidence | R14證明h20 independent capacity的樂觀下界仍約需`1,280`個交易日advance；目前沒有可支持policy選擇的近期decision value | INSUFFICIENT |
| B1 recommendation | rank/unrank／chunk等可由未來kernel提供，但沒有證據需要現在先開B1實作 | PREMATURE |

## Decision reasoning

B0-P2預定輸出的`full-scan-vs-adaptive decision`、daily refinement policy、overfit guards與RegimePolicyBundle draft都依賴尚不存在的research-valid比較或E4 evidence。現有720 benchmark只證明synthetic harness的容量與parity，契約明確禁止外推成B0-P2 admission。R14則顯示依目前h20／三角色／embargo條件，持續等待或每日capture不會快速增加獨立樣本。

因此現在啟動B0-P2會主要產生假設性policy與未被證據驅動的架構文件，違反`MEASURED_GAP_REQUIRED`與`NO_FUTUREWARE`。最小充分選擇是NO-GO，不另開等待型repair或R15。

## Why not less／why not more／do not absorb

- Why not less：保持`NOT_ADMITTED`而不裁決，會讓B0-P2持續被誤認為下一張可施工卡。
- Why not more：目前沒有research-valid measured gap，不能合理切出search-policy、B1或runtime implementation。
- Do not absorb：不新增optimizer、scheduler、queue、database、registry、canonical writer、model adapter或通用workflow runtime。

## Re-entry conditions

B0-P2只有在下列任一條形成可驗證新資訊時才可重新裁決：

1. committed larger product matrix dimension／constraint authority；或
2. 同一research-valid workload上的bounded full-scan與adaptive comparator；或
3. 可重現E2 semantic/performance evidence加上E4 direct observation cadence。

單純增加calendar dates、重跑synthetic 720或新增prior-art清單不構成re-entry。

## Limits

本decision不授權B0-P2、B1、B2、C1、TFM3 download／inference、capture、replay、training、outcome、push、deploy或production。

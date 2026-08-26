# 逐 job 證據矩陣

## Global verdict

`NO-GO`。八個 job 沒有全部完成兩個代表性完整週期；所有 production
`launch_verified` 維持 `false`，八個 launchd label 維持 disabled。

| Job | 實際執行 | 主要量測 | 判定 |
|---|---|---|---|
| `daily` | 0 cycle | production wrapper 的成功與失敗路徑都可能呼叫 Clawd/ops `--send`；卡片邊界內沒有不執行其他專案 gateway 的代表性模式 | `NO-GO / EXTERNAL_AUTHORITY_REQUIRED` |
| `retrain` | 2 個 scheduled monitor cycle，均 exit 0 | delta `11030/1997` bytes、files `+3/+0`、peak RSS `231112704/170065920`、swap delta `1832323645/0`、unknown writes `0/0` | `NO-GO / HEAVY_BRANCH_NOT_EXERCISED`；兩次 PSI 都沒有進入真正 retrain 分支 |
| `reference` | cycle 1 自動停損 | `29414→53734` files，超過 `45000`；delta `461305006` bytes、peak RSS `113803264`、swap delta `0` | `NO-GO / PROJECT_FILE_COUNT_BUDGET_EXCEEDED`；依契約不跑 cycle 2 |
| `fog-research-worker` | cycle 1 於 186.5 秒隔離停止 | peak RSS `3191783424`、swap delta `594081219`、host-free delta `-1322807296`；reclaim 先回收 `151684204` bytes／`5964` files | `NO-GO / HARD_MEMORY_CEILING_WAS_MISSING_DURING_CYCLE`；補 hard ceiling 後未冒險重跑 |
| `pm-research-harness` | 1 個 provider-disabled cycle exit 0 | `topic_runs=0`、未送卡；量測主要反映啟動前 reclaim，不能估算正常 growth | `NO-GO / REPRESENTATIVE_WORKLOAD_EMPTY`；空週期不跑 cycle 2 |
| `external-review` | 0 cycle | browser/API 正式模式會對 ChatGPT/Gemini 外送；API dry-run 只產生 fixture raw | `NO-GO / EXTERNAL_AUTHORITY_REQUIRED` |
| `external-review-preflight` | 0 cycle | source 直接 probe ChatGPT/Gemini Chrome session，沒有 offline representative mode | `NO-GO / EXTERNAL_AUTHORITY_REQUIRED` |
| `baseline-harness` | 修正 reclaim 後的完整嘗試 exit 1 | unlock policy 已能保留；host runner 隨後因 `medium-window review artifact is not OK` fail closed | `NO-GO / REPRESENTATIVE_REVIEW_NOT_OK`；依契約不跑 cycle 2 |

## 峰值推估

只有 retrain monitor 有兩個完整週期，可做「monitor 分支」的 bounded projection；這不等於
retrain job 全體核准。採兩週期較高 observed growth `602295.796 bytes/hour`：

- 一小時：`602296` bytes。
- 一天連續上界：`14455100` bytes。
- 14 天 retention 連續上界：`202371388` bytes。
- 第二週期沒有累積檔數，且 growth 降為 `274233.400 bytes/hour`。

其餘 job 缺代表性兩週期、被 hard stop、為空 workload 或涉及外部權限，因此不填猜測性
一小時／一天／保留期數字；全部維持 `NO-GO`。

## Evidence paths

- Machine verdict：`docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/job-verdicts.json`
- Receipts：`docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/receipts/`
- Raw samples：`docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/samples/`
- Baseline failed attempts：`docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/failed-attempts/baseline-harness/`

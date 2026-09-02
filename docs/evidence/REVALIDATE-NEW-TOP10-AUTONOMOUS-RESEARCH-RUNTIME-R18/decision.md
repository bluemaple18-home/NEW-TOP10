# R18 外接 Fog 重驗決策

- overall status: `GO / ACTIVATION_CANDIDATE`
- runtime status: `PASS_CANDIDATE`
- outer lifecycle status: `exit 0 / cleanup complete`
- source commit: `737b9bbbbc7e3197bfc9dc790955efc171963e3c`
- validation mode: manual-only；launchd 維持未啟用，沒有 push／deploy／production activation

## Runtime evidence

| cycle | status | topic runs | elapsed | peak RSS | pressure | swap delta | unknown writes | quiescent |
| ---: | --- | ---: | ---: | ---: | --- | ---: | --- | --- |
| 1 | `OK` | 1 | 2690.26s | 799,424,512 B | 1 → 1 | -50,331,648 B | `[]` | true |
| 2 | `OK` | 1 | 1849.97s | 758,562,816 B | 1 → 1 | -434,561,352 B | `[]` | true |

兩輪 `guard_exit_code=0`、`reasons=[]`，且各自只執行本 cycle 產生的一個代表性 topic。2 GiB process-tree RSS ceiling、5 GiB lifecycle byte budget與 50,000-file lifecycle budget均未放寬。

## Lifecycle acceptance

- 外層 `tmp_artifact_lifecycle.py run` 最終 exit code 為 `0`。
- lifecycle 結束後，R18 clean-room `<external-volume>/TOP10new-runtime-validation-tmp/ai-core-top10-fog-revalidation-r18-3nxntzne` 已不存在。
- R17 的 clean-room file-budget blocker已關閉；本卡只構成手動 activation candidate，不代表已啟用 launchd 或 production。

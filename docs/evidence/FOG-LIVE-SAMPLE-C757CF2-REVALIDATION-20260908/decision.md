# Fog live-sample 修補代表性驗證決策

- 候選 commit：`c757cf24bd5ca1fa3f20ef55db4385aef04c64f2`
- 判定：`PASS_CANDIDATE / NON_PRODUCTION`
- 驗證方式：既有 tmp artifact lifecycle 管理的外接碟隔離 sandbox，連續兩個代表性週期。
- lifecycle：exit `0`；sandbox 已回收。

## 週期結果

| cycle | status | child exit | quiescent | max live-sample gap | peak RSS | pressure | swap delta | unknown writes | topic runs |
| ---: | --- | ---: | --- | ---: | ---: | --- | ---: | --- | ---: |
| 1 | `OK` | 0 | true | 54.195279s | 690,700,288 B | 1 → 2 | -536,734,597 B | `[]` | 1 |
| 2 | `OK` | 0 | true | 54.139774s | 623,050,752 B | 2 → 2 | +1,181,157,949 B | `[]` | 1 |

兩輪 `guard_exit_code=0`、`reasons=[]`、`final_process_group_quiescent=true`。Fog 的 60 秒 hard maximum 未放寬，兩輪最大完成間隔均低於上限。sandbox 約 3.04 GiB，使用既有 5 GiB／50,000-file project policy；驗證結束後 exact lifecycle root 不存在。

第二輪 swap 增加約 1.10 GiB，但未超過 2 GiB hard budget，memory pressure 維持 level 2，程序 peak RSS 約 594 MiB，且 guard 沒有觸發停損。這證明本次代表性週期在既有政策內完成；不構成長期 host 穩定性或 production natural-cycle acceptance。

## 邊界

本證據只接受 `c757cf2` 作為 activation candidate。未執行 push、deploy、marker recovery、launchd mutation、heartbeat 恢復或自然週期 acceptance。舊失敗 receipt 與 denial marker 保持原狀。production activation 仍需固定 scope、failure-state review 與 Owner 明確授權。

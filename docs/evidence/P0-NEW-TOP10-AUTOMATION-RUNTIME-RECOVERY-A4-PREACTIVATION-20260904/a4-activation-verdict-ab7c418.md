# A4 bounded activation 驗收 — `ab7c418`

日期：2026-09-04

狀態：`PARTIAL / NATURAL_ACCEPTANCE_PENDING`

## Production action

- Owner 已明確授權 A4 production activation。
- 正式入口：`scripts/activate_automation_runtime.py --activate`
- 目標：daily、external-review-preflight、fog-research-worker 三條 launchd job。
- 固定 runtime commit：`ab7c4180422b028a6a2a39fa311ea0ba591d561e`
- 工具執行：單次，未重試。
- CLI 結果：exit `0`，`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`。

## 即時容量 gate

三條正式 runtime measure 均為 `PASS`：

| job | host free | project bytes | files | memory pressure | swap | reasons |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| daily | 32,542,789,632 | 3,057,754,711 | 30,510 | 2 | 8,738,182,266 | `[]` |
| external-review-preflight | 32,542,789,632 | 82,925 | 21 | 2 | 8,738,182,266 | `[]` |
| fog-research-worker | 32,542,777,344 | 1,206,991,857 | 13,019 | 2 | 8,738,182,266 | `[]` |

## Activation receipt

- Artifact：`activation-receipt-ab7c418-20260904T195149+0800.json`
- SHA-256：`0a00d989c5f221feb02ec3bc90874ab2d46983c34bd65b32a93fe8b179b9f7a2`
- schema：`top10.automation-runtime-activation.v1`
- receipt status：`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`
- failure：`null`
- signal count：`0`
- receipt rename 與 parent directory fsync 已完成。
- signal teardown 依契約由 process exit status 證明；本次 CLI exit `0`。
- 三份 prestate plist 已保存在同名 `.prestate/` 目錄。
- daily 與 fog 原始 denial hash 已寫入 receipt，舊 evidence 仍保留；runtime 端 marker 均為 clear。

## Post-activation verification

- 三份 installed plist hash 與 receipt 的 `new_sha256` 完全相符。
- 三份 ProgramArguments 均指向 `<runtime-root>/scripts/...`。
- 三個 launchd job 均為 loaded、`not running`；activation 沒有手動觸發 child。
- activation 後再次執行正式 runtime validator：`RUNTIME_CHECKOUT_GO`。
- 3 秒後重查，runtime checkout 仍 pin 在固定 SHA，三個 runtime restart-denied marker 均不存在。

## Remaining acceptance

A4 已完成，但 recurring automation 尚不可標示為完全恢復。A5 必須取得：

- fog：連續 2 次 15 分鐘自然 cadence。
- external-review-preflight：連續 2 次 17:40 自然排程。
- daily 自動報牌：連續 2 個交易日 17:30 自然排程，且 child、當日 artifact、publish/send terminal result 全部成功。

不得用 manual run 或 kickstart 代替自然週期。

## 未做

- 未手動觸發自動報牌、研究或外部 provider。
- 未修改其他五條 launchd job。
- 未 push。

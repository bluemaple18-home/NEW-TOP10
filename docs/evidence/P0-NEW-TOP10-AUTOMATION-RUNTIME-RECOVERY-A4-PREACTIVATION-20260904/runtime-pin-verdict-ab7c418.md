# A4 runtime pin 驗收 — `ab7c418`

日期：2026-09-04

狀態：`READY_FOR_A4_ACTIVATION_AUTHORIZATION`

production mutation：`0`

## 結果

- Owner 已授權只更新 dormant runtime checkout。
- `<runtime-root>` 已由 `60c7677d9e946e6ec702f851a986d0aad925f887` 切到 detached `ab7c4180422b028a6a2a39fa311ea0ba591d561e`。
- 切換前後 runtime 工作區均乾淨。
- 正式 runtime validator 回傳：

```text
RUNTIME_CHECKOUT_GO runtime_root=<runtime-root> commit=ab7c4180422b028a6a2a39fa311ea0ba591d561e
```

- runtime `.venv/bin/python` 可執行。
- daily、external-review-preflight、fog 三個 runtime restart-denied marker 均不存在。
- 三個 launchd job 仍載入但未執行，installed plist 仍指向 `<repo-root>`；本輪沒有 scheduler topology mutation。

## 判決

前一份 `preactivation-verdict-ab7c418.md` 的 `BLOCKED_BY_RUNTIME_PIN` 已解除。候選現在可進 A4 bounded activation，但尚未取得執行 `--activate` 所需的 production mutation 授權。

A4 成功後仍只會進入 `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`；必須再依 A5 等待三條 job 各自連續兩次自然排程成功，才能判定 recurring automation 已恢復。

## 本輪未做

- 未修改 installed plist 或 launchd 狀態。
- 未清除或搬移開發 checkout 的 denial marker。
- 未啟動任何 job。
- 未送外部 provider。
- 未 push。

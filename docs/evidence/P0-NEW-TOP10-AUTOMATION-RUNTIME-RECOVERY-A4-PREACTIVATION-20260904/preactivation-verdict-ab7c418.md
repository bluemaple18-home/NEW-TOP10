# A4 啟用前驗收 — `ab7c418`

日期：2026-09-04

狀態：`BLOCKED_BY_RUNTIME_PIN`

production mutation：`0`

## Root question

固定候選 `ab7c4180422b028a6a2a39fa311ea0ba591d561e` 是否已具備執行 A4 bounded activation 的前置條件。

## 已確認

- `70ff1e9dda855e1030a8bb169e77931d49f629a8` 是候選 SHA 的 ancestor；既有雙獨立 reviewer 接受的 signal-safe activation repair 已包含在候選內。
- runtime checkout `<runtime-root>` 為 detached、工作區乾淨，且 `.venv/bin/python` 可執行。
- 三個目標 job 均已載入但目前未執行：
  - `com.new-top10.daily`：last exit `75`
  - `com.new-top10.external-review-preflight`：last exit `78`
  - `com.new-top10.fog-research-worker`：last exit `75`
- 三份 installed plist 仍指向 `<repo-root>`；尚未切到隔離 runtime。
- runtime 端三個 restart-denied marker 均不存在。
- 開發 checkout 的原始 denial evidence 已保存且 hash 相符：
  - daily：`fc32f0cbb5e687a4263903340087cbfce7b0bc9066aae38c37e7d11b25291939`
  - fog：`ae1b23791e20a67965b80b5532831ae67018525df92165437a620b7e85d363d3`
- 修正後三條 storage preflight 已分別量測為 `PASS`；啟動門檻只採全域 `10%`，runtime reserve 仍為 `max(20 GiB, 10%)`。

## 唯一阻擋

正式 runtime validator 對候選回傳：

```text
RUNTIME_CHECKOUT_NO_GO: runtime HEAD 未 pin 到 accepted commit:
expected=ab7c4180422b028a6a2a39fa311ea0ba591d561e
actual=60c7677d9e946e6ec702f851a986d0aad925f887
```

因此現在不能執行 A4 activation。先把 dormant runtime checkout pin 到固定候選 SHA，才可重跑正式 runtime validation 與 A4 preflight。

## 邊界與下一步

- 本輪未切 runtime、未修改 launchd、未清 marker、未啟動 job、未送外部 provider、未 push。
- 下一個動作需要 Owner 明確授權：把 `<runtime-root>` 更新到 `ab7c4180422b028a6a2a39fa311ea0ba591d561e`。
- runtime pin 完成不等於 production activation；A4 的 `--activate`、launchd 切換及 marker transaction 仍需另一個明確 production 授權。
- A4 成功後狀態最多為 `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`；daily、fog、external-review-preflight 仍須各完成 A5 規定的連續兩次自然排程驗收，才可標成恢復。

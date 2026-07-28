---
id: FOG-RUNTIME-TIME-AUTHORITY-01-I5
status: BOUNDED_DRY_REPAIR_1_VERIFIED
type: acceptance
---

# FOG-RUNTIME-TIME-AUTHORITY-01 I5 Live Acceptance

## Resume authorization（2026-07-28）

- 使用者已明確授權繼續本機 deploy、retry circuit recovery、LaunchAgent
  恢復與 bounded live acceptance。
- Recovery base固定為已推上`main`的
  `13c9faed686677fff45f30db636ad61445be00cf`。
- Release tag固定為
  `top10-2026-07-28-01-fog-exact-regime-topic-eligibility`。
- Daily source lineage blocker已由`be9bb74`修復；exact-regime topic
  eligibility及 symlink authority blocker已由`3969aba`與`51c084c`修復，
  independent re-review為`REVIEW_GO`。
- 舊三次 live probe chain維持封存，不把它改寫成成功，也不直接執行第四次
  probe。這次是 blockers修復、Review GO並整合到`main`後的新 I5 acceptance
  chain。

### Root question

固定 main lineage是否能在不修改 production model／ranking／weights／baseline／
promotion的前提下，安全恢復 Fog circuit並連續產生三輪可信 v3 scheduler
receipts？

### Mutation budget與停損

1. Runtime mutation前必須完成一份唯讀 preflight receipt。
2. Circuit recovery只允許呼叫既有 explicit verifier gate一次；不得直接刪除
   state/context。
3. 若 daily source lineage或 exact-regime eligibility舊 blocker在新鏈首次
   重現，立即`NO_GO`並回到 safe stopped state，不重試。
4. Scheduler acceptance最多三輪；任何 gate失敗立即 unload並保存 artifacts，
   不補第四輪。
5. 不啟用 PM harness queue mutation，不執行 external AI、publish、Discord或
   交易。

### Acceptance evidence

所有 preflight、before/after hashes、plist alignment、circuit rotation、
scheduler receipts、logs與 rollback結果寫入：

`docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-I5/`

### Bounded dry Repair 1

首次 linkage-only bounded dry在 circuit recovery前 fail closed，暴露兩個 topic
generation callers沒有傳 explicit date。Repair 1已建立 public-seam RED並以最小
caller wiring修復；affected suite與 full suite皆通過。證據：

`docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-I5/bounded_dry_repair_1.md`

## Objective

將已審核並整合至 `main` 的 Fog time/data authority安裝到本機 LaunchAgent，
安全恢復既有 retry circuit，完成 bounded dry run與三輪 scheduler acceptance。

## Fixed lineage

- I1–I4 integration：`74a034f`
- I1–I4 acceptance：`333d57d`
- Processed-semantics blocker repair：`2760d30`
- Processed-semantics main integration：`111f138`
- Regression IDs：`FRTA-REG-TIME-AUTHORITY`、
  `FRTA-REG-RECEIPT-V3`、`FRTA-REG-VERIFIER-RECOMPUTE`、
  `FRTA-REG-WIRING`

## Changed-file allowlist

- 本卡
- `docs/AUTOMATION.md`
- `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-I5/**`

Live runtime可變更範圍：

- `~/Library/LaunchAgents/com.new-top10.fog-research-worker.plist`
- `logs/fog_research_retry_<market-date>.state`
- `logs/fog_research_retry_<market-date>.context.log`
- `artifacts/market_regime_history.json`
- 本 worker正常產生的 research／fog／receipt／status artifacts

## Ordering

1. 保存 installed plist、retry state/context、queue及 protected production hashes。
2. 停止 Fog LaunchAgent；確認沒有 active worker。
3. Inventory legacy v2 receipts；只 archive，不補造 v3 authority。
4. 安裝 reviewed plist，驗證 path、rendered hash、repo SHA與 policy hash。
5. 輸出 bounded dry acceptance。
6. 以既有 explicit recovery gate恢復 circuit；不得直接刪除 state。
7. 收集三輪跨 900 秒 scheduler interval receipts。
8. 比對 circuit、queue、model、ranking、baseline before/after hashes。

## GO

- Installed plist與 repo rendered plist byte-identical。
- Canonical time/data authority hash通過。
- Bounded dry acceptance通過。
- 三輪 scheduler receipts皆為 v3、fresh、market date與 source lineage正確。
- Circuit正常、queue行為符合契約。
- model、ranking、baseline與 promotion state未變。

## NO-GO / rollback

任一 gate失敗立即 unload job，保留失敗 artifacts與 state；不得恢復 legacy
receipt、不得自動清 circuit或重放 queue。

## Live blocker receipt

- Installed plist已更新但保持 unloaded。
- Canonical `market_regime_history.v2` 已由 repo builder建立，最新交易日
  `2026-07-27`、exact regime `RISK_OFF`。
- Current main產生的 closed-regime daily artifact在
  `NO_EXECUTABLE_TOPIC` 路徑仍缺 `source_lineage.daily_source_date`，因此 receipt
  producer以 `DAILY_ARTIFACT_SCHEMA_REJECT` fail closed。
- 不得以 run date或 regime source date補值；須由 canonical features lineage
  獨立產生 daily source date並加回 regression，修復 Review／整合後再續 I5。

---
id: FOG-RUNTIME-TIME-AUTHORITY-01-I5
status: BLOCKED_DAILY_SOURCE_LINEAGE
type: acceptance
---

# FOG-RUNTIME-TIME-AUTHORITY-01 I5 Live Acceptance

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

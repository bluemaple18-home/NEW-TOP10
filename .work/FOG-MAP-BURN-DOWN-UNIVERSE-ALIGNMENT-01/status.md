---
id: FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01-status
status: integrated
type: task_status
---

# Root question

如何讓 current universe 維持 canonical，同時誠實呈現歷史已分類 subset 與新增 pending delta？

# Ranked hypotheses

1. 若 producer 的 scope authority 錯置是主因，把 current total 與 rollup source scope 分開後，`54,432` delta 應出現在 pending。
2. 若 verifier 的 full-classification 假設是主因，改成守恆與明確 source scope 驗證後，合法 partial 應轉綠，而 over-classified／count mismatch 仍維持失敗。
3. 若 rollup 本身不守恆，僅改 verifier 仍應因 source scope 或 category sum 檢查而 fail closed。

# Current state

- Capability：Python／CodeGraph ready；CodeGraph indexed SHA 與 base SHA 相符。
- Evidence：主 worktree 的 verification artifact 唯一失敗為 `burn_down_counts_classify_full_universe`；current `2,921,184`、historical classified `2,866,752`。
- Phase 0 RED：`.venv/bin/python -m pytest -q tests/test_research_fog_map_burn_down.py`，exit `1`；producer 與合法 partial verifier 各 1 個 target-symptom failure。
- Falsified／supported：假說 1、2 受 RED 支持；negative guards 已證明現有 over-classified／count mismatch 不會被誤放行。
- Root cause：producer 把歷史 rollup total 當 current authority；verifier 又把 current universe 全數分類當成唯一合法狀態。
- Fix：producer 固定以 current expanded total 作 map full total，另保存 historical source scope；verifier 改驗 current／source scope、pending 與 category conservation。
- GREEN：targeted／affected `11 passed, 6 subtests passed`；322-topic integration map verifier report 為 `OK`。
- Full suite：`624 passed, 2 failed`；兩個 failure 均位於 allowlist 外且與 Fog Map seam 無依賴，詳見 verification evidence。
- Independent Review：`REVIEW_GO`；P0/P1皆為0，P2 non-blocking finding 1項。
- Mainline acceptance：targeted `11 passed, 6 subtests passed`；full suite `626 passed, 4 warnings`；compile、allowlist與diff check通過。
- Integration：candidate與review evidence已patch-equivalent整合到`main`，詳見`acceptance/mainline_acceptance.md`。
- Recovery precheck：current inventory建立成功，recovery verifier `14/14 passed`，狀態為`GO_FOR_RECOVERY`。
- Frontier：等待明確授權執行safe recovery；circuit仍開啟，尚未跑live Fog、重啟LaunchAgent或deploy。

# CLEANUP-28 結果

## 結論
已新增 `scripts/verify_odd_lot_research_suite.py`，用具名 profile 收斂六支 research verifier：

- `candidate_comparison`
- `exit_horizon`
- `exit_strategy`
- `exposure_sensitivity`
- `regime_sensitivity`
- `regime_throttle`

六支舊 verifier 入口已在 frozen valid/invalid parity 與 consumer gate 通過後退休。`scripts/verify_odd_lot_candidate_decision_report.py`、odd-lot builders、daily、model、正式 ranking 路徑未修改。

## 證據
- Parity 與驗收摘要：`.work/CLEANUP-28/evidence/parity.json`
- Script reference audit 摘要已寫入 parity evidence。
- Script lifecycle audit 摘要已寫入 parity evidence。

## 驗證
- Focused tests：`PASS`，39 passed。
- Active old verifier reference scan in `scripts/tests/config`：`PASS`，無命中。
- Script reference audit `--strict-new`：`PASS`；tracked scripts 439，status counts protected 11 / referenced 428，unknown dynamic references 1，new suspected orphans 0。
- Script lifecycle audit `--strict-new`：`PASS`；tracked scripts 439，category counts builder 137 / maintenance 95 / production entrypoint 11 / research 27 / verifier 169，new unclassified 0。
- `git diff --check`：`PASS`。
- Daily hash gate：`PASS`，四個 hash 與 CLEANUP-27 evidence 相同。

## Canonical 驗收

- full pytest：`219 passed, 28 subtests passed`
- warnings：4 個既有 dependency deprecation warnings
- reference／lifecycle `--strict-new`：PASS
- focused tests：`39 passed`
- `git diff --check`：PASS
- daily hash gate：PASS

worktree 先前的 3 個環境 failure 已由 canonical checkout 全綠證明不是本卡 regression。

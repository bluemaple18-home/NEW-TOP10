# R16 External Fog Revalidation Decision

- verdict: `NO-GO`
- stop reason: `PROCESS_TREE_RSS_BUDGET_EXCEEDED`
- cycle count: `1`（第一輪非 PASS，依契約未跑第二輪）
- process-tree peak RSS: `2,236,661,760 bytes`
- largest contributor: `build_weekend_universe_inventory.py --write-bounded-frontier-queue`
- contributor RSS: `2,202,353,664 bytes`
- memory pressure: `1 → 1`，peak `1`
- swap delta: `-75,497,472 bytes`
- unknown / registered-unmetered writes: `[] / []`

Guard 正確 fail closed；不得把本輪視為 capacity PASS。inventory 在 historical representative fixture 前先被停止，因此 R15 的 fixture-selection 修復尚未取得 external execution 證據。

本機後續修復：summary-only + bounded queue 改為兩段 streaming，避免常駐約 296 萬筆完整 row；full-record 模式維持原契約。R17 必須另取得明確授權，並沿用 5 GiB sandbox、2 GiB hard ceiling、第一輪非 PASS 不跑第二輪。

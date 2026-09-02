# R15 Process RSS Attribution Decision

## Status

`NO-GO / REPRESENTATIVE_WORKLOAD_EMPTY`

## Facts

- source commit：`860d945dc4246f4d5a3bed5971a4eba55e954c0e`
- cycle 1 elapsed：`248.77947187423706` seconds
- peak process-tree RSS：`1,635,909,632` bytes（低於 2 GiB hard ceiling）
- memory pressure：`2 → 1`；peak `2`
- swap delta：`+1,777,661,378` bytes
- unknown／registered-unmetered writes：皆為空
- 最大 contributor：`scripts/build_weekend_universe_inventory.py --write-bounded-frontier-queue`，單 PID peak `1,612,349,440` bytes
- 第二 contributor：`app.research.observation_ingest --rebuild`，單 PID peak `726,532,096` bytes
- historical exact-regime fixture 最終 `topic_runs=[]`，guard 將 cycle 判為 `REPRESENTATIVE_WORKLOAD_EMPTY`；依約未跑 cycle 2。

## Interpretation

- R12–R14 的 aggregate peak 不足以證明 strategy matrix 是主峰；R15 已把目前最大 contributor 定位到 weekend universe inventory。
- 本輪 inventory path 雖低於 2 GiB，但沒有完成代表性 topic，不能支持兩週期 capacity PASS 或 activation。
- 下一步先用本機 deterministic seam 重現 fixture 為何無法供應 topic；未建立 RED／GREEN 前不得再次執行 external cycle。

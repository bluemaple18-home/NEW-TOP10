# Mainline verdict — candidate 3023ed0

- Candidate: `3023ed022b72738c49afca5a3311044a19eb0b72`
- Reviewer A: `GO`
- Reviewer B: `NO_GO`（P1）
- Mainline: `NO_GO / REPAIR_3_INTEGRATION_FINDING`
- Mainline tests before review: `133 passed, 35 subtests passed`
- Production／launchd／marker mutation: `0`

Mainline 以實際 `fcntl.flock(..., LOCK_UN)` failure injection 重現 Reviewer B finding：第一個 unlock 例外會中止其他 lock release 並跳過 `_disarm()`。此 finding 屬於 Owner 已授權的 Repair 3 teardown 最後防線，不擴大 topology、receipt 或 production scope。

收斂修正：逐 lock 嘗試釋放並彙總錯誤；staging、locks、signal teardown 各自使用 exception boundary；CLI 對未預期 transaction exception 固定 exit 75。新增 RED 驗證 durable topology receipt 不被改寫、handlers／mask exact restore、三把鎖可重新取得與 CLI fail closed。

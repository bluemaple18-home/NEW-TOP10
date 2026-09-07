# Repair 1 — REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01

任務ID：`REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01-REPAIR-1`

請先讀 `AGENTS.md`、原 task card、`.work/REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01/review/round1.md` 與目前 candidate diff。你是 Repair writer；只修 round-1 findings，不擴 scope、不修改 control/evidence 文件。

允許檔案仍限原卡 code/tests。禁止 production、kickstart、清 marker、launchctl、deploy、push、commit、ME-D1；禁止新增 ledger/anchor/daemon/scheduler authority。

逐一 RED→GREEN：

1. `F-001`：terminal evidence 的 `artifact_run_date` 必須是真實日曆日期，且等於既有 `scripts/fog_runtime_time_authority.py` 對 `scheduled_at` 推導的 market run date。新增 self-consistent wrong-date 與 impossible-date tests；writer與reader都 fail closed。
2. `F-002`：所有 acceptance-sensitive evidence/event/plist/archive reads，以及 terminal evidence atomic immutable publish，改用 anchored directory FD、`O_NOFOLLOW`/`O_DIRECTORY`、same descriptor `fstat/read/write/link`；不得在 check 後再用 path 讀寫。加入 leaf swap、ancestor swap 或等價 deterministic race tests。
3. `F-003`：分離 cadence anchor qualification 與 accepted-chain qualification。既有 live `OK/natural/child exit 0/final quiescent`、counter=0 的 archived receipt即使沒有 terminal evidence，也可作下一輪 cadence anchor，但不得算 accepted；第一個新合格週期 counter=1，第二個=2/ACCEPTED。若 previous counter>0，仍必須完整驗證 cadence/natural/artifact/marker/locks/status chain，偽造 counter不得累加。
4. `F-004`：Fog metadata 由 wrapper 自產，避免 child/caller自述；非 Fog jobs 保留既有 `TOP10_STORAGE_SCHEDULED_AT`／`TOP10_STORAGE_INVOCATION_ID` override 語意並補 regression。
5. Cadence drift 由 300 秒縮至 fail-closed 60 秒，receipt 明示 `natural_provenance_method=ARCHIVED_RECEIPT_CADENCE_V1`。不要聲稱能區分惡意的 exact-cadence kickstart；Owner 已限制驗收期間不得 kickstart，且本卡禁止新增第二 authority。
6. 補 writer failure 前／中／後或等價 atomic publication regressions，確認不留下可被 reader 接受的 partial evidence；若 guarded worker writer失敗，既有 EXIT trap仍清 exact-owned locks。

驗證：重跑 Mainline probe、focused acceptance tests、`tests/test_storage_safety.py`、Fog validation/lock/signal/retry shell tests、`bash -n`、Python compile與 `git diff --check`。回報 changed files、RED/GREEN、仍失敗且不歸因本卡的證據；不得自行宣稱 live acceptance。

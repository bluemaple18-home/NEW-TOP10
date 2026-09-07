# Worker task — REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01

任務ID：`REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01`

卡片類型｜派工對象：strict/core-bounded Repair｜單一 implementation Worker。

請讀：`AGENTS.md`、`docs/tasks/2026-09-07_REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01.md`、`.work/REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01/context_manifest.md`，再按 manifest 只讀必要 source/test 區段。

任務目的：以 TDD 完成 `FOG-NAE-SLICE-001`～`003`。沿用既有 Storage Guard archived receipts；新增的 terminal evidence 只是單次 invocation artifact，不是新 ledger。請在 shared workspace 直接修改允許檔案，Mainline 負責最終驗收。

硬限制：

- 不 manual kickstart、不清 marker、不寫 production runtime、不 deploy、不 push、不 commit。
- 不硬寫 `natural_trigger_verified=true`；PPID=1／`trigger_type=natural` 只能是候選。
- 不讀任何未綁定 exact invocation 的 latest artifact/receipt 作 acceptance。
- 不回填或改寫既有 live receipt，不新增 scheduler/DB/ledger/daemon/heartbeat。
- 不碰 ME-D1、ranking/model/publish、Fog 研究邏輯與卡片／backlog／frontier／handoff／`.work` control artifacts。

必要行為：

1. 先只寫並實跑一個能重現「child OK 但 exact artifact evidence 缺失仍不得 accepted」的 observable RED；確認因目標症狀失敗後才做 minimal GREEN。後續 scenario 仍維持逐一 red→green。
2. worker 在 guarded production invocation 且最終 artifact 成功時，atomic publish exact invocation terminal evidence；至少含 schema、job、scheduled_at、invocation_id、run_id、artifact_run_date、terminal result、canonical artifact path/hash。既有檔案不可覆寫。
3. wrapper 把它自行決定的 job/scheduled_at/invocation_id 傳給 child；不可讓 child 自述 natural origin。
4. guard 只在 child exit、final process group quiescent 後驗 exact evidence：安全 regular file、invocation/job/date/run_id/path/hash/event terminal status 全部相符。wrong/latest/symlink/path traversal 一律拒絕。
5. cadence verifier 只讀 `scripts/com.new-top10.fog-research-worker.plist` 的 StartInterval 與 `logs/storage_safety/receipts/fog-research-worker/*.json`；相鄰 archived receipt、scheduled_at 與 invocation timestamp 必須一致且在 bounded drift 內。不得加入新的 cadence ledger/anchor。
6. accepted counter 只有 current exact artifact valid、cadence verified、child exit=0、final quiescent、denial marker absent、Fog worker及 queue lock absent時，才由前一合格 receipt 的 counter+1；否則 0/pending。兩輪才 `ACCEPTED`。
7. 非 Fog jobs 與 validation-only 行為維持既有語意。

驗收：

- 四個指定 cases：missing evidence→pending/0；valid artifact＋unverified cadence→pending/0；兩者 valid→counter+1；連續兩輪→ACCEPTED/2。
- hostile cases：wrong invocation/latest/date/hash/path/symlink、錯 cadence、denial marker、殘留 lock 都 fail closed。
- 跑 focused tests、相關 `tests/test_storage_safety.py` 與 Fog validation tests、`bash -n`、`git diff --check`。
- 把實跑 RED/GREEN 指令、精簡輸出與變更檔案回報 Mainline；不要自行宣稱 live natural acceptance 完成。
- 若需要超出 allowlist，或 archive cadence 無法在不新增 authority 的情況下成立，立即停止並回報 fork。

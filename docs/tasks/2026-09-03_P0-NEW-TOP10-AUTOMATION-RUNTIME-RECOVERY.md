---
id: P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-20260903
chain_id: NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-20260903
status: PARTIAL_RECOVERY_NATURAL_ACCEPTANCE_PENDING
type: recovery-program
priority: P0
owner: TOP10new operations
role: mainline
cycle: 1
thickness: strict
risk: critical
model: gpt-5.6-sol
reasoning: high
model_reason: 八個正式排程的 production runtime truth 已與先前「修好」宣稱分離，且同時涉及 storage fail-closed、runtime lifecycle、scheduler acceptance 與跨 writer 隔離；需先固定 authority 與 acceptance，再切 bounded implementation slices。
date: 2026-09-03
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
external_write_allowed: false
---

# P0 — NEW-TOP10 Automation Runtime Recovery

👉 [假設與目標確認] 目標：把 NEW-TOP10 八個正式 launchd job 的「有設定」恢復成「可證明自然排程有執行、child 有完成、正確日期產物有落地」；邊界：本卡只建立 recovery authority／切片／驗收契約，現在不清 marker、不重啟或 enable launchd、不殺 PID、不 deploy、不 push、不送外部 review；驗收：不得再以 plist、manual run、unit test、clean-room 或 `launch_verified=true` 單獨宣稱 automation 已修復。

## 0. P0 判定

目前 automation 應視為：

`NO-GO / PRODUCTION AUTOMATION NOT ACCEPTED`

截至 2026-09-03 的 runtime audit：

- 正式 launchd job 共 8 個。
- Enabled 3 個：`daily`、`external-review-preflight`、`fog-research-worker`；三個都沒有可接受的健康 runtime 證據。
- Disabled 5 個：`reference`、`retrain`、`pm-research-harness`、`external-review`、`baseline-harness`；目前不得假設這五個都應重新啟用。
- `daily`：2026-09-02 17:30 natural trigger 因 `UNREGISTERED_WRITE_PATH` 形成 persistent restart-denied；2026-09-03 17:30 被 `PERSISTENT_RESTART_DENIED_MARKER` 擋住，child 未 spawn。最新實際成功 daily artifact 的 `run_date=2026-09-01`，完成於 2026-09-02 11:17，且 `metadata.trigger=manual`；沒有 2026-09-02／2026-09-03 對應的自然排程 ranking/report/publish 成功證據。
- `external-review-preflight`：8/27、8/28、8/30、9/1、9/2、9/3 均有失敗；9/3 provider receipt 證明 ChatGPT 與 Gemini 都在 child 內因 `mktemp` 無法於 `logs/storage_safety/runtime/external-review-preflight/tmp` 建檔而失敗。這不是 provider login/auth RCA。
- `fog-research-worker`：launchd 可顯示 `running`，但 latest receipt 為 `RESTART_DENIED`、`child_exit_code=null`，且 stale Python guard 持有 worker lock/log；supervisor alive 不等於 workflow alive。
- 2026-09-03 09:32:49 另一條 Mainline 寫 `docs/tasks/2026-09-03_MONITOR-NEW-TOP10-FOG-LIVE-REVALIDATION.md`，09:32:55 worker 收到 SIGTERM，09:33:05 marker 記錄 `UNREGISTERED_WRITE_PATH`。RCA 已證明 worker 本身沒有寫 `docs/tasks/`；代表 production guard 會把同 checkout 內其他開發 writer 的變更誤判成 production child 未登記寫入。

因此過去任何「manual 跑成功」「clean-room 兩輪成功」「plist 已安裝」「`launch_verified=true`」「evidence-preservation repair 已在 main」都只能算 partial evidence，不能再寫成 scheduler restored。

## 1. 已確認 root causes

### RC-1 — Production runtime 與 active development 共用 checkout

`app/storage_safety.py::project_write_snapshot()` 對整個 repo 建立 before/after snapshot；`unknown_changed_paths()` 只依 `registered_write_paths` 判定路徑是否可接受，沒有 writer/process attribution。

結果：只要 production child 執行期間，另一條 Mainline／Codex／人工在同 checkout 改到非 registered path，guard 就可能把外部 writer 的變更算到 production child，進而 SIGTERM child 並寫 restart-denied。

這是 architecture boundary 問題，不是加一條 allowlist 就能正確解決。

### RC-2 — Storage reclaim 會刪掉 child 即將使用的 TMPDIR

目前順序：

1. `scripts/run_with_storage_guard.sh` 先建立 `logs/storage_safety/runtime/<job>/tmp` 等目錄並 export `TMPDIR`。
2. `app/storage_safety.py::run_guarded_job()` 在 child spawn 前先執行 `reclaim_allowlisted(..., execute=True)`。
3. retention rule `runtime_workspace` 可把空 runtime directory `rmdir` 掉。
4. child 才 spawn；`review_chatgpt_chrome.sh`／`review_gemini_chrome.sh` 用 `mktemp "${TMPDIR}/..."` 時，父目錄已不存在。

所以 `external-review-preflight` 的目前失敗是 deterministic local lifecycle bug。

### RC-3 — Supervisor/lock/health truth 沒有與 child workflow truth 分開

Fog 現況能出現：launchd `running` + guard PID 還在 + lock 還被持有，但 child 已 SIGTERM／沒有有效 progress／latest receipt 已 restart-denied。

因此 `launchd running`、PID 存在、lock 存在都不能作為 job healthy 的充分條件。

### RC-4 — 「排程已觸發」與「工作已成功」沒有 canonical acceptance contract

目前多份歷史驗收把 static config、manual run、clean-room、installed plist 或單次 receipt 混合成「已修復」。缺少 natural schedule → child → terminal result → dated artifact → publish/send 的完整鏈，造成 false completion。

## 2. Prior art / 開源研究

本卡只吸收設計原則，不新增第二套 scheduler、daemon、workflow engine 或 telemetry service。

### PA-1 — Git worktree：隔開 active development 與 runtime working tree

來源：Git 官方 `git-worktree` 文件
https://git-scm.com/docs/git-worktree

官方定義：同一 repository 可以有多個 working tree，各自有獨立 working-tree state／HEAD 等 metadata；可在不干擾既有 working tree 的情況下使用另一個 checkout。

分類：`ABSORB`

採用點：

- Production launchd 不再直接指向 active development checkout。
- 優先使用既有 Git/runtime seam 建 dedicated `<runtime-checkout>`；它仍由同一 canonical repo/commit 供應 code，不建立第二個 source authority。
- runtime checkout 只供 scheduler/runtime 使用；開發者 task/doc/code mutation 留在正常 development worktree。

限制：Git worktree 本身不是 process sandbox，也不解決所有 filesystem isolation；這裡只吸收「不同 working tree 隔開 mutable file view」的能力。

### PA-2 — systemd `RuntimeDirectory=`：runtime directory 應由 service lifecycle 明確擁有

來源：systemd 官方 repository `systemd.exec`
https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml

官方文件把 `RuntimeDirectory=` 定義成 service 可寫 runtime directory，並由 service lifecycle 管理／在 unit 終止時移除；`StateDirectory=`／`CacheDirectory=`／`LogsDirectory=` 則分開不同持久性用途。

分類：`ABSORB`

採用點：

- `tmp/cache/state/log` 的建立、reclaim、child spawn 必須有單一清楚順序與 ownership。
- `TMPDIR` 在 child spawn 前必須存在，且不能被同一次 pre-spawn reclaim 刪掉後不重建。
- 不引入 systemd；只吸收 runtime path lifecycle contract。

### PA-3 — Kubernetes CronJob + Job：schedule creation 與 terminal completion 是兩層 truth

來源：Kubernetes 官方 CronJob / Job 文件
https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/
https://kubernetes.io/docs/concepts/workloads/controllers/job/

官方模型把 CronJob 定義為「按 schedule 建立一次性 Job」，而 Job 另有 terminal `Complete`／`Failed` 狀態；CronJob 也保留 originally scheduled timestamp，並明示排程可能出現 missed/duplicate creation，所以 workload 應具 idempotent semantics。

分類：`ABSORB`

採用點：

- NEW-TOP10 receipt 必須分開 `scheduler_triggered`、`child_spawned`、`child_terminal_status`、`artifact_date`、`publish_result`。
- 只看到 launchd trigger/PID 不得推導 workflow success。
- acceptance 必須比對 expected scheduled time 與實際 artifact run date。

### PA-4 — Healthchecks.io heartbeat：start / success / fail 是 scheduled job 最小觀測語義

來源：Healthchecks.io 官方 docs
https://healthchecks.io/docs/

其 cron monitoring 把 execution start、success、fail 分開，且「有 start、在 grace time 內沒有 success」即視為 failure。

分類：`REFERENCE_ONLY`

採用點：只參考三態 heartbeat/receipt 語義；本期不新增外部 Healthchecks.io dependency。

### PA-5 — OpenTelemetry FaaS timer semantic conventions

來源：OpenTelemetry 官方 semantic conventions
https://opentelemetry.io/docs/specs/semconv/faas/faas-spans/

其 timer-triggered invocation 有 trigger type、cron expression、invocation id、invocation time 等欄位。

分類：`REFERENCE_ONLY`

採用點：若現有 receipt 欄位命名不足，可參考 `trigger`／`scheduled_at`／`invocation_id`；目前規格仍標 Development，不把它升成 NEW-TOP10 authority，也不因此導入 OTel SDK。

## 3. Minimum sufficient / 不吸收什麼

### why_not_less

- 只修 TMPDIR：daily/fog 仍會被 active development writer 誤殺。
- 只清 restart-denied marker：下一次同條件仍可再產生 denial，且等同把證據清掉後重試。
- 只加 `docs/**` 到 allowlist：會讓 production child 真正寫 docs 時也被合法化，破壞 fail-closed 邊界。
- 只看 launchd exit/PID：fog 已證明 supervisor alive 可與 workflow dead 同時存在。
- 只跑 manual acceptance：不能證明 scheduler owner、calendar trigger、installed plist 與 production environment 的完整鏈。

### why_not_more

- 不建 process-attribution database／writer ledger，除非 A0 runtime checkout isolation 做完後仍有 measured gap。
- 不換 scheduler、不導入 Kubernetes/systemd、Temporal、Airflow、Celery 等第二 runtime。
- 不新增外部 heartbeat SaaS 作為恢復前置依賴。
- 不一次 enable 五個目前 disabled job。
- 不重寫 Storage Guard；優先修既有 seam 的 lifecycle 與觀測邊界。

### do_not_absorb

- Kubernetes controller architecture。
- systemd daemon／unit model。
- Healthchecks.io hosted service dependency。
- OpenTelemetry 全套 SDK/collector。
- 通用 distributed lock service、PKI、RBAC、writer registry。

## 4. Recovery slices 與實作順序

主依賴：

`A0 → (A1, A2, A3) → checkpoint → A4 → A5 → A6`

`A7` 可與 A1–A3 並行做 minimal slice，但不得為了 dashboard/telemetry 延後 runtime recovery。

### A0 — Runtime / Checkout Isolation（P0，第一阻塞）

Objective：Production scheduler 不再觀察 active development checkout 的一般 mutation。

實作方向：

1. 盤點 `scripts/setup_launchd.sh`、八份 `scripts/com.new-top10.*.plist` 與所有 project-root resolution seam。
2. 建立單一 `<runtime-checkout>` 概念；優先用 Git linked worktree 或既有 deployment checkout seam，pin 到明確 accepted commit。
3. launchd `ProgramArguments`／`WorkingDirectory` 必須解析到 `<runtime-checkout>`，不是人日常開發的 `<repo-root>` working tree。
4. code authority 仍是同一 Git repo/commit；runtime checkout 不接受日常 task card/doc/code editing。
5. `logs/artifacts/data/models` 是否留在 runtime checkout 或導向既有受控 runtime root，要依現有 storage policy 選 minimum delta；不得創第二 canonical data authority。
6. 寫 deterministic test/fixture：在 guard 監控 `<runtime-checkout>` child 時，同步修改另一個 development worktree 的非 registered path，guard 不得報 `UNREGISTERED_WRITE_PATH`；若直接改 runtime checkout 的同類 path，仍必須 fail closed。

候選 seam：

- `scripts/setup_launchd.sh`
- `scripts/com.new-top10.*.plist`
- `scripts/run_with_storage_guard.sh`
- scheduler/path verification scripts
- targeted tests

Acceptance：

- installed candidate config 能證明 scheduler root 與 active development root 不同。
- concurrent dev write reproduction 不再殺 production child。
- runtime checkout 內真正 unknown write 仍會被 Storage Guard 阻擋。
- 沒有新增 scheduler authority、database 或常駐 daemon。

### A1 — Storage Guard attribution boundary / false-positive prevention

Objective：guard 只對「這個 runtime 應負責的 filesystem boundary」做可靠判斷，不把無關 writer 的 mutation 算到 child。

實作方向：

1. A0 完成後重新跑原本 fog false-positive reproduction。
2. 若 dedicated runtime checkout 已完全消除 cross-writer mutation，A1 僅補 root invariant/assertion 與 regression test，不新增 writer attribution 機制。
3. 若仍存在必要共享 writable root，再把 snapshot scope 限到 runtime-owned protected roots，或用既有 process-group/known output seam 做最小 attribution；不可先發明 global writer registry。
4. 保留 `registered_write_paths`、meter、hard capacity ceilings、unknown write fail-closed semantics。

主要 seam：`app/storage_safety.py::project_write_snapshot()`、`unknown_changed_paths()`、`registered_changed_paths_outside_meter()`、`tests/test_storage_safety.py`。

Acceptance：external dev writer 不再造成 false positive；runtime child 真實 unknown write 仍 deterministic NO-GO。

### A2 — TMPDIR / reclaim lifecycle repair

Objective：pre-spawn reclaim 不得破壞 child 的必需 runtime directories。

RED 必須先重現：

`wrapper mkdir/export TMPDIR → reclaim_allowlisted removes empty runtime dir → child mktemp fails`

實作可接受兩種 minimum path，Mainline 依測試選一種：

- reclaim 完成後，在 `_spawn_verified_process_group()` 前以單一 helper 重新 materialize job runtime dirs；或
- 調整 reclaim rule/ordering，使 active invocation 的 required runtime dirs 不在 pre-spawn phase 被刪除。

要求：

- 不得只是讓 `review_chatgpt_chrome.sh`／`review_gemini_chrome.sh` 自己 `mkdir -p` 來掩蓋共同 lifecycle bug。
- `TMPDIR`、joblib、uv/XDG/Matplotlib cache 的 invariant 應由 guard/wrapper boundary 擁有。
- retention/reclaim 仍要有測試，不能因修 TMPDIR 而失效。

候選 seam：`scripts/run_with_storage_guard.sh`、`app/storage_safety.py`、`docs/operations/top10-storage-policy.json`（僅若測試證明 policy 需改）、`tests/test_storage_safety.py`、`tests/test_external_review_provider_preflight.py`。

GREEN：兩 provider 的 test child 均能在 guard lifecycle 下 `mktemp` 成功，且 reclaim/容量測試仍全綠。

### A3 — Fog supervisor / PID / lock lifecycle

Objective：child 已終止或 restart-denied 後，不得留下「launchd running 但 workflow dead」的假健康狀態。

實作方向：

1. 明確分 `supervisor_pid`、`child_pid/process_group`、`child_spawned`、`child_terminal_status`、`last_progress_at`。
2. guard 收到 SIGTERM、stop-loss、restart-denied、child exit 後，必須走 bounded cleanup/finalization；lock ownership 隨 owner process lifecycle 釋放。
3. stale lock repair 只能在能證明 owner PID 不存在／identity 不匹配時清理；禁止 blind `rm lock` 或 blind kill。
4. 若 process group 尚有 descendant，維持 fail closed 並留下 terminal receipt，不能只留一個永遠存活的 wrapper。
5. health verifier 必須能區分 `SUPERVISOR_ALIVE`、`CHILD_RUNNING`、`WORKFLOW_PROGRESSING`、`TERMINAL_SUCCESS/FAILURE`。

候選 seam：fog runner/supervisor scripts、storage guard process-group lifecycle、lock helper、fog runtime tests、ops verifier。

Acceptance：可 deterministic 重現 child SIGTERM/restart-denied，完成後無 stale owner lock；health 不再把僅 supervisor 存活判成 healthy。

### A4 — Activate denial evidence preservation dependency

Dependency：`docs/tasks/2026-09-03_REPAIR-NEW-TOP10-STORAGE-DENIAL-EVIDENCE-PRESERVATION.md`，main 已有 `3c85c38`。

這個 repair 的作用只限於「後續 persistent denial 仍保留首次原因與 path evidence」。它不是 automation recovery。

執行方式：

- A0–A3 code candidate 與 regression tests 通過後，再做 activation review／production preflight。
- 只有 Owner 額外授權 production activation 後，才可 clear 現有 marker、reload/restart launchd 或處理 live PID/lock。
- marker 清除前必須先保存原始 denial receipt/hash，不能用清 marker 取代 RCA。

Acceptance：原始 denial evidence durable；persistent denial 不洗掉 root cause；activation 不放寬 allowlist。

### A5 — Scheduler Runtime Acceptance Contract（禁止 false「修好了」）

從此任何 recurring job 只有滿足以下鏈才可標 `ACCEPTED`：

1. candidate code/config tests PASS。
2. installed/enabled scheduler owner 與 accepted source commit/path 一致。
3. 到達「自然排程時間」，不是 manual kickstart／manual run。
4. scheduler 真的建立本次 invocation，記錄 `scheduled_at`／`trigger_type=natural`／`invocation_id`。
5. real child `child_spawned=true`。
6. child terminal `exit_code=0`，且 supervisor/process group quiescent。
7. 產生應有「正確 run date」artifact；daily 不可拿前一日 manual artifact 充當本日成功。
8. 有 publish/send 的 job 必須有對應 publish/send terminal result；preflight 則必須有 provider-specific readiness result。
9. 沒有新的 restart-denied，沒有 stale PID/lock。
10. 下一個自然週期再次成功，才完成 recurring acceptance。

最低 natural acceptance：

- `fog-research-worker`：連續 2 個自然 cadence cycle。
- `daily`：連續 2 個 natural trading-day scheduled run。
- `external-review-preflight`：連續 2 個 natural scheduled run。

若因日曆時間無法在單次 implementation session 等到第二個 natural run，狀態只能是 `CANDIDATE_GREEN / NATURAL_ACCEPTANCE_PENDING`，不得改寫為「修好了」。不得用 manual run 代替第二個 natural cycle。

下列證據一律只能算 partial：

- plist exists / plist lint
- launchd loaded/enabled
- `launch_verified=true`
- unit/integration tests
- clean-room success
- manual run / manual kickstart
- process/PID exists
- artifact exists但日期/trigger 不符

### A6 — 五個 disabled job 的 intent reconciliation

Objective：A0–A5 恢復核心 runtime 後，逐一決定五個 disabled job 是 intentional retired/paused，還是 production 應啟用。

範圍：`reference`、`retrain`、`pm-research-harness`、`external-review`、`baseline-harness`。

做法：

1. 只讀比對 canonical docs、plist、歷史 receipts、現行 workflow owner。
2. 每 job 產生一個 verdict：`INTENTIONALLY_DISABLED` / `SHOULD_BE_PRODUCTION` / `SUPERSEDED` / `UNKNOWN_NEEDS_OWNER`。
3. 沒有 verdict 前不得 bulk enable。
4. `SHOULD_BE_PRODUCTION` 另開 activation slice，沿用 A5 natural acceptance。

Acceptance：八個 job 的 intent 全部有 canonical 狀態；不存在「plist 在 repo 裡，所以應該 enable」的推論。

### A7 — Ops status truth / observability 最小補強

Objective：消除 `automation_status.json`、manual success、launchd state 被誤讀成 global healthy。

最小欄位：

- `job`
- `scheduler_enabled`
- `scheduler_state`
- `scheduled_at`
- `trigger_type` (`natural` / `manual` / `validation`)
- `invocation_id`
- `child_spawned`
- `child_exit_code`
- `child_terminal_status`
- `artifact_run_date`
- `publish_or_provider_result`
- `restart_denied`
- `restart_denied_reason`
- `supervisor_pid`
- `child_pid`
- `lock_owner_status`
- `last_progress_at`
- `accepted_natural_cycles`
- `acceptance_status`

實作優先沿用既有 receipt/status writer；不建新 DB。Ops rollup 必須逐 job 顯示，global health 只能由各 required job 的 accepted state 聚合，不能由單一 manual success 推導。

## 5. Mainline 切卡規則

Mainline 應把本 program 拆成 bounded implementation/review cards，不允許 Worker 一次同時改 A0–A7。

建議順序：

1. `A0-RUNTIME-CHECKOUT-ISOLATION`
2. `A1-STORAGE-GUARD-WRITER-BOUNDARY`
3. `A2-RUNTIME-DIR-RECLAIM-LIFECYCLE`
4. `A3-FOG-SUPERVISOR-LOCK-LIFECYCLE`
5. Checkpoint：重跑三條 incident reproduction。
6. `A4-DENIAL-EVIDENCE-ACTIVATION-PREFLIGHT`
7. `A7-AUTOMATION-STATUS-TRUTH`（若 A5 缺 receipt 欄位，須在 A5 前完成 minimal slice）
8. `A5-NATURAL-SCHEDULER-ACCEPTANCE`
9. `A6-DISABLED-JOB-INTENT-RECONCILIATION`

每張 implementation card 都必須：

- RED reproduction 先於 fix。
- 指定 source seams 與禁止修改區。
- targeted tests + affected gate + `git diff --check`。
- activation/rollback 分開；code GREEN 不自動授權 production mutation。
- 若涉及 activation/rollback/teardown，依 AI Core 規則做兩個互不先讀 verdict 的獨立 Reviewer。

## 6. Program acceptance

本 P0 program 只有在以下全部成立才可關閉：

- A0 runtime checkout isolation 已在 installed scheduler path 生效。
- A1 cross-writer false-positive reproduction 綠，真 unknown runtime write 仍 fail closed。
- A2 TMPDIR/reclaim deterministic regression 綠，external-review-preflight 不再因本地 tmp lifecycle 失敗。
- A3 fog supervisor/lock 不再出現 stale-alive 假健康。
- A4 denial evidence preservation 已通過 activation boundary；原始 marker evidence 有保存。
- Daily、Fog、External Review Preflight 各自完成 A5 所要求的連續 natural cycle acceptance。
- 五個 disabled job 全部完成 A6 intent verdict；只有明確 `SHOULD_BE_PRODUCTION` 的 job 才進後續 activation。
- Ops status 能明確顯示 trigger、child、terminal、artifact、publish/provider、denial、lock 與 natural-cycle acceptance。
- 沒有任何地方再把 manual/validation success 顯示為 natural scheduler success。

Program terminal states 只允許：

- `ACCEPTED_AUTOMATION_RECOVERED`
- `PARTIAL_RECOVERY_NATURAL_ACCEPTANCE_PENDING`
- `BLOCKED_WITH_REPRODUCIBLE_EVIDENCE`
- `NO-GO`

禁止使用沒有 runtime acceptance evidence 的 `FIXED` / `RESTORED` / `HEALTHY`。

## 7. 目前 authority / Hard stops

這次 Owner 只授權「寫入 backlog，並先研究必要文獻／開源」。因此現在：

- 可：新增／更新本 program 與 operational frontier 文件。
- 不可：clear `restart_denied` marker。
- 不可：kill/restart stale PID、移除 live lock。
- 不可：launchctl bootstrap/bootout/kickstart/enable/disable。
- 不可：修改 installed plist。
- 不可：deploy／push／production 補跑／正式外部 review send。
- 不可：因為五個 job disabled 就直接 enable。

下一個 Mainline 動作：從 A0 開第一張 implementation card；code/test 可在取得正常 implementation authority 後進行，但 production activation 仍需獨立授權。

## 8. Implementation checkpoint — 2026-09-04 local candidate

Owner 後續已明確指派修復三條自動化，因此本段已取得 local code/test implementation authority；第 7 節的 production hard stops 仍全部維持。

- A0：獨立 detached runtime checkout + accepted 40-char SHA pinning candidate 已完成；development worktree 寫入不再進入 runtime write snapshot，runtime checkout 的 unknown write 仍 fail closed。
- A1：目前不新增 writer registry／DB；A0 的 checkout isolation invariant 已覆蓋本 incident measured gap。
- A2：pre-spawn reclaim 後會重建 active runtime TMP/cache workspace，避免 GPT／Gemini provider `mktemp` 因目錄被 reclaim 而失敗。
- A3：Fog／PM／research queue lock identity 改為 PID + process start token；identity mismatch 可安全 reclaim，identity unknown fail closed；Fog 自身 lock 已在 queue contention 前武裝 cleanup trap；Fog health 明確區分 supervisor、child、progress、terminal success/failure。

本輪新增一個 regression RED：`tests/test_fog_research_retry_circuit.sh` 在 sandbox 中因既有 fixture 未注入 process-identity `ps` seam，先於 retry assertions 退出 `cannot establish lock identity`。假說一「fixture wiring 落後於新 lock contract」成立：補入 deterministic fake `ps` 後原 retry circuit 行為 GREEN；假說二「應放寬 production lock identity fail-closed」因此不採用。

Checkpoint evidence：

- `tests/test_fog_runtime_health.py`：5 passed。
- A3 shell regressions（lock identity／contention／cleanup／retry circuit／runtime time wiring）：全部 GREEN。
- `tests/test_fog_storage_validation.py`：8 passed。
- storage process-group targeted regression：5 passed，69 deselected。
- A0/A2 affected pytest checkpoint：112 passed，35 subtests passed。
- modified shell `bash -n`：PASS。
- affected Python `py_compile`：PASS。
- `git diff --check`：PASS。

本 checkpoint 的當時狀態為 `CANDIDATE_GREEN / NATURAL_ACCEPTANCE_PENDING`；後續 A4 結果由下一節取代。

## 9. A4 activation checkpoint — 2026-09-04

Owner 後續分別明確授權 dormant runtime pin 與 A4 production activation；兩項授權均已使用完畢，不延伸成後續 production write authority。

- Fixed candidate：`ab7c4180422b028a6a2a39fa311ea0ba591d561e`。
- Runtime checkout 已 detached pin 到 fixed candidate；正式 validator 回 `RUNTIME_CHECKOUT_GO`。
- Daily、External Review Preflight、Fog 三條即時 storage measure 均 `PASS`。
- `scripts/activate_automation_runtime.py --activate` 單次執行 exit `0`，terminal status 為 `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`。
- 三份 installed plist 與 launchd owner 均切到隔離 runtime；未手動觸發 child。
- 原始 denial hash 已保存，runtime 端三個 restart-denied marker 均 clear。
- Activation receipt 與 post-activation verdict：`docs/evidence/P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-A4-PREACTIVATION-20260904/`。

目前 program terminal state：`PARTIAL_RECOVERY_NATURAL_ACCEPTANCE_PENDING`。

下一個 Mainline 動作只讀驗收 A5 自然週期；不得以 manual run／kickstart 代替。A6 disabled-job intent reconciliation 維持 `pending`，不得因 A4 成功自動 enable。

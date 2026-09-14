# ACTIVATE-TOP10-FOG-FD93D1B-01

- objective：只將 `com.new-top10.fog-research-worker` 從 `c69834a` 切換至固定 runtime `fd93d1b`。
- authority：Owner 於 2026-09-12 明確授權 Fog activation。
- constraints：不 manual run、不 kickstart、不 push；不修改 daily、external-review、preflight、retrain；保留舊 runtime denial marker；失敗必須由既有 transaction rollback 並驗證。
- preflight：runtime identity、host capacity、兩輪 representative validation、affected suite、installed plist 與 launchd prestate 均須通過。
- acceptance：activation receipt 為 `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`、failure 為空、rollback errors 為空、Fog loaded/not running 且只指向 `fd93d1b`；out-of-scope plist hashes 不變。自然週期 acceptance 另候排程證據。
- rollback：由 `scripts/activate_automation_runtime.py` 的 transaction handler 還原舊 plist、loaded state、disabled mask 與 denial mirror；不得另寫旁路部署流程。
- evidence：`docs/evidence/FOG-LIVE-SAMPLE-FD93D1B-REVALIDATION-20260912/summary.json` 為 `PASS_CANDIDATE`；affected suite `111 passed, 39 subtests`；activation transaction suite `95 passed`；host capacity gate `PASS`（project bytes `1,351,926,356`、files `13,464`、host free `58,489,454,592`、memory pressure pressure level `1`）。
- review：activation transaction entrypoint 與兩名 Reviewer `GO/GO` 的 `8fe9366` 版本 SHA-256 相同；`fd93d1b` 只變更 Fog sampling headroom 與直接測試。Rule 25 不適用，因本卡不建立 canary、publish、transaction/tag/push chain。
- status：`DEPLOYED / NATURAL_ACCEPTANCE_PENDING`；activation receipt status 為 `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`。

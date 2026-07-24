# REVIEW-RESEARCH-FUNDAMENTAL-VOLUME-01 Repair-1 Re-review

## Verdict

`REVIEW_GO`

原 findings `F-01`～`F-03` 全部關閉。本次只審查 Repair-1 是否滿足原修復驗收，不把 Repair Executor 自述當作 acceptance，也未擴張審查範圍。

## Fixed range

- parent：`78c6f3a418f88ceb9d1f2aeb1fddec811c870e2c`
- parent tree：`a29a98c0b8e6d1dee2f02dbfcd1eb17efe02d8be`
- candidate：`a28036a7797f9d1067698ae387d1a76231e917a8`
- candidate tree：`59be6c7292a9228690b24eeccc90a5ce01e6661a`
- branch reference：`codex/repair-research-fundamental-volume-01-01`
- Reviewer worktree：clean、detached at candidate SHA
- ancestry：candidate direct parent 與指定 parent 相同；`merge-base --is-ancestor` PASS

## Finding closure

### F-01／P1 — CLOSED

原 finding：Volume daily runner 對既有 ledger 不變量未 fail closed。

獨立證據：

- `scripts/run_volume_climax_warning_append_only_shadow.py:84` 新增完整 `validate_ledger()`。
- runner 在續寫既有 ledger 前呼叫 validator，完成新 observations／receipt 後再次驗證，通過才 atomic write。
- validator 覆蓋 schema、frozen contract、config path／SHA、日期唯一與排序、post-seal、source hashes、warning-only、raw／active counts、no-ranking-change、no-push、summary 與 promotion fail-closed。
- CLI corrupt fixtures 對 duplicate date、pre-seal date、mutated warning、missing source hash、missing config SHA、ranking mutation、push mutation均要求非零退出。
- combined component failure fixture驗證 receipt 為 `PARTIAL`；既有 automation test 驗證 production daily 保持 `allow_failure=true`。
- 實際 combined runner exit 0、status `OK`；combined verifier exit 0。

修復驗收：PASS。

### F-02／P2 — CLOSED

原 finding：Fundamental verifier 直接重用 builder，不是獨立重算。

獨立證據：

- `scripts/verify_fundamental_point_in_time_readiness.py` 不 import 或呼叫 builder／`build_payload()`。
- verifier 直接讀取 `features.parquet` 與 local fundamental cache，獨立解析 publication availability。
- verifier 獨立重算 stock coverage、trailing-20D liquidity Top200、D+10 maturity exclusion、最近 252 日 research gate 與 80% model gate。
- verifier驗證 features、regime 與 cache manifest hashes。
- `available_from` mutation fixture會使 synthetic artifact 與 oracle 分歧，並要求確實捕捉。
- 正式 independent verifier exit 0：`FUNDAMENTAL_POINT_IN_TIME_READINESS_OK`。

修復驗收：PASS。

### F-03／P2 — CLOSED

原 finding：Volume verifier 未完整覆蓋 frozen contract。

獨立證據：

- verifier 明確斷言 config SHA、完整 contract、source hashes、唯一 warning text、`production_ranking_changed=false`、`push_sent=false`。
- corrupt fixtures涵蓋 contract／source／warning semantics mutations。
- 59／60／61 observations 都經完整 validator，且 `promotion_ready=false`。
- combined verifier 對 Volume ledger 呼叫同一完整 invariant validator。
- Volume verifier exit 0：`VOLUME_CLIMAX_WARNING_APPEND_ONLY_SHADOW_OK`。

修復驗收：PASS。

## Independent commands

所有命令以 Reviewer worktree 為 cwd，使用既有專案 `.venv` interpreter：

| Command | Exit | Result |
|---|---:|---|
| `<main-repo>/.venv/bin/python -m py_compile scripts/run_volume_climax_warning_append_only_shadow.py scripts/verify_volume_climax_warning_append_only_shadow.py scripts/verify_fundamental_point_in_time_readiness.py scripts/verify_overlay_shadow_daily_monitor.py` | 0 | PASS |
| `<main-repo>/.venv/bin/python scripts/verify_fundamental_point_in_time_readiness.py` | 0 | `FUNDAMENTAL_POINT_IN_TIME_READINESS_OK` |
| `<main-repo>/.venv/bin/python scripts/verify_volume_climax_warning_append_only_shadow.py` | 0 | `VOLUME_CLIMAX_WARNING_APPEND_ONLY_SHADOW_OK` |
| `<main-repo>/.venv/bin/python scripts/run_overlay_shadow_daily_monitor.py` | 0 | combined `status=OK` |
| `<main-repo>/.venv/bin/python scripts/verify_overlay_shadow_daily_monitor.py` | 0 | `OVERLAY_SHADOW_DAILY_MONITOR_OK` |
| `<main-repo>/.venv/bin/python -m pytest -q tests/test_overlay_shadow_daily_automation.py tests/test_daily_automation_orchestrator.py` | 0 | `8 passed` |
| `git diff --check 78c6f3a418f88ceb9d1f2aeb1fddec811c870e2c..a28036a7797f9d1067698ae387d1a76231e917a8` | 0 | PASS |

## Provisioning evidence

- 上輪錯誤巢狀的 ignored `data/fundamentals/fundamentals/` 已從 worktree 移除，並保留於 Reviewer worktree 外的暫存區作可回復備份。
- local fundamental cache：116 份 flat JSON。
- features SHA-256：`62874f29d17b117cea58dbf429288deb4bc79b603a2b027347fdbb68a0c5b58a`
- regime SHA-256：`d67e3eb6e7bb089d71a3f7946cc3e3b1c3800ff5268319564c3cef4a759e3485`
- fundamental cache manifest SHA-256：`4daa0730c0d9d4ddba148c3706b38f487b8628f8e5876530c4745e7ce93991e2`
- industry map SHA-256：`86ca58072c0db0581df741e212b0bccc641848638b52b4ae1e3b1a0b4e96cb20`
- ignored research inputs／receipts 不屬於 evidence commit。

## Scope and boundaries

- Repair changed files符合卡片 allowlist。
- 未修改 repair implementation。
- 未存取元大 secure attachment。
- 未抓取外部資料。
- 未修改 production ranking、model、weights 或 push。
- 未 merge、未 push。

## Remaining risks

- ignored research inputs／runtime receipts 不屬於 commit，跨機 re-review 仍須以 artifact hashes provision。
- Fundamental oracle 與 builder 是刻意獨立的兩套 publication logic；未來正式 contract 變更時必須同步更新，否則 verifier會 fail closed。

## Acceptance

在固定 candidate SHA 上，F-01～F-03 均有靜態實作、adversarial fixture、runtime receipt 與 regression tests 的獨立證據。未發現任何原 finding 仍未關閉。

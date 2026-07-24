# REPAIR-RESEARCH-FUNDAMENTAL-VOLUME-01-01

## Scope

- parent：`78c6f3a418f88ceb9d1f2aeb1fddec811c870e2c`
- reviewed candidate：`4deb72660dce9fc15f44d45e30307eb24f0caae1`
- review no-go：`9a90e5317c8c61745bd7273cdc865019399b9525`
- 僅修復 `F-01`～`F-03`。
- 未新增研究訊號、未調整門檻、未抓取外部資料，未修改 production ranking／model／weights／push。

## Fixed findings

### F-01：Volume runner fail closed

- 續寫前驗證 schema、frozen contract、config path／SHA。
- 驗證 observation 日期唯一、嚴格排序、全部晚於 seal，並拒絕回填 ledger 尾端以前的漏日。
- 驗證 features／ranking source hashes、warning-only 語意、raw／active counts、no-ranking-change、no-push 與 summary promotion fail-closed。
- 完成新 observations 與 receipt 後，再對完整 ledger 驗證一次才 atomic write。

### F-02：Fundamental 獨立 verifier

- verifier 不再 import 或呼叫 builder／`build_payload()`。
- 直接讀取 `features.parquet` 與 local fundamental cache，獨立解析 publication availability。
- 獨立重算 stock coverage、逐日 trailing-20D liquidity Top200、D+10 maturity exclusion、最近 252 日 research gate 與 80% model gate。
- 驗證 features／regime／cache manifest hashes。

### F-03：Volume frozen-contract verifier

- 明確斷言 config SHA、完整 contract、source hashes、唯一 warning text、`production_ranking_changed=false`、`push_sent=false`。
- corrupt fixtures 以 CLI 非零退出驗證 duplicate date、pre-seal date、mutated warning、missing source hash、missing config SHA、ranking mutation 與 push mutation。
- 59／60／61 observations 均明確驗證 `promotion_ready=false`。
- combined verifier 會對 Volume ledger 呼叫相同完整 invariant validator。

## RED

以 parent `78c6f3a…` 原始碼執行合成 corrupt-ledger fixture：

- 結果：`RED_OLD_RUNNER_ACCEPTED_MUTATED_WARNING`
- 原 Fundamental verifier 仍命中：
  - `17: build_payload,`
  - `23: assert artifact == build_payload()`

上述分別重現 F-01 的 fail-open 與 F-02 的共同邏輯依賴。

## GREEN

| Command | Exit | Result |
|---|---:|---|
| `<main-repo>/.venv/bin/python -m py_compile ...` | 0 | 4 scripts compiled |
| `<main-repo>/.venv/bin/python scripts/verify_fundamental_point_in_time_readiness.py` | 0 | `FUNDAMENTAL_POINT_IN_TIME_READINESS_OK` |
| `<main-repo>/.venv/bin/python scripts/verify_volume_climax_warning_append_only_shadow.py` | 0 | `VOLUME_CLIMAX_WARNING_APPEND_ONLY_SHADOW_OK` |
| `<main-repo>/.venv/bin/python scripts/run_overlay_shadow_daily_monitor.py` | 0 | combined `status=OK` |
| `<main-repo>/.venv/bin/python scripts/verify_overlay_shadow_daily_monitor.py` | 0 | `OVERLAY_SHADOW_DAILY_MONITOR_OK` |
| `<main-repo>/.venv/bin/python -m pytest -q tests/test_overlay_shadow_daily_automation.py tests/test_daily_automation_orchestrator.py` | 0 | `8 passed` |

Combined monitor 第一次在缺少 ignored `stock_industry_map.csv` 時，chip／event 非零且 receipt 正確為 `PARTIAL`；補入同一台主 repo 的本機 ignored inputs 後，第二輪為 `OK`。production daily 的既有 allow-failure test 仍通過。

## Fixtures

- corrupt ledger：duplicate、pre-seal、mutated warning semantics、missing features source hash。
- frozen contract：missing config SHA、`production_ranking_changed=true`、`push_sent=true`。
- point-in-time mutation：把 synthetic cache 的 `available_from` 從 `2025-01-01` 改到 `2030-01-01`，獨立 oracle 必須與原 artifact projection 分歧。
- promotion boundary：59／60／61 observations 全部維持 fail-closed。
- combined receipt：Volume component 非零時 status=`PARTIAL`、failed component 正確、promotion／production ranking 均為 false。

## Local provisioning

為執行正式 verifier，只從同一台主 repo 複製既有 ignored `features.parquet`、116 份 fundamental cache、regime artifact、industry map 與既有 shadow ledgers至此 worktree。未連網、未抓取新資料，且 `git status` 未追蹤這些 inputs。

## Remaining risks

- ignored research inputs／runtime receipts 不屬於 commit；跨機 re-review 仍需按 artifact hashes provision 相同資料。
- Fundamental oracle 與 production builder 刻意採兩套實作；未來 publication 規則若正式變更，兩者都必須各自更新，否則 verifier會 fail closed。
- 本 repair candidate 尚未經原 Reviewer re-review，不宣稱 accepted、merge-ready 或可 promotion。

## Re-review

本文件所屬單一 Repair candidate commit 的完整 SHA 由交付訊息固定，交回原 Reviewer thread `019f9241-fe47-7ef0-accf-3e021a49c401`。

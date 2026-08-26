# REPAIR-TOP10-STORAGE-FOG-REVALIDATION-04-1｜Verification

## 收卡狀態

`READY_FOR_REVIEW / FOG_NO_GO_SWAP_GROWTH_BUDGET_EXCEEDED`

Repair generation：`2`（final allowed generation）；reviewed generation-1 candidate：
`bd7fa8d67409e7db439c3a3f8640ae18aaf8472b`；targeted remaining finding：
`FOG-REV04-P1-002`。

本 Repair 只修復 `FOG-REV04-P1-001` 與 `FOG-REV04-P1-002`。沒有執行 fog workload、cycle、
代表性 workload、retry、launchd、merge、push、deploy或外部服務操作；fresh 與前代 sandbox、
marker、contract、restart denial及 raw receipt全程只讀。

## Root question 判定

`READY_FOR_REVIEW`：implementation 卡已收斂為 `ready_for_review` 並保留 swap blocker；共用 storage guard
改以 monotonic absolute deadline 排程 live sample，並以有效 safety observation 的完成時間衡量
cadence。未來任一 scheduled live gap或單次 sampler duration使完成間距實際超過 policy interval
時，會立即加入 `LIVE_SAMPLE_CADENCE_EXCEEDED`、終止同一 verified PGID、跳過額外 final sample、
保存 persistent restart denial並回 `70`。既有 cycle 1 raw reason仍只有
`SWAP_GROWTH_BUDGET_EXCEEDED`，post-run cadence finding另欄保存，沒有改寫歷史 guard判定。

Storage safety的整體上線判定仍為 `NO-GO`；cycle 2、retry 與任何 fresh workload均禁止，必須先
通過 targeted Repair Review並由主線取得新的 fresh activation。

Generation-2 只修正一項 phase edge：sampling開始時 child存活，但 overlong sampler完成前 child
正常退出時，completion gap仍獨立觸發 cadence stop。Sample phase仍可標成 `final`，但不得吞掉
`LIVE_SAMPLE_CADENCE_EXCEEDED`；cadence stop後不再執行額外 final sample。

## Finding trace

### FOG-REV04-P1-001

- `docs/tasks/2026-08-03_TOP10-STORAGE-FOG-REVALIDATION-04.md`：frontmatter 改為
  `status: ready_for_review`、`blocker: SWAP_GROWTH_BUDGET_EXCEEDED`，blocker detail與收卡段落
  明示 cadence violation、cycle 2／retry／fresh workload均禁止。
- `docs/tasks/2026-08-03_REPAIR-TOP10-STORAGE-FOG-REVALIDATION-04-1.md`：generation-1 Repair
  收斂為 `ready_for_review`，不標 completed或可再次派工。

### FOG-REV04-P1-002

- `app/storage_safety.py`：`run_guarded_job()` 以 `time.monotonic` 的 absolute deadline計算下一次
  wait，並比較有效 observation 的 monotonic完成時間；snapshot／sample overhead不再累加成下一輪
  完整 interval。Cadence safety判斷不使用 `Sample.timestamp` wall clock。
- 同一路徑在 gap `> sample_interval_seconds` 時加入穩定 reason
  `LIVE_SAMPLE_CADENCE_EXCEEDED`，再走既有 dedupe、verified PGID termination、denial、receipt
  與 exit `70`。
- `tests/test_storage_safety.py`：deterministic fake monotonic clock與process waiter證明 2秒sample
  overhead下 scheduled sample仍落在 `0/10/20` absolute cadence，wait為 `8/8`而非累積 drift；
  另以 11秒 gap證明 reason、target PGID termination、persistent denial與 `70/75`。
- 單次 sampler本身耗時11秒、interval為10秒時，在第一次 live observation完成點立即 reason-coded
  stop；process waiter呼叫數為 `0`，receipt只含 `preflight/live`，未再執行 scheduled或final sample。
- Generation-2 regression讓 child在 scheduled sampler的11秒 overhead內正常 exit `0`；receipt
  保留 `preflight/live/final` 三筆 evidence，但結果必須是 `STOPPED`／guard `70`、persistent denial，
  不得回 generation-1 的 `OK`／`0`，也不得再追加另一筆 final sample。
- 測試刻意提供倒退的 wall timestamps，證明 cadence safety只依 monotonic time；既有
  first-write、immediate、fast child、hard runtime、swap/RSS、PGID與receipt tests全數通過。

### 既有 evidence 誠實補記

- `cycle-1.json` raw `reasons`與 restart-denial reasons均精確保持
  `['SWAP_GROWTH_BUDGET_EXCEEDED']`。
- 新增 `post_run_findings.live_sample_cadence`：兩段精確 gap為 `60.485444`、
  `61.7187129` 秒，最大 `61.7187129`，ceiling `60`，reason
  `LIVE_SAMPLE_CADENCE_EXCEEDED`。
- `verification.md` 明示這是 post-run evidence finding，不是 raw guard reason；監控契約亦失敗，
  未來必須先通過 Repair Review與新的 fresh activation才能重跑。

## RED → GREEN

RED（新增 regression、實作前）：

```text
2 failed, 38 deselected
TypeError: run_guarded_job() got an unexpected keyword argument 'monotonic_clock'
```

Sampler-duration edge RED（completion-aware修復前）：

```text
1 failed, 40 deselected
AssertionError: wait_calls 1 != 0
```

Focused GREEN：

```text
3 passed, 38 deselected in 0.26s
```

Generation-2 精確 RED：

```text
1 failed, 41 deselected
AssertionError: 0 != 70
```

Generation-2 focused GREEN（新edge、absolute deadline、sampler overrun、fast child、normal exit、
PGID／denial）：

```text
7 passed, 35 deselected in 0.92s
```

Affected suites：

```text
50 passed, 16 subtests passed in 4.84s
```

執行範圍：`tests/test_storage_safety.py tests/test_fog_storage_validation.py`；這些是 deterministic
tests，沒有啟動 fog workload或cycle。

Full suite：

```text
1 failed, 683 passed, 4 warnings, 270 subtests passed in 62.75s
```

唯一 failure仍為既有 ledger evidence gap：
`tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`。
本 Repair沒有修改該路徑，新增 cadence regression沒有其他 failure。

## Machine evidence與只讀 digest核對

- `cycle-1.json` parse與 Decimal gap重算：`PASS`；size `5363` bytes；bounded JSON SHA-256
  `4341084c5d42e96d7564eccf1e202584259a83eaa8a0e1924413b676dbf72694`。
- Fresh marker：`9fbe2790dd164b6f4d6484c1a4452c92cea5faa79a1ed6b0b2426d0b4b1bb968`。
- Fresh contract：`d010144130c0cac4f6dca0155d172147977b8b2c6e227105b743874e87f9b0b8`。
- Fresh entrypoint：`661b9a1b10dc8f932eb7c99afa7502cea34f416c07758ccb8cbe8615494427cd`。
- Fresh runner：`2780a484e51950b2a6c30089d16111051f5bb3db71fe14e4be74d71923c8ae17`。
- Fresh restart denial：`5d926ebd12a574b30a287f6940fc250bf218f85c932db6e0d8d8bc2b263dd557`。
- 前代 marker：`6c0af0aa838fea1e65524cd87f17f9ace19293ee4d84f3ea3dd3b29ec65d058e`。
- 前代 restart denial：`eea4c1027f1b944b96ffba9c9ee7abcedaacb81fedaf35d10919d17409ea91bb`。
- `<main-checkout>` protected hashes仍精確為
  `c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`、
  `ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`、
  `f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`；dirty path集合仍為前代三檔。
- `git diff --check`：`PASS`。

## Generation-2 changed files與 candidate契約

- `app/storage_safety.py`
- `tests/test_storage_safety.py`
- `docs/tasks/2026-08-03_REPAIR-TOP10-STORAGE-FOG-REVALIDATION-04-1.md`
- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-04/verification.md`
- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-04/repair-1-verification.md`

Changed files全在 allowlist。Generation-2 candidate為本檔所在的單一 commit；其 parent必須精確為
generation-1 candidate `bd7fa8d67409e7db439c3a3f8640ae18aaf8472b`。本 Repair不自審、不建立 Reviewer；主線應喚醒
既有 Reviewer `019fc6fc-7a02-79b1-bc99-856efa7cb2ac` 做 targeted re-review。

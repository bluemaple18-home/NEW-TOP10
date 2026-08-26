# TOP10-STORAGE-GUARD-DEADLINE-NORMAL-RETURN-01 Verification

## Status

`READY_FOR_REVIEW`

這是 standalone shared storage guard candidate；不改寫前一 fog revalidation chain 的
`BLOCKED / REVIEW_REPAIR_LIMIT`，也不授權 fog workload、fresh revalidation、production launch、
merge、push或deploy。

## Identity 與 scope

- Formal thread：`019fc73e-bafe-7ca1-ac93-f04dbbb4e44f`
- Project ID：`local-49c40f44270697f9bce80f898c3c5a4d`
- Provisioning HEAD：`dcf3ece6847b3a3c3c4c8b3945ea2318fe411899`
- Source candidate／provisioning HEAD第一親代：
  `7bd4dc0d36eda40847bb5604e3d7f3d2c4dbddf2`
- CodeGraph indexed SHA：`dcf3ece6847b3a3c3c4c8b3945ea2318fe411899`
- CodeGraph exact symbol／impact：`run_guarded_job()` 位於 `app/storage_safety.py`，影響入口為
  `scripts/storage_safety.py:main` 與 `tests/test_storage_safety.py` guard regressions。首次自然語意
  context未命中；精確 symbol query後取得 public seam與 28-symbol impact。

## Root question 與 hypotheses

Root question判定為 `PASS_CANDIDATE`：waiter在 sample deadline後因 child exit `0` 正常回傳時，
guard現在以實際 monotonic completion fail closed，回 `70`、receipt `STOPPED`、保留
`child_exit_code=0`、建立 persistent restart denial，且不新增 scheduled／final sample掩蓋逾期。

- 主假說確認：故障只存在於 normal-return path缺少 completion deadline判定；最小 `else` path
  修復使同一 RED轉綠。
- 相鄰假說確認：`runtime_deadline <= next_sample_deadline` 時，normal return仍只產生
  `HARD_RUNTIME_EXCEEDED`。
- On-time假說確認：deadline前 normal exit `0` 維持 `0 / OK / reasons=[] / denial absent`。
- 未改 public signature、policy/schema/ceiling、sampler、timeout scheduler、receipt schema或
  process-group identity契約。

## RED → GREEN

RED command：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_storage_safety.py::StorageSafetyRegressionTest::test_late_normal_return_after_sample_deadline_fails_closed
```

RED結果：`1 failed`，actual精確為：

```text
(0, "OK", 0, [], false, ["preflight", "live", "final"])
```

Expected：

```text
(70, "STOPPED", 0, ["LIVE_SAMPLE_CADENCE_EXCEEDED"], true, ["preflight", "live"])
```

最小 production修復後同一 command為 `1 passed`；再加入 runtime precedence與 on-time cases後，
三個新案例為 `3 passed`。

## Trace mapping

- FR-001：late sample normal return回 `70 / STOPPED`；cadence reason、persistent denial、
  `automatic_clear_allowed=false`、child exit `0`、PGID quiescence與 sample phases均有 assertion。
- FR-002：hard runtime先於 sample deadline時，receipt與 denial reasons精確只有
  `HARD_RUNTIME_EXCEEDED`。
- FR-003：on-time normal return維持 `0 / OK`，無 reasons與 denial；既有 child non-zero、fast child、
  missing valid live sample與 hard runtime regressions全綠。
- FR-004：TimeoutExpired、absolute deadline、sampler overrun、sampling期間 child exit、first-write、
  RSS／swap、unknown／registered-unmetered write、PGID、receipt與 fog validation unit regressions全綠。

## Tests

- Focused new cases：`3 passed in 0.22s`。
- Deadline／sampler／PGID／receipt／runtime adjacent suite：`13 passed in 1.61s`。
- Affected suite：
  `tests/test_storage_safety.py tests/test_fog_storage_validation.py` →
  `53 passed, 16 subtests passed in 5.39s`。
- Full suite：`686 passed, 1 failed, 270 subtests passed in 152.04s`。
- Full suite唯一 failure為卡片預告且不在本次 diff的既有 ledger evidence gap：
  `ResearchComponentLedgerTest.test_verifier_accepts_generated_ledger`；精確 failed check為
  `evidence_exists`，缺 evidence的 ledger IDs為 `research:candidate_ranking`、
  `research:chip_flow`、`research:concept_membership`、`research:fundamental_revenue`、
  `research:industry_map`、`research:market_context`、`research:market_regime_history`、
  `research:overlap_first`、`research:trail10`、`runtime:industry_theme_context`。未修改或放寬該
  verifier，亦未把 full suite宣稱全綠。

## Protected 與 production fail-closed evidence

`<main-checkout>` dirty path集合仍精確為前代三檔，SHA-256未變：

- `scripts/build_weekend_universe_inventory.py`：
  `c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`
- `tests/test_weekend_universe_inventory_snapshot.py`：
  `ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`
- `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`：
  `f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`

八個 labels `com.new-top10.daily`、`retrain`、`reference`、`fog-research-worker`、
`pm-research-harness`、`external-review`、`external-review-preflight`、`baseline-harness` 均由
`launchctl print-disabled`確認為 `disabled`，且 `launchctl print`均為 `NOT_LOADED`。Storage policy
八個對應 job的 `launch_verified=false` 全部未變。

沒有執行 fog／representative workload／fresh cycle／retry；沒有讀寫前一鏈 sandbox、marker、
contract或 restart denial；沒有操作 launchd、外部服務、browser/provider、merge、push或deploy。

## Static checks 與 changed files

- `rg -n '\[DBG-' app tests scripts`：零命中。
- `git diff --check`：`PASS`。
- Changed-file allowlist：
  - `app/storage_safety.py`
  - `tests/test_storage_safety.py`
  - `docs/tasks/2026-08-03_TOP10-STORAGE-GUARD-DEADLINE-NORMAL-RETURN-01.md`
  - `docs/evidence/TOP10-STORAGE-GUARD-DEADLINE-NORMAL-RETURN-01/verification.md`

## Remaining risk／next step

- Full suite仍有上述既有 ledger evidence gap，因此證據狀態不是全域 `GO`；本卡只為
  `READY_FOR_REVIEW`。
- 主線必須建立新的獨立 Reviewer驗證 candidate；不得沿用前一 blocked Reviewer，也不得由本
  implementation自審。

# REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPAIR-2

- Repair base：`759dd7c76bf7ea3766fb67670c501be3a24ef2c4`
- Review evidence：`d4507353fdc21a28600524887cc30c4b067d5c13`
- Verified implementation SHA：`43c1ef87a870f63b7c49b27ab30e9f98d28334dd`
- Scope：只修 `F-02`
- Status：`DELIVERED_CANDIDATE / READY_FOR_REVIEW`

## Worktree preflight

- cwd：獨立 Codex worktree
- starting HEAD：`d7c5bda8ab513271faf34e47614e5155a1f40753`
- repair base ancestor：是
- starting state：clean、detached HEAD
- capability：worktree registered；Python tests prepared；CodeGraph
  `degraded:fallback_rg`
- 卡片 branch 另掛在 dispatch 指定的 `/private/tmp` worktree；本次正式 task
  worktree未切換或改動該 worktree
- merge／push／deploy／acceptance：皆未執行

## Phase 0 red baseline

命令：

```bash
.venv/bin/pytest -q \
  tests/test_regime_research_autonomy.py::test_public_matrix_rejects_content_addressed_forged_sealed_trade_dates
```

修復前結果：

```text
1 failed
E assert 'EXPECTED_FAMILY_VALID' == 'SEALED_TRADE_DATES_MISMATCH'
```

fixture 使用可信 runtime history、真實 split 與合法 `81/720` family，僅把
registration 的 `sealed_trade_dates` 改為 `["2099-01-01"]`，再由
`build_experiment_pre_registration()` 重算 experiment ID、sealed hashes 與
registry content address。`append_experiment_registry()` 成功，但 public gate 仍回
`EXPECTED_FAMILY_VALID`，精準重現 F-02。

## 修復

1. `statistical_lineage_authority()` 從可信 runtime history 與 immutable split
   重新計算：
   - `sealed_trade_dates`
   - `sealed_trade_date_hash`
   - `sealed_dataset_slice_hash`
2. `validate_statistical_family_registration()` 在 registry self-consistency 之前逐欄
   比對 runtime authority，任一不符立即 fail closed。
3. 穩定 reason codes：
   - `SEALED_TRADE_DATES_MISMATCH`
   - `SEALED_TRADE_DATE_HASH_MISMATCH`
   - `SEALED_DATASET_SLICE_HASH_MISMATCH`
4. public-path mutation tests 各自變更上述單一欄位，並重新建立
   experiment／registry content address，確認不依賴單一 fixture。

## Red → green 與 targeted

Phase 0、三欄 mutation、Repair-1 八欄 lineage guards：

```text
12 passed
```

完整 targeted：

```text
52 passed
```

## Verifier

命令：

```bash
.venv/bin/python scripts/verify_regime_research_autonomy.py \
  --base 759dd7c76bf7ea3766fb67670c501be3a24ef2c4 \
  --candidate 43c1ef87a870f63b7c49b27ab30e9f98d28334dd \
  --output /tmp/regime-repair2-verifier-implementation.json
```

結果：

```text
status=OK
check_count=28
failed_count=0
```

完整 delivery candidate SHA 的 verifier 由 Executor 在最後 evidence commit 後
再次執行，結果隨 Reviewer handoff receipt 交付，避免 commit SHA 自我引用。

## Full suite

```text
538 passed, 1 failed, 246 subtests passed
```

唯一 failure：

```text
tests/test_research_component_ledger.py::
ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
```

此為 Review 與 Repair-1 已記錄的 ignored-artifact provisioning debt；本卡未修改
ledger、其 verifier 或相關 artifact 路徑。

## 四 canary 與 forged attacks

完整 receipt：`canary-receipts.json`。

- A：`PASS`；3-family 由 `INVALID_CORRECTION_FAMILY` 拒絕。
- B：`PASS`；baseline／candidate 均為 `81/720`、corrected alpha
  `0.05/720`、`EXPECTED_FAMILY_VALID`。
- C：`PASS`；global `720`、missing `478`，
  `PARTITION_COVERAGE_INCOMPLETE`。
- D：`PASS`；`RISK_OFF|`、13 episodes、角色 counts `6/1/5/1`，
  actual units `2/14`、gap `12`，狀態
  `PRE_REGISTRATION → COARSE_SCREEN → INSUFFICIENT_EVIDENCE`。
- forged dataset：`PASS`；public gate 以 `DATASET_HASH_MISMATCH` 拒絕。
- forged sealed：`PASS`；content-addressed `["2099-01-01"]` registration
  由 `SEALED_TRADE_DATES_MISMATCH` 拒絕；receipt 同時保存 registration/runtime
  的 dates、date hash、dataset-slice hash。

## Production boundary 與 diff

- `models/latest_lgbm.pkl`：
  `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`
- `models/baseline_stats.json`：
  `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7`
- 與 Repair base 比較，`models/`、ranking、weight、promotion paths 無差異。
- 變更僅在本卡、F-02 runtime validator、canary/verifier、mutation tests 與本卡
  evidence allowlist。
- `git diff --check` 通過；無 `[DBG-*]` instrumentation。

## Handoff

- 原 Reviewer task：`019fa367-851b-7402-bec7-6b11b68249de`
- Reviewer 應以 handoff receipt 的完整 delivery candidate SHA 重跑 verifier、
  public sealed attack 與既有 canary。
- 本 evidence 不構成 acceptance。

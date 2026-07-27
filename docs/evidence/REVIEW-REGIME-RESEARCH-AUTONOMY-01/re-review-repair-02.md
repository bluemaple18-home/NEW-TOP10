# REGIME-RESEARCH-AUTONOMY-01 Repair-2 最終 Re-review

## 結論

- verdict: `NO_GO`
- terminal status: `BLOCKED / REVIEW_REPAIR_LIMIT`
- Repair-1: `9f59aab69a70305d6afb4951ac7b97f176350f69`
- Repair-1 re-review evidence: `4c249aba3dd052b6a693773bb4606e3f5b8302d3`
- reviewed Repair-2 candidate: `f656c18a6ec716d40c824d83174419abbeaf2530`
- review scope: `9f59aab69a70305d6afb4951ac7b97f176350f69...f656c18a6ec716d40c824d83174419abbeaf2530`
- candidate mutation: 無；本提交只新增本 final re-review evidence。
- prohibited actions: 未 merge、push、deploy、promotion。

`REG-R006-R1` 已關閉；`REG-R003-R1` 的 manager-generated global family 路徑與
pseudo-replication protection 已改善，但 public matrix CLI 仍接受可正式登錄的自選
local correction family，故 global family 可被繞過。依 Repair-2 卡片，本輪
`NO_GO` 後停止 repair chain，標記 `BLOCKED / REVIEW_REPAIR_LIMIT`。

## Preflight

- review worktree: `<repo-root>` 的獨立 review worktree
- branch: `codex/review-regime-research-autonomy-01`
- review HEAD before evidence: `4c249aba3dd052b6a693773bb4606e3f5b8302d3`
- worktree before evidence: clean
- model: Codex / GPT-5 family；執行環境未提供更精確 model build
- reasoning: 執行環境未提供可稽核 reasoning label
- fixed refs: 三個完整 SHA 均可解析；Repair-1 是 Repair-2 ancestor
- CodeGraph: candidate worktree 沒有 `.codegraph` index；未初始化或修改 candidate，
  改用固定 SHA 的 `git diff/show`、精準 source inspection 與 executable fixtures。

## Blocking finding

### REG-R003-R2 — P1 — public matrix 接受自選且可正式登錄的 local correction family

**位置**

- `scripts/run_backtest_strategy_matrix.py:54-60`
- `scripts/run_backtest_strategy_matrix.py:357-378`
- `scripts/run_backtest_strategy_matrix.py:381-405`
- `scripts/run_autonomous_research.py:727-773`

**事實**

1. `expected_statistical_family()` 讀取任意 `--pre-registration` JSON 後，只用
   `experiment_id == deterministic_experiment_id(payload)` 判定
   `registration_valid=true`。
2. Matrix 沒有取得或比對 research contract，也沒有確認 registration 的
   `registry_record_hash`、append-only registry membership、registered state 或 global
   family policy。
3. `multiple_testing_gate()` 驗證 expected family 的內部 hash 一致性；只有
   `expected_family_size > len(expected_ids)` 時才強制
   `correction_scope=global_parameter_universe`。當呼叫者宣告
   `family_size == tested_count` 時，自選 local family 可通過。
4. `validate_experiment_registration()` 與 `append_experiment_registry()` 本身也不把
   correction family IDs/size 綁到 contract parameter universe，因此完整欄位、自洽
   hash 的三組 local-family registration 可正式回 `REGISTERED`。

**獨立 public CLI adversarial fixture**

Fixture 使用：

- 六個互斥 exact-match episodes
- 每 episode 一筆獨立正報酬 trade
- 三個 scenarios：horizon `3,5,10`
- 每 scenario：
  - independent statistical units: `6`
  - sign-test `p=0.015625`
  - robust neighbors: `2`
  - pseudo replication: `false`
- forged registration：
  - `tested_combination_ids`: 三組實際 scenarios
  - `correction_family_combination_ids`: 同三組
  - `correction_family_size=3`
  - `correction_scope=local_profile`
  - `parameter_space_hash`: 使用真實 contract hash
  - sealed／split／metric／dataset 等正式 registration 必要欄位完整

正式 registration 檢查：

```text
validate_experiment_registration:
  ok=true
  reason_code=REGISTERED

append_experiment_registry:
  ok=true
  reason_code=REGISTERED
```

真正 subprocess matrix CLI：

```bash
<repo-root>/.venv/bin/python scripts/run_backtest_strategy_matrix.py \
  --rankings-dir <tmpdir>/rankings \
  --features <tmpdir>/features.parquet \
  --max-ranking-files 6 \
  --horizons 3,5,10 \
  --stop-loss-pcts none \
  --take-profit-pcts none \
  --max-group-exposures none \
  --require-exact-regime \
  --market-regime-history <tmpdir>/history.json \
  --base-regime BROAD_RISK_ON \
  --family-tags BIG_BULL,HIGH_CHOPPY \
  --allowed-episode-ids <six-immutable-episode-ids> \
  --pre-registration <tmpdir>/registered-local-family.json \
  --output <tmpdir>/matrix.json
```

結果：

```text
exit=0
family_validation_reason=EXPECTED_FAMILY_VALID
correction_family_size=3
corrected_alpha=0.016666666666666666
evidence_complete=true
ok=true
reason_code=ROBUST_CANDIDATE_AVAILABLE
eligible scenario count=3
```

相同三組 rows 若使用 contract-derived 720 global family：

```text
correction_family_size=720
corrected_alpha=0.00006944444444444444
evidence_complete=true
ok=false
reason_code=MULTIPLE_TESTING_OR_ROBUSTNESS_FAILED
```

因此自選 registration 會把本來不能通過 global correction 的三個 scenarios 全部放行。

**風險**

public matrix 是 Repair 卡要求的真實入口。任何能建立 registration artifact 的呼叫者都可
宣告較小 family、重算 deterministic ID，取得較寬鬆 alpha，讓未通過預註冊 720 global
family 的策略成為 formal candidate。這是 `REG-R003-R1` 原 P1 的實質繞過，不是單純
provenance 文案缺口。

**必要修正**

- Matrix 必須從 immutable contract/registry record 推導 expected global family，不可把
  registration 自報 IDs/size 當 authority。
- `--pre-registration` 必須驗證完整 registration、registry membership、record hash 與
  current registered experiment identity。
- Registration validator 必須比對：
  `parameter_space_hash`、完整 legal combination IDs、global family ID/size 與 partition
  policy；即使 `tested_count == claimed_family_size` 也不得接受 local scope。
- 依 Repair-2 卡片禁止 Repair-3；此 finding 僅記錄為
  `BLOCKED / REVIEW_REPAIR_LIMIT`。

## REG-R003-R1 最終重驗

| 子項 | 結果 | 獨立證據 |
|---|---|---|
| manager pre-registration expected/global family | `PASS` | 真正 closed manager 產生 81 tested IDs、720 global IDs；registration、baseline、candidate 的 family ID 相同。 |
| global Bonferroni denominator | `PASS` | manager path `corrected_alpha=0.05/720=0.00006944444444444444`。 |
| partition policy | `PARTIAL` | 720→profile 且 scope 改為 local 時回 `INVALID_PARTITION_CORRECTION_SCOPE`；但自報 family size=profile size 時可繞過 global scope。 |
| matrix/gate tested-ID mismatch | `PASS` | 改一個 expected tested ID 回 `TESTED_COMBINATION_FAMILY_MISMATCH / INSUFFICIENT_EVIDENCE`。 |
| duplicate trade pseudo-replication | `PASS` | public matrix 的 duplicate stock/date/interval fixture 回 `DUPLICATE_TRADE_IDENTITY`、`pseudo_replication_detected=true`、`INSUFFICIENT_EVIDENCE`。 |
| immutable registered-family authority | `FAIL` | 可正式 `REGISTERED` 的三組 local family 被 matrix 視為 `EXPECTED_FAMILY_VALID` 並產生三個 eligible IDs。 |

`REG-R003-R1`: `UNRESOLVED / P1`

## REG-R006-R1 最終重驗

| 子項 | 結果 | 獨立證據 |
|---|---|---|
| contract `declared_complete=false` | `PASS` | candidate payload 即使自報 complete、具 28 筆 passing rows，仍回 `PARAMETER_UNIVERSE_INCOMPLETE`。 |
| inventory blocked | `PASS` | contract inventory 不是 `COMPLETE` 或仍有 blocked dimensions 時無條件 locked。 |
| candidate payload 不得自證 | `PASS` | validator 不再信任 `universe_declared_complete` payload。 |
| tagged exact identity coverage | `PASS` | complete contract 下只提供七個 base-only IDs，回 `MISSING_REQUIRED_REGIMES`，列出 21 個 tagged exact identities。 |
| complete 28 exact identities | `PASS` | 只有 contract complete、無 blocked dimensions、28 identities 全部獨立通過時回 `UNIVERSAL_CANDIDATE_UNLOCKED`。 |

`REG-R006-R1`: `RESOLVED`

## 其他六項 no-regression

| Finding | 結果 | Evidence |
|---|---|---|
| REG-R001 | `PASS` | cross-regime holding-window fixture 仍 fail loud；replay boundary code 未改。 |
| REG-R002 | `PASS` | 真正 closed manager registry trace 為 `PRE_REGISTRATION → COARSE_SCREEN → NO_STRATEGY`；promotion=false。 |
| REG-R004 | `PASS` | episode date overlap/chronology fixture pass；split validator 未改。 |
| REG-R005 | `PASS` | sealed-date alias reuse、unknown/untraceable stitching source fixtures pass；lineage code 未改。 |
| REG-R007 | `PASS` | `eligible=false` selection/fallback/queue/execute regression pass。 |
| REG-R008 | `PASS` | fixed `--candidate f656...` verifier `26/26 OK`。 |

集中 regression command：

```text
7 passed, 26 deselected
```

涵蓋 cross holding window、closed manager trace、episode overlap、sealed alias、
unknown stitching、ineligible topic 與 consolidated verifier。

## Verification

### Repair-2 focused red→green tests

```bash
<repo-root>/.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py \
  -k 'public_matrix_blocks_pre_registration_family_mismatch or \
      public_matrix_rejects_duplicate_trade_pseudo_replication or \
      universal_gate_does_not_trust_candidate_completeness_claim or \
      universal_gate_requires_all_legal_tagged_exact_identities'
```

- `4 passed, 29 deselected`
- test gap: 沒有「完整、自洽、可正式 REGISTERED 的 local family」negative fixture；現有
  mismatch fixture 不會觸發本 finding。

### Targeted

```bash
<repo-root>/.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py
```

- `33 passed`

### Affected

```bash
<repo-root>/.venv/bin/python -m pytest -q \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_pm_research_harness_loop.py \
  tests/test_shadow_research_campaign.py \
  tests/test_feature_promotion_decision.py \
  tests/test_regime_research_autonomy.py
```

- `69 passed`

### Fixed candidate verifier

```bash
<repo-root>/.venv/bin/python scripts/verify_regime_research_autonomy.py \
  --base 7efda43641118f36b10261b4a04e0278bba941a2 \
  --candidate f656c18a6ec716d40c824d83174419abbeaf2530
```

- `status=OK`
- `26/26 passed`

### Full suite

```bash
<repo-root>/.venv/bin/python -m pytest -q
```

- `519 passed`
- `1 failed`
- `246 subtests passed`
- failure:
  `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`
- 同一 failure 已在 Repair-1 parent 獨立重現，屬既有 baseline debt。

### Scope / production / hygiene

- `git diff --check 9f59...f656...`: `PASS`
- changed production model/ranking/weight paths: 無
- `models/latest_lgbm.pkl`:
  `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`
- `models/baseline_stats.json`:
  `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7`
- candidate SHA after verification:
  `f656c18a6ec716d40c824d83174419abbeaf2530`

## Final verdict

`NO_GO`

Terminal status:
`BLOCKED / REVIEW_REPAIR_LIMIT`

Reviewed Repair-2 SHA:
`f656c18a6ec716d40c824d83174419abbeaf2530`

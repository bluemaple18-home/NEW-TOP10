# REPAIR-REGIME-RESEARCH-AUTONOMY-01-02 Repair-2 Evidence

## 結論

- delivery status: `DELIVERED_REPAIR_CANDIDATE`
- scope: 僅修復 `REG-R003-R1`、`REG-R006-R1`
- fixed parent Repair-1:
  `9f59aab69a70305d6afb4951ac7b97f176350f69`
- fixed re-review evidence:
  `4c249aba3dd052b6a693773bb4606e3f5b8302d3`
- Repair-2 candidate SHA: 由本文件所屬 candidate commit 與交付訊息回報
- prohibited actions: 未修改 production ranking／模型／權重，未 promotion、merge、push、deploy

## Preflight

- worktree: `<repo-root>` 獨立 Codex worktree
- starting HEAD:
  `c6f693856a160391caf143efd642d548b2a2f8f6`
- starting state: detached HEAD、clean
- parent relation: Repair-1 是 starting HEAD 的 ancestor
- re-review relation: 固定 evidence commit 不是 starting HEAD ancestor；目前歷史的
  `429e0d56f9c27eb3a0b777de1bf57e5fcf94d34f` 攜帶與固定 evidence commit
  完全相同的 evidence blob
  `e2486cf6bd679f74fe89c2e414373607669ee9a4`
- CodeGraph: 此 worktree 未初始化 index；依規範改用精準 source inspection，未建立或修改 index
- Python: 使用 shared checkout 的 `.venv`，Python `3.12.12`
- starting production hashes 與 Repair-1 相同，見下方 production hash gate

## Red evidence

先只新增四個 public-path adversarial tests，未修改實作：

```bash
<shared-checkout>/.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py \
  -k 'public_matrix_blocks_pre_registration_family_mismatch or public_matrix_rejects_duplicate_trade_pseudo_replication or universal_gate_does_not_trust_candidate_completeness_claim or universal_gate_requires_all_legal_tagged_exact_identities'
```

修前結果：

```text
4 failed, 29 deselected
```

四個失敗均為預期 fail-open：

1. candidate 自報 complete 可繞過 contract incomplete。
2. base-only required list 可漏掉合法 tagged exact identities。
3. matrix 執行集合與 registration 不一致仍回 `ok=true`。
4. 相同 trade 重複 20 次仍回 `ok=true`。

## 最小真實入口修復

### REG-R003-R1

- closed pre-registration 現在保存：
  - 實際 profile 的排序後 immutable `tested_combination_ids`
  - `tested_combination_ids_hash`
  - 完整 global correction family 的 720 個 combination IDs
  - `correction_family_id`、`correction_family_size`
  - `validation_profile_partition.v1` partition policy
- public manager 以 `--pre-registration` 將同一 immutable registration 傳給
  baseline/candidate matrix。
- matrix 驗證 content-addressed registration ID，逐項比對實際 combination IDs、
  tested hash、完整 family IDs/hash/size，以及 partition policy 的 global correction scope。
- Bonferroni denominator 固定使用 global family size `720`，不再以當次 `81` rows
  自組較小 family。
- sign test 以 immutable exact-regime episode 聚合為獨立統計單位。
- 缺 episode identity、重複 trade identity、跨 alias episode 的重疊 trade、
  統計單位證據缺失均 fail closed。
- family mismatch 或 pseudo-replication 回：
  `INSUFFICIENT_EVIDENCE / evidence_complete=false`。

### REG-R006-R1

- `universe_declared_complete` 改由 contract 推導；candidate payload 不再是信任來源。
- contract 只有在 `declared_complete=true`、`inventory_status=COMPLETE` 且沒有
  blocked dimensions 時才可能進入 universal gate。
- `full_cartesian_product` identity policy 由七個非 UNKNOWN base regimes 與兩個
  family tags 推導完整 28 個 exact identities。
- contract 的 configured required set 必須與 derived set 完全一致。
- 若使用非笛卡兒積，僅接受具 `legal_identity_rules` 與完整
  `legal_universal_regime_ids` 的 `explicit_legal_identity_set`。
- coverage/results 中實際研究過、但不在 contract required policy 的 identity
  會 fail closed；所有 28 個合法 tagged/base exact identities均納入 required coverage。

## Green evidence

相同四個 adversarial tests：

```text
4 passed, 29 deselected
```

完整 targeted：

```bash
<shared-checkout>/.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py
```

```text
33 passed
```

## Public CLI evidence

以獨立 synthetic parquet、ranking directories、八個 exact-regime episodes，
直接 subprocess 執行 public closed manager 與 matrix CLI；未 monkeypatch runner。

正常 closed manager：

- exit: `0`
- status: `OK`
- decision/final state: `NO_STRATEGY`
- promotion allowed: `false`
- tested profile combinations: `81`
- tested IDs hash:
  `sha256:37d429964703f9cbe73afeccdf23b6db4d480c836927b8e707b082982fba2cd1`
- global correction family size: `720`
- global correction family ID:
  `sha256:79899da01ead21b31ebd48571e2e3b6460f65946dad86bab7e5a1d546a0b4baa`
- baseline/candidate family ID: 完全相同
- corrected alpha: `0.00006944444444444444` (`0.05 / 720`)
- family validation: `EXPECTED_FAMILY_VALID`
- baseline/candidate development episode IDs: 完全相同
- registry trace:
  `PRE_REGISTRATION` →
  `REGISTERED→COARSE_SCREEN` →
  `COARSE_SCREEN→NO_STRATEGY`

Public adversarial matrix CLI：

| Case | Gate result | Decision |
|---|---|---|
| registration/matrix family mismatch | `INSUFFICIENT_EVIDENCE`, `TESTED_COMBINATION_FAMILY_MISMATCH`, `evidence_complete=false` | `INSUFFICIENT_EVIDENCE` |
| duplicate trade pseudo-replication | `INSUFFICIENT_EVIDENCE`, `pseudo_replication_detected=true`, `evidence_complete=false` | `INSUFFICIENT_EVIDENCE` |

## No-regression

```bash
<shared-checkout>/.venv/bin/python -m pytest -q \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_pm_research_harness_loop.py \
  tests/test_shadow_research_campaign.py \
  tests/test_feature_promotion_decision.py \
  tests/test_regime_research_autonomy.py
```

```text
69 passed
```

其餘六項維持：

- `REG-R001`: exact episode path tests pass；未修改 replay episode boundary 行為。
- `REG-R002`: public registry/state trace pass；缺 family/statistical evidence 仍 fail closed。
- `REG-R004`: split chronology/overlap validation 未修改，相關 tests pass。
- `REG-R005`: sealed lineage/reuse validation 未修改，相關 tests pass。
- `REG-R007`: ineligible topic selection/queue/execute tests pass。
- `REG-R008`: verifier 固定 base/candidate 與 production hash gate pass。

## Verifier

```bash
<shared-checkout>/.venv/bin/python scripts/verify_regime_research_autonomy.py \
  --base 7efda43641118f36b10261b4a04e0278bba941a2 \
  --candidate HEAD
```

Pre-commit candidate-tree result：

```text
status=OK
26/26 passed
```

Verifier 僅同步新的 expected-family synthetic contract，以及加入本 Repair-2
task/evidence allowlist；未放寬 production path。

## Full suite

```bash
<shared-checkout>/.venv/bin/python -m pytest -q
```

```text
519 passed
1 failed
246 subtests passed
```

唯一 failure：

```text
tests/test_research_component_ledger.py::
ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
```

固定 re-review evidence 已在 Repair-1 parent 獨立重現相同 failure；屬既有 baseline
debt，非本 Repair-2 regression。本次不越界修改 component ledger。

## Production hash gate

```text
models/latest_lgbm.pkl
ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d

models/baseline_stats.json
c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7
```

兩者與 Repair-1、verifier 既定值完全一致。

## Hygiene / acceptance boundary

- `git diff --check`: `PASS`
- `[DBG-...]` instrumentation: 無
- production model/ranking/weight path changes: 無
- external state changes: 無
- final acceptance: 留給原 Reviewer最終 re-review；Repair executor 不自行宣告 `GO`

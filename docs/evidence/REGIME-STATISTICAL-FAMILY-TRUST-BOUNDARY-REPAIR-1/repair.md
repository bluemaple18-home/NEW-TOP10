# REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPAIR-1

- Repair base：`47cd110f17ce0f008de86156820d83436d1072dd`
- Review evidence：`e4a801c773739cd7a2e121c245c692980e38d3b7`
- Verified implementation SHA：`56c45e4d7f641f6ba2b86aa683e8198dfa905c3b`
- Scope：只修 `F-01`
- Status：`DELIVERED_CANDIDATE`

## Worktree preflight

- cwd：獨立 Codex worktree
- starting HEAD：`bc3e73da0c40c4fccd1d11ce70ca6763c5d0a516`
- repair base ancestor：`47cd110f17ce0f008de86156820d83436d1072dd`
- starting state：clean、detached HEAD
- branch worktree：正式 repair branch 另掛在 dispatch 指定 worktree；本次未切換、未改動該 worktree
- merge／push／deploy／acceptance：皆未執行

## Phase 0 red baseline

命令：

```bash
cd <repo-root>
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py::test_public_matrix_rejects_content_addressed_forged_runtime_lineage
```

修復前結果：

```text
1 failed
assert expected_family["registration_valid"] is False
E assert True is False
```

測試使用真實 runtime history 與真實 development IDs，但 registration 重新
content-address 後偽造：

- `dataset_hash`
- `split_id`
- `split_artifact_hash`
- validation／embargo／sealed episode IDs
- `episode_split_ids_hash`

因此紅燈精準證明 public path 接受 forged lineage，而不是只觸發既有 development-ID gate。

## 修復

1. 新增 `statistical_lineage_authority()`，由可信 runtime history、trusted contract、
   exact regime 與 horizons 重建 deterministic episode split。
2. closed manager 與 public matrix 共用同一 authority，避免 manager／public 重算漂移。
3. public validator 逐欄比對：
   - dataset hash
   - split ID
   - split artifact hash
   - development／validation／embargo／sealed episode IDs
   - episode split IDs hash
4. mismatch 以穩定 reason code fail closed；另保留既有 registration self-consistency、
   registry membership 與 development CLI binding。

## Red → green 與 reason-code guard

Phase 0 同一測試修復後：

```text
1 passed
```

Targeted：

```text
48 passed
```

穩定 reason codes：

- `DATASET_HASH_MISMATCH`
- `SPLIT_ID_MISMATCH`
- `SPLIT_ARTIFACT_HASH_MISMATCH`
- `DEVELOPMENT_EPISODE_IDS_MISMATCH`
- `VALIDATION_EPISODE_IDS_MISMATCH`
- `EMBARGO_EPISODE_IDS_MISMATCH`
- `SEALED_EPISODE_IDS_MISMATCH`
- `EPISODE_SPLIT_HASH_MISMATCH`（registration 自身 episode hash 不自洽）

## Forged-lineage public CLI attack

完整 receipt：`canary-receipts.json` 的 `forged_lineage_public_attack`。

- status：`PASS`
- subprocess return code：`0`（維持既有 public CLI 行為）
- scenario count：`81`
- gate ok：`false`
- evidence complete：`false`
- reason code：`DATASET_HASH_MISMATCH`
- forged dataset hash：`sha256:forged-runtime-lineage`
- runtime dataset hash：
  `sha256:5ce301e63159ab39bfe312ce58196fe37904b6929b8a0ee5a9f38e6a6f4ee8a4`
- forged split ID：`sha256:forged-split`
- runtime split ID：
  `sha256:090a0073d1d21da80bd43cb15480bc00d6d97627f95aed266934905338494ca6`

## 四個 canary

命令：

```bash
cd <repo-root>
.venv/bin/python scripts/run_regime_statistical_family_canary.py \
  --output docs/evidence/REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPAIR-1/canary-receipts.json \
  --real-data-root <main-repo-root> \
  --max-real-ranking-files 3
```

結果：

- A：`PASS`；3-family 以 `INVALID_CORRECTION_FAMILY` 拒絕。
- B：`PASS`；baseline／candidate 均 return code 0、`81/720`、
  corrected alpha `0.05/720`、`EXPECTED_FAMILY_VALID`。
- C：`PASS`；union `242/720`、missing `478`，
  `PARTITION_COVERAGE_INCOMPLETE`。
- D：`PASS`；`RISK_OFF|`、13 episodes，角色 counts `6/1/5/1`，
  actual units `2/14`、gap `12`，狀態
  `PRE_REGISTRATION → COARSE_SCREEN → INSUFFICIENT_EVIDENCE`。

## Verifier、full suite 與 diff

Verifier：

```bash
cd <repo-root>
.venv/bin/python scripts/verify_regime_research_autonomy.py \
  --base 47cd110f17ce0f008de86156820d83436d1072dd \
  --candidate 56c45e4d7f641f6ba2b86aa683e8198dfa905c3b
```

結果：`28/28 OK`。

Full suite：

```text
534 passed, 1 failed, 246 subtests passed
```

唯一 failure：

```text
tests/test_research_component_ledger.py::
ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
```

此為 review evidence 已記錄的 ignored-artifact provisioning debt；本次未修改 ledger
測試或 implementation path。`git diff --check` 通過，未殘留 `[DBG-*]` instrumentation。

## Production boundary

- `models/latest_lgbm.pkl`：
  `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`
- `models/baseline_stats.json`：
  `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7`
- `git diff 47cd110... -- models/`：無差異。
- ranking、weight、promotion contract/code paths 對 repair base：無差異。
- available-data input features、industry map、兩份 ranking hashes與原 canary完全相同。
- production model、ranking、權重、promotion 未寫入。

## Handoff

- 原 Reviewer task：`019fa367-851b-7402-bec7-6b11b68249de`
- Reviewer 應以最終 delivery candidate SHA 重跑同一 verifier 與 forged-lineage receipt。
- 本 evidence 不構成 acceptance。

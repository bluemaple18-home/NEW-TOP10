# REGIME-RESEARCH-AUTONOMY-01 Repair-1 正式 Re-review

## 結論

- verdict: `NO_GO`
- parent candidate: `5cc87798804a48046cd9698b901e2b1bc8995871`
- original review evidence: `e6bd85790b8873e1b4149bab1bb5afbe2fdcede1`
- reviewed repair candidate: `9f59aab69a70305d6afb4951ac7b97f176350f69`
- review scope: `5cc87798804a48046cd9698b901e2b1bc8995871...9f59aab69a70305d6afb4951ac7b97f176350f69`
- candidate mutation: 無；本提交只新增本 re-review evidence。
- prohibited actions: 未 merge、push、deploy、promotion。

Repair-1 已補上大部分原 finding，但 `REG-R003` 與 `REG-R006` 仍存在可讓未完成證據被視為完整的 P1 fail-open，因此不可接受。

## Preflight

- review worktree: `<repo-root>` 的獨立 review worktree
- cwd: review worktree root
- branch: `codex/review-regime-research-autonomy-01`
- review HEAD before evidence: `e6bd85790b8873e1b4149bab1bb5afbe2fdcede1`
- worktree before evidence: clean
- model: Codex / GPT-5 family；執行環境未提供更精確 model build
- reasoning: 執行環境未提供可稽核的 reasoning label
- fixed refs: 三個完整 SHA 均可由 `git cat-file -e <sha>^{commit}` 解析
- CodeGraph: review worktree 沒有 `.codegraph` index；依規範改用固定 SHA 的 `git diff/show` 與精準 source inspection，未初始化或修改 candidate。

## Blocking findings

### REG-R003-R1 — P1 — correction family 未綁定 pre-registration，統計證據可在較小自選 family 內通過

**位置**

- `scripts/run_autonomous_research.py:1800-1811`
- `scripts/run_backtest_strategy_matrix.py:236-267`
- `scripts/run_backtest_strategy_matrix.py:299-327`
- `scripts/run_autonomous_research.py:657-728`

**證據**

1. Closed pre-registration 寫入的是完整 parameter universe hash（720 combinations）。
2. Matrix runner 只執行當前 validation profile 傳入的 scenario 子集，並在結果產生後，以當次 rows 的 `combination_id` 動態計算 `correction_family_id`。
3. `multiple_testing_gate()` 只驗證 rows 對「rows 自己算出的 family hash」一致，沒有接收或比對 registration 的 `parameter_space_hash`、預註冊 combination IDs 或 correction family。
4. 真正 public CLI fixture 的可稽核值：
   - pre-registration `parameter_space_hash`:
     `sha256:bcf2e751de5b0cef85eb2513eda044d3d063594c4a6197c1cea689f330b5fd0e`
   - baseline/candidate matrix `parameter_space_hash`:
     `sha256:537cd9f0f3199d0ff4852e5e055919e31df61dc8b77a5b6fa0ccb61b4b7e3743`
   - matrix `correction_family_id`:
     `sha256:37d429964703f9cbe73afeccdf23b6db4d480c836927b8e707b082982fba2cd1`
   - tested rows: `81`
   - 三者不一致，但 workflow 沒有因 preregistration mismatch 阻擋。
5. Adversarial fixture 只提供三個 scenario，將同一正報酬 trade 重複 20 次。單筆 sign-test `p=0.5` 被壓成 `p=0.000000953674`，並取得兩個動態 neighbor；gate 回：
   `ok=true / evidence_complete=true / ROBUST_CANDIDATE_AVAILABLE`。

**風險**

不同 profile／批次可各自在較小、事後形成的 correction family 內判定，而不是對預註冊研究 family 做 family-wise correction；重複或高度相依 trade 亦被當成獨立樣本。這會讓 candidate 在未滿足 AC-07 的情況下進入後續 funnel。

**必要修正**

- pre-registration 必須保存本次實際測試的 immutable combination IDs、correction family ID 與其 hash。
- matrix 與 gate 必須接收 expected family，逐項比對後才允許 `evidence_complete=true`。
- 若 registration 宣告的是完整 720 universe，profile 子集不可另立較小 family；或須在 registration 明確登記合法 partition 與全域 correction policy。
- 統計單位須以可辯護的獨立 episode／cluster 聚合，拒絕重複或重疊 trade 的 pseudo-replication。

### REG-R006-R1 — P1 — universal gate 信任 candidate 自報完整，且 required policy 漏掉 tagged exact regimes

**位置**

- `config/regime_research_contract.json:15-45`
- `scripts/run_autonomous_research.py:772-855`

**證據**

1. Contract 明確是：
   - `parameter_universe.declared_complete=false`
   - `inventory_status=PARTIAL_BLOCKED_SOURCE_UNKNOWN`
2. `validate_universal_candidate()` 只檢查 candidate payload 的
   `universe_declared_complete`；它不與 contract 的 `declared_complete` 或 inventory status 比對。
3. Adversarial payload 把 `universe_declared_complete` 自行設為 `true`，補齊 contract 列出的七個 base-only regime rows 後，validator 回：
   `unlocked=true / UNIVERSAL_CANDIDATE_UNLOCKED`，即使同一份 contract 仍宣告 universe 不完整。
4. Contract 同時宣告：
   - `identity_rule=exact_base_and_exact_family_tag_set`
   - family tags 為 `BIG_BULL`、`HIGH_CHOPPY`
   - 但 `required_universal_regime_ids` 只列七個空 tag identity。
5. 依目前 taxonomy 的七個非 UNKNOWN base 與兩個可重疊 tags，可形成 28 個 exact identities；required policy 只要求 7 個，漏掉 21 個 tagged identities，例如
   `BROAD_RISK_ON|BIG_BULL`、
   `BROAD_RISK_ON|HIGH_CHOPPY`、
   `BROAD_RISK_ON|BIG_BULL+HIGH_CHOPPY`。
   Public CLI 本次實際研究的 identity 正是
   `BROAD_RISK_ON|BIG_BULL+HIGH_CHOPPY`，但它不在 universal required list。

**風險**

不完整 parameter inventory 可由 payload 自行宣稱完成；且 tagged exact regime 即使尚未完成／失敗，也不影響 universal unlock。這直接違反 FR-07、FR-09、AC-09 與 REG-R006 的 fail-closed 要求。

**必要修正**

- `universe_declared_complete` 必須由 immutable contract／coverage artifact 推導，不得信任 candidate payload。
- Contract 為 `declared_complete=false` 或 inventory blocked 時，universal gate 必須無條件 locked。
- required regimes 必須與 exact identity policy 一致；若不是 taxonomy 全笛卡兒積，需有可稽核的合法 identity rules 與完整 required set，並涵蓋實際研究過的 tagged regimes。

## REG-R001..R008 獨立重驗

| Finding | 結果 | Re-review 證據 |
|---|---|---|
| REG-R001 | `PASS` | ranking、entry、每個 holding bar、exit 皆經同一 `episode_id` 驗證；跨 episode fixture fail loud。baseline/candidate public CLI matrix 使用完全相同 development episode IDs。 |
| REG-R002 | `PASS` | 以真正 subprocess public CLI 執行 closed manager，非 monkeypatch runner。Registry trace 為 `PRE_REGISTRATION`、`REGISTERED→COARSE_SCREEN`、`COARSE_SCREEN→BLOCKED`；缺統計證據時 outcome 為 `INSUFFICIENT_EVIDENCE`，promotion=false。 |
| REG-R003 | `FAIL` | 缺 `p_value` 可正確回 `INSUFFICIENT_EVIDENCE`；deterministic IDs、p-value、neighbor、drawdown 欄位已存在。但 correction family 未綁 registration，且 pseudo-replicated trades 可使 gate 通過，見 blocking finding。 |
| REG-R004 | `PASS` | 空 dates、episode 內重複、start/end 不符、跨 episode date overlap、chronology 倒置皆 fail loud；metadata 的 overlap 由驗證結果推導。 |
| REG-R005 | `PASS` | 相同 canonical sealed dates 即使 episode ID alias 不同仍回 `SEALED_DATASET_REUSE`；unknown component source 與不可追溯 source hash 均拒絕。 |
| REG-R006 | `FAIL` | missing fields／missing listed regimes／duplicate lineage／fixed hash／independent emergence／transition shadow fixtures皆鎖定；但 contract incomplete 與 tagged exact regimes 可被繞過，見 blocking finding。 |
| REG-R007 | `PASS` | `eligible=false` 於 generate、active bank、queue、fallback、selector、execute 均排除，只保留 monitor/coverage。 |
| REG-R008 | `PASS` | verifier 接受 `--candidate`，固定比較 `base...candidate`，由 candidate tree 讀 production hashes；`--candidate 9f59...` 得 `26/26 OK`。 |

## Public CLI closed-manager evidence

使用獨立 synthetic fixture，直接執行：

```bash
<repo-root>/.venv/bin/python scripts/run_autonomous_research.py \
  --date 2026-04-13 \
  --output <tmpdir>/run.json \
  --features <tmpdir>/features.parquet \
  --baseline-dir <tmpdir>/baseline \
  --candidate-dir <tmpdir>/candidate \
  --min-ranking-files 1 \
  --max-ranking-files 1 \
  --max-topics 1 \
  --execute \
  --execute-topic-count 1 \
  --closed-regime-research \
  --market-regime-history <tmpdir>/history.json \
  --research-contract config/regime_research_contract.json \
  --no-manager-update
```

結果：

- exit: `0`
- status: `OK`
- decision: `INSUFFICIENT_EVIDENCE`
- final state: `BLOCKED`
- scenario count: baseline `81` / candidate `81`
- baseline/candidate exact development episode IDs: identical
- candidate formal scenario IDs: empty
- promotion allowed: `false`
- registry events:
  1. `PRE_REGISTRATION`
  2. `STATE_TRANSITION REGISTERED→COARSE_SCREEN`
  3. `STATE_TRANSITION COARSE_SCREEN→BLOCKED`

這證明 R002 的 public CLI fail-closed trace 已實際接線；同一 trace 亦暴露 R003 的 registration/matrix family hash 不一致。

## Verification

### Candidate diff / scope

- `git diff --check 5cc87798804a48046cd9698b901e2b1bc8995871...9f59aab69a70305d6afb4951ac7b97f176350f69`: `PASS`
- repair allowlist inspection: 無 production ranking/model/promotion 修改
- candidate SHA 在所有測試後仍為：
  `9f59aab69a70305d6afb4951ac7b97f176350f69`

### Targeted

```bash
<repo-root>/.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py
```

- `29 passed`

### Affected

```bash
<repo-root>/.venv/bin/python -m pytest -q \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_pm_research_harness_loop.py \
  tests/test_shadow_research_campaign.py \
  tests/test_feature_promotion_decision.py \
  tests/test_regime_research_autonomy.py
```

- `65 passed`

### Fixed candidate verifier

```bash
<repo-root>/.venv/bin/python scripts/verify_regime_research_autonomy.py \
  --base 7efda43641118f36b10261b4a04e0278bba941a2 \
  --candidate 9f59aab69a70305d6afb4951ac7b97f176350f69
```

- `status=OK`
- `26/26 passed`

### Full suite

```bash
<repo-root>/.venv/bin/python -m pytest -q
```

- `515 passed`
- `1 failed`
- `246 subtests passed`
- failure:
  `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`
- parent candidate 的同一單測也獨立重跑為相同 failure，因此是既有 baseline debt，不是 Repair-1 regression；不改變上述兩項 P1 `NO_GO`。

## Final verdict

`NO_GO`

Reviewed repair SHA:
`9f59aab69a70305d6afb4951ac7b97f176350f69`

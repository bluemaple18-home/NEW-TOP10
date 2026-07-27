# REPAIR-REGIME-RESEARCH-AUTONOMY-01-01

## Delivery

- status: `DELIVERED_REPAIR_CANDIDATE`
- fixed_parent_candidate: `5cc87798804a48046cd9698b901e2b1bc8995871`
- fixed_review_evidence: `e6bd85790b8873e1b4149bab1bb5afbe2fdcede1`
- pre_repair_head: `0c2d0e441859ccf53c2210512c7671b8081616b6`
- repair_candidate_sha: 提交本文件的 commit；完整 SHA 於 commit 產生後由交付訊息回報
- production_promotion_ranking_weight_merge_push_deploy: `not_performed`

commit SHA 由 commit 內容推導，無法在同一 commit 內自我嵌入；本文件不使用假 SHA 或
amend 迴圈。candidate 形成後的 fixed-end verifier 結果由交付訊息補上。

## Preflight

- cwd/worktree: isolated Codex worktree
- branch: detached HEAD；正式 repair branch 指向相同 pre-repair HEAD 並掛在另一 worktree
- task model lock: `gpt-5.6-sol`
- task reasoning lock: `high`
- runtime model/reasoning introspection: 執行環境未提供可獨立查驗介面
- parent/review index lock: 兩個固定 SHA 均存在且為 pre-repair HEAD 祖先
- Python: `3.12.12`
- uv: `0.9.25`
- pytest: `9.1.1`
- CodeGraph: 此 worktree 未初始化；因 `.codegraph` 不在 allowlist，未建立新 index
- memory recall: 無相關既有紀錄

## Red Evidence

完整 red 記錄見 `docs/evidence/REPAIR-REGIME-RESEARCH-AUTONOMY-01-01/red.md`。

- command: `.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py`
- pre-repair result: `20 passed, 9 failed in 2.47s`
- post-repair result: `29 passed in 1.56s`

| Finding | Red → Green evidence |
|---|---|
| REG-R001 | 跨 episode holding window 原先未拒絕；現要求 ranking、entry、每個 holding bar、exit 共用同一 episode ID |
| REG-R002 | CLI 原先無 registration/split/trace；現產生 immutable split、pre-registration、persistent append-only registry 與 state transitions |
| REG-R003 | 真實 matrix row 原先缺 gate 欄位；現由 replay trades 計算 deterministic combination ID、exact-sign p-value、correction family、neighbor lineage/count、drawdown gate |
| REG-R004 | alias IDs 可共用交易日；現驗證非空、唯一、ISO、start/end、內部順序、跨 episode 互斥與 chronology |
| REG-R005 | sealed dates 改名與 unknown stitching 原先可通過；現以 canonical trade-date/dataset-slice hashes 防重，component source ID/hash 必須可追溯 |
| REG-R006 | missing fields/regimes 原先可 unlock；現 contract taxonomy 為 mandatory required-regime 來源，逐 regime 驗 fixed parameter、unique sealed lineage、independent emergence、transition forward shadow |
| REG-R007 | `eligible=false` topic 原先可被 selector 選取；現 generate output、active bank、queue、fallback、selector、execute 全部 fail closed，僅保留 monitor/coverage artifact |
| REG-R008 | verifier 原先綁目前 worktree；現接受 `--candidate`，固定 `base...candidate`，production hash 從 candidate tree 讀取且忽略 untracked/review-only worktree 狀態 |

## Closed Manager Trace

可重現命令：

```bash
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py \
  -k 'closed_manager_cli' \
  --basetemp <tmpdir>
```

- result: `1 passed, 28 deselected in 0.81s`
- experiment_id:
  `experiment:1aec1bded3e0a83de665864fde43d8986017f41540961d1cdbcb99de1cf96e49`
- split_id:
  `sha256:2720873e302bea667e4b154525a38b58dd7bf15bc8588f52d52db4331cadcf52`
- sealed_trade_date_hash:
  `sha256:fae0865556c4649bd7d1c670da2348f40d73c4fa52bc9ba723ffe47a0881cf80`
- sealed_dataset_slice_hash:
  `sha256:827ecc68157db48d0610e9ddc9ce59a4bb7b77b3a9205d453ab5578021549706`
- registry_record_hash:
  `sha256:32cb52f8118c35903d66df118409a2cf86293ce4635d98ff56ff57c7bd6df519`

Append-only event trace：

1. `PRE_REGISTRATION` / state `REGISTERED`
2. `REGISTERED → COARSE_SCREEN`
   - previous hash: registration record hash
   - evidence: immutable episode split artifact
3. `COARSE_SCREEN → BLOCKED`
   - previous hash: coarse transition event hash
   - evidence: closed execution evidence artifact

Candidate matrix fixture 刻意缺統計證據；CLI outcome 為
`INSUFFICIENT_EVIDENCE`、closed final state 為 `BLOCKED`，沒有誤寫成
`NO_STRATEGY`，也沒有跳到 validation/sealed/forward/policy candidate。
baseline 與 candidate command 使用同一組 development episode IDs。

## Verification

### Targeted

```bash
.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py
```

- result: `29 passed in 1.56s`

### Affected suites

```bash
.venv/bin/python -m pytest -q \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_pm_research_harness_loop.py \
  tests/test_shadow_research_campaign.py \
  tests/test_feature_promotion_decision.py \
  tests/test_regime_research_autonomy.py
```

- result: `65 passed in 1.48s`

### Fixed candidate verifier / worktree drift regression

```bash
.venv/bin/python scripts/verify_regime_research_autonomy.py \
  --base 7efda43641118f36b10261b4a04e0278bba941a2 \
  --candidate 5cc87798804a48046cd9698b901e2b1bc8995871 \
  --output <tmpdir>/repair-regime-verifier-fixed-candidate.json
```

- result: `26 checks, 0 failed`
- interpretation: current worktree 的 review、repair 與 untracked 狀態不會改變 fixed
  candidate verdict。

### Full suite

```bash
.venv/bin/python -m pytest -q
```

- result: `515 passed, 1 failed, 246 subtests passed, 4 warnings in 84.65s`
- sole failure:
  `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`
- isolated reproduction: `1 failed in 0.25s`
- interpretation: 原 Reviewer 已在 fixed base 與 parent candidate 重現同一 artifact
  provisioning failure；本 repair 未修改 ledger 或該 test，故不是 repair regression。

### Syntax / diff

- affected Python `py_compile`: `PASS`
- `git diff --check`: `PASS`
- debug marker scan (`[DBG-`): no matches

## Production Isolation

| Artifact | SHA-256 |
|---|---|
| `models/latest_lgbm.pkl` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` |
| `models/baseline_stats.json` | `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7` |

- hashes match verifier constants and fixed candidate
- diff under `models/`, formal data paths and `artifacts/backtest/`: none
- production model/ranking/weight/promotion changes: none

## Remaining Risk

- 本 repair 驗證治理鏈與 synthetic CLI trace，未執行真實長期 closed research dataset；
  不宣稱已找到策略或證明兩百萬參數來源。
- exact one-sided sign test 與 neighbor rule 已預註冊並由真實 trades 計算，但統計 power
  仍取決於每個 episode 的實際 trade count；不足時會回 `INSUFFICIENT_EVIDENCE`。
- contract 的 parameter inventory 仍為 `PARTIAL_BLOCKED_SOURCE_UNKNOWN`，因此 universal
  promotion 應維持 locked。
- full suite 保留一個已在 base 重現的 ledger provisioning failure。
- Repair candidate 必須回原 Reviewer re-review；本 executor 不自行接受、整合或上線。

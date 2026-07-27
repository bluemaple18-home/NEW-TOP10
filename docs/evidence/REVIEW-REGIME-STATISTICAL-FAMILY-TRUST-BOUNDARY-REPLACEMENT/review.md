# REVIEW-REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPLACEMENT

- Verdict：`GO`
- Chain：`REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01`
- Reviewer identity continuity：`019fa367-851b-7402-bec7-6b11b68249de`
- Replacement card：`REVIEW-REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPLACEMENT`
- Repair generation：`2`（未重置）
- Fixed base：`759dd7c76bf7ea3766fb67670c501be3a24ef2c4`
- Reviewed candidate：`b1e3dc191527c24a5d3f5d80b975a81ad8a46543`
- Ownership：independent replacement Reviewer
- Boundary：review-only；未 merge、push、deploy 或 acceptance

## Findings ledger continuity

- `F-01`：`resolved`。Repair-1 已把 dataset、split artifact／ID、四種 episode IDs
  與 episode hash 綁回可信 runtime authority；本輪 forged dataset attack 仍 fail
  closed。
- `F-02`：`resolved`。Repair-2 新增 runtime authority 對
  `sealed_trade_dates`、`sealed_trade_date_hash`、
  `sealed_dataset_slice_hash` 的逐欄比對。
- Unresolved blocking findings：`[]`
- 本輪未建立新的 finding，也未開啟 Repair generation 3。

## Preflight 與審查範圍

- 固定 base／candidate Git objects 存在，base 是 candidate 的祖先。
- replacement review card 位於 candidate 之上的 review-only commit；測試與 diff
  均固定使用 frontmatter 指定的 base／candidate。
- 起始 worktree clean、detached HEAD；無 `index.lock`。
- candidate 的 executable diff 只觸及：
  - `scripts/run_autonomous_research.py`
  - `scripts/run_regime_statistical_family_canary.py`
  - `scripts/verify_regime_research_autonomy.py`
  - `tests/test_regime_research_autonomy.py`
- 其餘 candidate 變更是 Repair-2 card／evidence allowlist。
- Reviewer 未修改 candidate；本 commit 只新增本 replacement evidence。

## 獨立 public-path adversarial review

Reviewer 另寫 temporary harness，不採用 Executor 的 stored PASS 作結論。每個 fixture
都重新計算 `experiment_id`、registry content address，經正式 public matrix CLI
執行 `81/720` scenarios：

| 攻擊欄位 | 自洽處理 | return code | gate ok | evidence complete | reason code | 結果 |
| --- | --- | ---: | --- | --- | --- | --- |
| `dataset_hash` | 同步重算 sealed slice hash | 0 | false | false | `DATASET_HASH_MISMATCH` | PASS |
| `sealed_trade_dates` | 同步重算 date hash 與 slice hash | 0 | false | false | `SEALED_TRADE_DATES_MISMATCH` | PASS |
| `sealed_trade_date_hash` | 單欄 mutation＋重算 content address | 0 | false | false | `SEALED_TRADE_DATE_HASH_MISMATCH` | PASS |
| `sealed_dataset_slice_hash` | 單欄 mutation＋重算 content address | 0 | false | false | `SEALED_DATASET_SLICE_HASH_MISMATCH` | PASS |

四組皆在 registration／registry 自身重新 content-address 後由 runtime lineage
comparison fail closed；不是只被舊 registry hash 擋下。

## Targeted、verifier 與 full suite

Targeted：

```text
52 passed in 1.36s
```

固定 SHA verifier：

```text
status=OK
check_count=28
failed_count=0
```

Full suite：

```text
538 passed, 1 failed, 246 subtests passed
```

唯一 failure：

```text
tests/test_research_component_ledger.py::
ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
```

Reviewer 額外列出 verifier failed checks，只有 `evidence_exists`。缺少的是此獨立
worktree 未 provision 的 ignored `artifacts/model_experiments/**`、`artifacts/**`、
`data/clean/features.parquet` 與 `data/reference/**` evidence；沒有 schema、runtime
contract、ranking mutator 或本 candidate 路徑失敗。這與原 Review、Repair-1／2
已記錄的 provisioning debt 相同，不是 Repair-2 regression。

## 四個 canary 與既有 attack

- Canary A：`PASS`；偽造 3-family 由 `INVALID_CORRECTION_FAMILY` 拒絕。
- Canary B：`PASS`；baseline／candidate 皆為 `81/720`，
  `corrected_alpha=0.00006944444444444444`，reason
  `EXPECTED_FAMILY_VALID`。
- Canary C：`PASS`；union `242/720`、missing `478`，狀態
  `PARTITION_COVERAGE_INCOMPLETE`。
- Canary D：`PASS`；exact regime `RISK_OFF|`、13 episodes，角色 counts
  `6/1/5/1`，actual independent units `2/14`、gap `12`，state trace
  `PRE_REGISTRATION → COARSE_SCREEN → INSUFFICIENT_EVIDENCE`。
- 既有 forged dataset：`PASS`；81 scenarios，由
  `DATASET_HASH_MISMATCH` 拒絕。
- 既有 forged sealed registration：`PASS`；81 scenarios，由
  `SEALED_TRADE_DATES_MISMATCH` 拒絕。

重跑使用的 contract、features、industry map、兩份 ranking 與 bounded subset hashes
均與 Repair-2 evidence 相同。`generated_as_of_history` artifact 含本次生成內容，其
artifact hash 與 Executor receipt 不同；bounded counts、semantic state trace 與正式
source-data hashes 不變，未將 timestamp-bearing generated artifact 誤報成
production hash。

## Production boundary 與 diff hygiene

固定 base、candidate 與 Reviewer worktree 的下列 SHA-256 完全相同：

- `models/latest_lgbm.pkl`：
  `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`
- `models/baseline_stats.json`：
  `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7`

`models/`、production ranking、weight、promotion paths 無 candidate diff。
`git diff --check <base>..<candidate>` 通過；Python diff 無 `[DBG-*]`、
`TODO` 或 `FIXME` 殘留。

## 判定軸

- Spec：`GO`。F-02 三欄與 Repair-1 dataset lineage 均由 public runtime authority
  重算並逐欄 fail closed；合法 `81/720`、`242/720` coverage 與 available-data
  canary 行為未變。
- Standards：`GO`。targeted、固定 SHA verifier、四 canary、兩組 stored attacks、
  四組 Reviewer 獨立 attacks、production hashes 與 diff hygiene 均符合 review
  契約。

## Remaining non-blocking risks

- validation profiles 仍只覆蓋 `242/720`，不得宣稱完整搜尋。
- available-data run 仍只有 `2/14` independent units，結論維持
  `INSUFFICIENT_EVIDENCE`。
- full-suite ignored-artifact provisioning debt 仍存在；它不是本 candidate 的
  production readiness 證據，也不由本 review 修復。

本 `GO` 僅是 independent Reviewer verdict，不構成 merge、deploy 或 acceptance。

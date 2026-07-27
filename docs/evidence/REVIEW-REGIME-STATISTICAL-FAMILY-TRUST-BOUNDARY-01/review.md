# REVIEW-REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01

- Verdict：`NO_GO`
- Base：`f656c18a6ec716d40c824d83174419abbeaf2530`
- Reviewed candidate：`47cd110f17ce0f008de86156820d83436d1072dd`
- Reviewer task：`019fa367-851b-7402-bec7-6b11b68249de`
- Review evidence commit：由本檔首次提交的 Git object 與主線 acceptance receipt 記錄。

## Blocking finding

### F-01：public matrix CLI 未把 registration 的完整資料與 split lineage 綁回 runtime 可信輸入

`validate_statistical_family_authority()` 會驗證 registration 自身的 content-address、
contract/global family/partition/tested IDs，也會比對 public CLI 傳入的 development IDs；
但沒有從 runtime history 與可信 split artifact 重新計算並比對：

- `dataset_hash`
- `split_id`
- `split_artifact_hash`
- `episode_split_ids_hash`
- validation／embargo／sealed episode IDs

因此攻擊者可建立內容自洽且 registry hash 正確、但 lineage 欄位偽造的 registration。
Reviewer 的 `/tmp` adversarial harness 實際得到：

```text
append_registry_ok=true
public_cli_returncode=0
public_cli_family_validation_reason=EXPECTED_FAMILY_VALID
validator.ok=true
validator.reason_code=STATISTICAL_FAMILY_AUTHORITY_VALID
registration_dataset_hash=sha256:forged-runtime-lineage
runtime_exact_match_dataset_hash=sha256:f328e8caacfeb4b93c23a1c2e4deb5c817d07292f2fe130a02b1dc4b0d3cca4f
```

這表示 public CLI 可接受與實際 runtime dataset hash 不同的 registration，違反卡片要求的
「exact regime／episode split／dataset lineage」信任邊界。

## 其餘驗證

- Targeted：`39 passed`
- Verifier：歷史 verifier base 與固定 review base 均為 `28/28`
- Full suite：`525 passed, 1 failed, 246 subtests passed`
  - 唯一 failure 是 review worktree 缺少 ignored research/data evidence，
    `evidence_exists` provisioning debt；candidate 未修改該 ledger/verifier。
- Canary A：content-addressed fake 3-family 被 `INVALID_CORRECTION_FAMILY` 拒絕。
- Canary B：baseline／candidate 各執行 `81/720`，corrected alpha 為 `0.05/720`。
- Canary C：union `242/720`、missing `478`，狀態為
  `PARTITION_COVERAGE_INCOMPLETE`。
- Canary D：`RISK_OFF|`、13 episodes、實際獨立 units `2/14`，
  `PRE_REGISTRATION → COARSE_SCREEN → INSUFFICIENT_EVIDENCE`。
- 其他 adversarial fixtures：
  - wrong contract/global hash/global IDs：fail closed
  - duplicate/missing/out-of-universe tested IDs：fail closed
  - registry hash alias：fail closed
  - forged complete／`NO_STRATEGY`：由實際 counts 重新計算後拒絕
- Production model/ranking/weight hashes 未變。

## 判定軸

- Spec：`NO_GO`。F-01 直接違反完整 lineage 綁定與 public-path fail-closed 契約。
- Standards：除 worktree ignored-artifact provisioning debt 外，targeted、verifier、
  canaries 與既定 trust-boundary 攻擊均通過；F-01 仍是發布阻塞。

## Repair-1 最小契約

1. Public CLI 必須接收可信 runtime history 與 immutable split artifact（或等價的 manager
   authority），自行重算完整 lineage，不得採信 caller registration 的 lineage 欄位。
2. 重算並逐欄比對 dataset、split artifact、split ID、四種 episode IDs 與
   `episode_split_ids_hash`；任一不符皆 fail closed 並回傳穩定 reason code。
3. 新增 public-path red→green test：重新 content-address 並登錄 forged lineage，
   修復前可通過、修復後必須拒絕。
4. 保留合法 `81/720`、partition coverage、available-data canary 行為及 production hashes。
5. 修復 candidate 交回同一 Reviewer task 複審。

## Repair-1 re-review

- Reviewed candidate：`759dd7c76bf7ea3766fb67670c501be3a24ef2c4`
- Verdict：`NO_GO`
- Finding：`F-02`

Repair-1 已正確綁定 dataset、split artifact/id、四角色 episode IDs 與 episode hash，
但未比對同一 runtime authority 產生的 `sealed_trade_dates`、
`sealed_trade_date_hash`、`sealed_dataset_slice_hash`。

同一 Reviewer 撰寫的 public-path adversarial harness 實跑結果：

```text
append_registry_ok=true
registration_sealed_trade_dates=["2099-01-01"]
runtime_sealed_trade_dates starts with 2025-05-26
public_cli_returncode=0
public_cli_family_validation_reason=EXPECTED_FAMILY_VALID
```

因此 content-address 正確但 sealed dates/slice lineage 偽造的 registration 仍可通過。
Repair-2 必須由 runtime authority 重算並逐欄比對上述三欄，任一不符 fail closed，
補 public-path red→green test，並保持 Repair-1 其餘驗證與 production hashes 不變。

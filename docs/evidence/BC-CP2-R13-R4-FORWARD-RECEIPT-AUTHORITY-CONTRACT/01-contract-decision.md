# BC-CP2 R13-R4 forward receipt authority contract decision

👉 [假設與目標確認] 目標是裁決 R13-R2 的 exact COMPLETE bundle 能否形成最小 committed-bundle authority；邊界是純唯讀、R13-only、不修改 historical admission、不新增 writer／registry；驗收是回答四個 fork 並把下一張 implementation card 鎖到無架構歧義。

## Verdict

`GO_MINIMAL_COMMITTED_BUNDLE_AUTHORITY_CONTRACT`

可行設計不是把 `ranking_provenance_admission.py` 擴成 forward registry，也不是修改
receipt bytes。它是一個可整檔移除的 R13-only 唯讀 reader：固定讀取單一 canonical
manifest，先證明四個 allowlisted files 的 working bytes 與 Git `HEAD` bytes 完全一致，
再重用 `ranking_provenance_receipt.verify_complete_bundle()` 驗證 bundle schema、hash、
scenario/date/run binding 與 ranking semantics。只有兩層都通過，reader 才回傳
`REGISTERED_FORWARD_BUNDLE_VERIFIED`。

此狀態只證明 **R13-R2 exact bundle 已成為 committed evidence**。它不是 ranking
admission、historical corpus admission、experiment admission 或任何 production authority。

## 已確認事實、契約明文與保守推論

### 已確認事實

- Fixed main HEAD 是 `d3a76693f4e91bd756f9285b8aa6b329fd5eefaa`；producer
  source commit `af9c32bdd63d86918fbd9d57c4f909beaa03f936` 是其 ancestor。
- `ranking_provenance_receipt.py:26-45,458-532` 固定 receipt／manifest exact-field
  schema；`FORWARD_CAPTURE` receipt 必須保持
  `admission_eligible=pending_registration`。
- `verify_complete_bundle()`（`:747-824`）會驗 canonical manifest/receipt bytes、plan、
  ranking/receipt/model hashes、receipt schema、scenario/date/run/producer identity、
  manifest-to-receipt binding 與 ranking semantics；它只讀 working tree，不驗證檔案已在
  Git `HEAD`。
- `ranking_provenance_admission.py:55-58,230-335,420-532` 是 50-record historical
  audit：authority 固定未設定，source 只有 availability／feasibility，legacy receipt shape
  與 forward receipt v1 不相容，任一 `PROVEN`／`ADMIT` 仍 fail closed。
- R13-R2 exact bundle 的四個必要 files 共 `2,815,580` bytes；summary
  `regime_shadow_ranking.json` 不在 manifest、receipt 或 verifier binding 中。

### 契約明文

- V1 card 的 registration boundary 要求完整 receipt bundle 先進 committed evidence，
  且歷史 50 筆 inventory 維持 NO-GO。
- Receipt 本身不授予 admission；R13-R3 也已裁決不能把 exact bytes、git commit 名稱或
  receipt identity 單獨冒充 authority。

### 保守工程推論

- Registration 可以是「固定 path 下 exact bytes + deterministic read-only verifier」，不必
  產生可變 registry、ledger 或 canonical writer。
- 因 receipt schema 永久要求 `pending_registration`，registration 後不得改寫該欄位；
  已註冊狀態必須是 reader 對 immutable receipt 的衍生判定，而非第二份可自行宣告的
  admission record。

## 四個必答 fork

### Fork 1 — Registration 與 admission artifact

Registration 只代表「下列四個 exact COMPLETE bundle files 已成為 Git `HEAD` 的
committed evidence，且 working bytes、committed bytes、bundle verifier 同時一致」。原
receipt 必須維持 `admission_eligible=pending_registration`，禁止重寫、rehash 或另造
`admission_eligible=true` receipt。

Registration **不產生另一個 committed admission decision artifact**。唯讀 reader 的
canonical JSON stdout／return value 是可重算 verification result，不是新 authority
writer 的輸出。任何未來 admission 都必須另卡、另 contract，且不得以此 result 自動
成立。

### Fork 2 — Forward 與 historical 完全分離

兩者必須完全分離：

- historical 50-record audit 繼續由
  `app/research/ranking_provenance_admission.py` 讀 availability／feasibility，保持
  `RECEIPT_AUTHORITY_CONFIGURED=False` 與全數 `REJECT`；下一卡不得修改此檔或其
  evidence。
- forward R13 authority 的最小 reader 固定為
  `app/research/r13_forward_receipt_authority.py`，只 import/reuse
  `app.research.ranking_provenance_receipt` 的 validators／bundle verifier；它沒有 writer、
  registry、discovery、glob 或 caller-supplied manifest path。
- 唯一 canonical manifest path 固定為：
  `artifacts/backtest/r13-r2-20260901-af9c32b/output/.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b/COMPLETE.manifest.json`。
- 唯一 public API 是
  `verify_registered_r13_bundle(*, project_root: Path = PROJECT_ROOT) -> dict[str, Any]`。
- 唯一 CLI 是
  `uv run python -m app.research.r13_forward_receipt_authority --verify`；不得接受 path、
  scenario、date、run、allowlist 或 output-path overrides。CLI 只把 canonical JSON result
  印到 stdout，成功回 0、拒絕回 1，不寫檔。

### Fork 3 — 解除 `pending_registration` 的條件與驗證者

Receipt 欄位本身永遠不被「解除」或改寫。只有當唯讀 reader 回傳
`REGISTERED_FORWARD_BUNDLE_VERIFIED` 時，下游在 **R13 committed-evidence 語境**可將
該 receipt 視為 registration 已完成；判定 predicate 是：

`receipt.admission_eligible == "pending_registration" AND authority.status == "REGISTERED_FORWARD_BUNDLE_VERIFIED"`。

驗證者是 repo-owned `r13_forward_receipt_authority.py`，Git `HEAD` 是 committed-byte
authority，既有 `verify_complete_bundle()` 是 bundle-integrity authority。reader 必須依序：

1. 以固定 allowlist 列出 canonical root 下 Git `HEAD` 的 tracked files；集合必須精確相等，
   不可少檔、加檔、第二個 manifest、第二個 run 或 summary。
2. 對每個 allowlisted path 以 `git show HEAD:<path>` 讀 committed bytes；path 不存在即
   `SOURCE_NOT_COMMITTED`，working bytes 不同即 `SOURCE_WORKTREE_DRIFT`。
3. 驗四個 committed bytes 的固定 size／SHA-256；任一 mismatch 即拒絕。
4. 重用 `verify_complete_bundle()`；所有 errors 必須為空。
5. 額外鎖定 manifest/receipt 為單一 entry，以及 exact
   `scenario=regime_shadow_research`、`ranking_date=2026-09-01`、
   `run_identity=r13-r2-20260901-af9c32b`、
   `batch_plan_id=sha256:7cb4ab0fc61758085f71a865de79e022633327894807322bea66a0535aef46aa`、
   `manifest_identity=sha256:a493c793a34a4598e0500de8dd3e80c8252033e5ab85d8f620b50d5fc63411cb`、
   `receipt_identity=sha256:c2487b57395f83ff3d266aab4fd0349784d6fa892701ba7235aa8ec3b7bf527f`、
   `capture_mode=FORWARD_CAPTURE` 與 receipt
   `admission_eligible=pending_registration`。
6. Duplicate/conflict 以兩層 fail closed：manifest validator 拒絕重複 date/artifact/receipt；
   canonical-root tracked-file set 拒絕第二個 run、第二個 manifest、同 identity 不同 path／
   bytes 或任何非 allowlisted file。不得「挑第一筆」或 latest fallback。

`git commit` 名稱、SHA 存在、單獨 manifest identity、單獨 receipt identity或單次
`verify_complete_bundle()` PASS 都不足以產生 registered state。

### Fork 4 — 單一 R13 bundle 可授權的下一 frontier

本 contract 只授權下一張 **R13-R5 committed-bundle authority implementation +
independent review/acceptance** 卡。即使 R13-R5 PASS，後續也只可回到 Mainline 重新裁決
是否存在新的、明示授權的 decision card；不會自動開始任何研究執行。

明確仍不授權：R14、Entry-Regime capacity/split、preregistration、historical corpus、
B0 Phase 2、B1、C1、production，也不授權 ranking root write、capture/replay、benchmark、
training、outcome/sealed read、merge、push 或 deploy。

## 下一張 implementation card 的固定契約

### Exact changed-files allowlist

只能新增：

1. `app/research/r13_forward_receipt_authority.py`
2. `tests/test_r13_forward_receipt_authority.py`
3. `artifacts/backtest/r13-r2-20260901-af9c32b/output/ranking_2026-09-01.csv`
4. `artifacts/backtest/r13-r2-20260901-af9c32b/output/.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b/COMPLETE.manifest.json`
5. `artifacts/backtest/r13-r2-20260901-af9c32b/output/.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b/receipts/ranking_2026-09-01.receipt.json`
6. `artifacts/backtest/r13-r2-20260901-af9c32b/output/.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b/model_snapshots/model-ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d.pkl`

因 `artifacts/*` 受 ignore，implementation 只能 explicit force-add 上述四個 bundle paths；
不得修改 `.gitignore`、不得 broad force-add directory。不得修改
`ranking_provenance_receipt.py`、`ranking_provenance_admission.py` 或既有 tests/evidence；
新 reader 只可 import/reuse 現有 verifier。

### Committed bundle allowlist

| Path | Bytes | SHA-256 |
| --- | ---: | --- |
| `.../COMPLETE.manifest.json` | 4,263 | `144777c9ea1aa8dcd944917820640a77866e3e4280549854549a98e3b90189c9` |
| `.../receipts/ranking_2026-09-01.receipt.json` | 8,074 | `dff85cb7028f3a664a5d96a0884f4f7e6d334c29ef2f8c23bd85e42cdcbc76ee` |
| `.../model_snapshots/model-ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d.pkl` | 2,798,697 | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` |
| `artifacts/backtest/r13-r2-20260901-af9c32b/output/ranking_2026-09-01.csv` | 4,546 | `d17cf9202b83f626023a8ee18aff423b1508540e6c54f294c7253021350046b2` |

表中的 `...` 只為顯示縮排；實作常數必須使用 exact changed-files allowlist 的完整
repo-relative paths。`regime_shadow_ranking.json`、input copies、FAILED/INVALID markers、
logs 與任何其他 files 一律不准 committed。

### Output schema 與 states

Reader return/stdout 必須是 deterministic exact-field object：

```json
{
  "schema_version": "ranking-provenance-forward-authority-verification.v1",
  "status": "REGISTERED_FORWARD_BUNDLE_VERIFIED",
  "authority_scope": "R13_R2_COMMITTED_EVIDENCE_ONLY",
  "manifest": {"path": "<fixed canonical path>", "sha256": "sha256:<hash>", "commit_status": "MATCHED"},
  "identity": {
    "scenario": "regime_shadow_research",
    "ranking_date": "2026-09-01",
    "run_identity": "r13-r2-20260901-af9c32b",
    "batch_plan_id": "sha256:<hash>",
    "manifest_identity": "sha256:<hash>",
    "receipt_identity": "sha256:<hash>"
  },
  "bundle_files": [{"path": "<repo-relative>", "sha256": "sha256:<hash>", "commit_status": "MATCHED"}],
  "downstream_authority": "NONE",
  "errors": []
}
```

只允許兩個 status：

- `REGISTERED_FORWARD_BUNDLE_VERIFIED`：所有 gate 同時通過。
- `REJECTED`：任一 gate 失敗；`errors` 為排序去重的 stable reason codes，
  `downstream_authority` 仍為 `NONE`，不得部分成功或降級。

`bundle_files` 必須按 path 排序。禁止 timestamp、mtime、absolute path、branch name、
latest/default/fallback、outcome/performance 欄位或 caller-controlled metadata。

### Positive／negative tests

正向測試至少包含：

1. 以 private core helper + 注入式 fixture contract 在 temporary Git repo 建立、commit 一個
   exact-layout 小型 valid `FORWARD_CAPTURE/pending_registration` bundle；驗證 committed、
   drift與 canonical JSON semantics。注入能力不得由 public API／CLI 暴露。
2. 實際四檔進 implementation commit 後，在該 commit 上驗證 canonical R13 bundle回
   registered、CLI 0、canonical JSON deterministic，四檔 working/HEAD bytes全為 MATCHED。

負向測試至少逐一覆蓋：

- 任一 bundle file missing、untracked、staged-but-not-HEAD、working-tree drift或 hash/size
  mismatch；
- extra tracked file、summary、第二個 run/manifest、duplicate scenario/date/artifact/receipt、
  identity collision/conflict；
- manifest/receipt noncanonical、schema extra/missing、rehashed swap、wrong plan/scenario/date/run、
  `REPLAY_GENERATED`、非 `pending_registration`、ranking semantic drift與 model hash drift；
- absolute/traversal/symlink path與 arbitrary CLI path override；
- historical regression：`ranking_provenance_admission.build_audit()` 仍是 50 records、300
  missing lineage fields、全數 `REJECT`、authority flag false。

Fixture 可透過 private helper 注入 temporary root／contract 測 committed semantics；public
API 與 CLI 必須保持 fixed R13 contract，不能暴露 path/identity/allowlist override。

## Data contract 與 fail-closed boundary

```text
data_contract:
  source_and_grain: one R13-R2 forward bundle / one scenario-date-run
  confirmed_schema_and_status_semantics: receipt.v1 + batch-manifest.v1; pending receipt plus verified authority result
  joins_and_cardinality: one manifest -> one entry -> one receipt -> one ranking -> one model snapshot
  aggregation_invariants: exactly four committed files; exactly one manifest entry; no aggregation
execution_boundary:
  database_pushdown: not applicable
  controlled_artifacts: four fixed Git-tracked files; read-only verifier stdout
degradation:
  unavailable_data: REJECTED with stable reason code
  provisional_thresholds: none
  model_limits: model bytes are identity evidence only; no inference
validation:
  fixture_or_unit: committed/drift/identity/duplicate/conflict matrix
  representative_real_data: exact R13-R2 four-file bundle after commit
  old_vs_new_reconciliation: historical admission output must remain byte/semantic equivalent
  business_invariants: no false registration; no historical/downstream promotion
warnings_and_exclusions: fail loud; no silently excluded tracked file
remaining_risk: registration proves committed bundle identity, not outcome quality or experimental admission
```

## Minimum sufficient、排除與 removal path

- **why_not_less**：只 commit bytes 或只跑 existing verifier 無法證明 working bytes 等於
  `HEAD`，也無法拒絕同 root extra tracked bundle；缺 repo-owned registered state 時仍只能
  `pending_registration`。
- **why_not_more**：修改 historical admission、建立通用 forward registry、寫 decision
  artifact、commit input corpus或加入 runtime discovery，皆超出單一 R13 bundle 的 measured
  gap。
- **do_not_absorb**：不新增 database、registry、ledger、canonical writer、runtime adapter、
  scheduler、generic multi-bundle authority或 production surface；不把 historical legacy receipt
  schema映射成 forward receipt v1。
- **rollback/removal path**：移除 `app/research/r13_forward_receipt_authority.py`、其單一 test
  file與四個 allowlisted tracked bundle files，即完整回到今日
  `pending_registration`／historical fail-closed狀態；沒有 migration、DB、config、workflow或
  runtime state要清理。

## Verification

- CodeGraph 在 source decision 前完成；命中 receipt `BundleRun`／bundle verifier與
  admission `_committed_json()`／`evaluate_admission()`／`verify_audit()` seams。
- 唯讀核對 fixed HEAD、producer ancestor、R13-R2 manifest/receipt schema、path、identity、
  sizes與 SHA-256；沒有 copy、capture、registration、admission、replay或 outcome read。
- 本卡未修改 code、tests、config、workflow、既有 evidence 或 bundle。

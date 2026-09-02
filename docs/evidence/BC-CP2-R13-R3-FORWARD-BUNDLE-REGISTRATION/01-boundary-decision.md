# BC-CP2 R13-R3 forward bundle registration boundary decision

👉 [假設與目標確認] 目標是判定 R13-R2 的既有 isolated `FORWARD_CAPTURE` bundle 能否經現有 committed-evidence seam 登錄；邊界是只讀、不複製 bundle、不改 admission 契約；驗收是給出唯一 fail-closed verdict 與最小後續 allowlist。

## Verdict

`NO_GO_NEW_SUBSYSTEM_REQUIRED`

R13-R2 的 output 本身是完整且可驗證的 forward bundle，但現有
`ranking_provenance_admission.py` 不是 forward-bundle registration seam：它沒有已
設定的 receipt authority、沒有讀取 `ranking-provenance-receipt.v1` COMPLETE bundle
的入口，也沒有可把該 receipt 轉為 admission lineage 的 schema mapping。因此不能
僅把 bytes commit 後宣稱已登錄，更不能把 R13 的 isolated session GO 升格為任何
下游 admission。

## Read-only evidence

- Fixed main HEAD：`d3a76693f4e91bd756f9285b8aa6b329fd5eefaa`。
- Audit source：`<isolated-r13-output>`，即任務卡指定的 R13-R2 output root；其中
  五個檔案總計 `2,817,408` bytes，且主 checkout 的 `HEAD` 沒有該 output bundle。
- `COMPLETE.manifest.json` 的 `status=COMPLETE`、`capture_mode=FORWARD_CAPTURE`，並以
  `manifest_identity=sha256:a493c793a34a4598e0500de8dd3e80c8252033e5ab85d8f620b50d5fc63411cb`
  固定單一 `regime_shadow_research / 2026-09-01 / r13-r2-20260901-af9c32b` entry。
- Receipt 是 canonical `ranking-provenance-receipt.v1`，其
  `admission_eligible=pending_registration` 與
  `receipt_identity=sha256:c2487b57395f83ff3d266aab4fd0349784d6fa892701ba7235aa8ec3b7bf527f`
  （注意：此 identity 是 receipt payload identity，不是 admission authority）。
- `verify_complete_bundle()` 讀 manifest 後重算 plan、驗 ranking/receipt bytes、receipt
  schema、receipt-to-manifest identity、model snapshot bytes、及 ranking semantics；見
  `app/research/ranking_provenance_receipt.py:747-824`。R13-R2 evidence 已記錄其結果為
  `{"errors": [], "status": "OK"}`。

## Bundle byte disposition

| 類別 | R13-R2 artifact | Bytes / SHA-256 | Registration disposition | 理由 |
| --- | --- | --- | --- | --- |
| COMPLETE manifest | `.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b/COMPLETE.manifest.json` | 4,263 / `144777c9ea1aa8dcd944917820640a77866e3e4280549854549a98e3b90189c9` | 必須 committed | 完整 bundle 的 root；entries 綁 ranking、receipt hash 與 receipt identity。 |
| Receipt | `.../receipts/ranking_2026-09-01.receipt.json` | 8,074 / `dff85cb7028f3a664a5d96a0884f4f7e6d334c29ef2f8c23bd85e42cdcbc76ee` | 必須 committed | 保存 capture mode、pending state、producer/model/config/universe/top-N/strict-input identity。 |
| Ranking | `ranking_2026-09-01.csv` | 4,546 / `d17cf9202b83f626023a8ee18aff423b1508540e6c54f294c7253021350046b2` | 必須 committed | manifest 與 receipt 都對其 bytes hash-bind，verifier 也直接讀取並檢查語意。 |
| Immutable model snapshot | `.../model_snapshots/model-ce6437….pkl` | 2,798,697 / `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` | 必須 committed | receipt identity 指向它，且 verifier 直接檢查其存在與 hash；不可以 `latest_lgbm.pkl` 取代。 |
| Strict inputs、config、universe、feature calendar、producer dependencies | 不屬 output bundle 的 input copies / source files | 不適用於 output total | 僅 hash-bound | manifest before/after input hashes與 receipt 欄位固定其 repo-relative path/hash；現有 bundle verifier不讀 input copies。任何新 authority 必須明定是否要升格其中某一類 bytes，不能默認回填。 |
| `regime_shadow_ranking.json` | summary output | 1,828 / `ea8e61bd2bd89c6574b829ecfe143981102844ae30c8ea95313e105857104769` | 必須排除 | 不在 COMPLETE manifest entries，亦不被 receipt 或 bundle verifier用作 lineage。 |

最小可登錄 bundle 是前四列，合計 **2,815,580 bytes**；連同被排除的 summary，
read-only output total 是 **2,817,408 bytes**。本判定沒有複製或登錄任何 bytes。

## Why the existing admission seam cannot register it

1. `app/research/ranking_provenance_admission.py:55-58` 把
   `RECEIPT_AUTHORITY_CONFIGURED = False`、authority path 與 schema 都設為空。其
   `validate_audit()` 在 `:490-511` 對任一 `PROVEN` field 與任何 `ADMITTED` status
   都 fail closed 為 `ADMISSION_AUTHORITY_NOT_CONFIGURED`。
2. `evaluate_admission()` 只從兩個既有 committed JSON sources 讀 availability/
   feasibility（`:230-248`；`build_audit()` 的 `_committed_json` calls 在 `:311-335`），
   沒有 manifest/receipt bundle reader 或 forward registration path。`_committed_json()`
   更要求 `HEAD:<path>` bytes 與 working bytes 精確相同（`:87-122`）；R13 output 目前
   位於 ignored isolated root，不能被視為 committed evidence。
3. admission 的 `_receipt_schema_errors()` 只接受 legacy 12-key shape，包括
   `contemporaneous_at_generation`、`immutable_committed_receipt`與`receipt_commit`
   （`:205-227`）。R13 receipt 是 16-key `ranking-provenance-receipt.v1` shape，反而有
   `capture_mode`、`admission_eligible`、`batch_plan_id`、`feature_calendar`與
   `strict_inputs`；二者沒有 direct schema compatibility。
4. 即使提供符合 legacy shape 的 synthetic receipt，`evaluate_admission()` 在 `:256-264`
   仍標為 `UNSUPPORTED_OR_UNREGISTERED_RECEIPT_AUTHORITY`；對應測試明確鎖定
   `BLOCKED_EVIDENCE_CONFLICT`（`tests/test_ranking_provenance_admission.py:77-104`）。
   因此把 R13 receipt 硬塞入 availability 並不是既有 seam 的合法使用方式。

## Binding and non-promotion boundary

manifest entry 同時固定 ranking path/hash、receipt path/hash 與 receipt identity；receipt
再固定 run/scenario/date、producer source commit/dependencies、immutable model snapshot、
config/universe/feature-calendar、top-N policy 與 strict-input hashes。`BundleRun.complete()`
建立這些 manifest entries（`app/research/ranking_provenance_receipt.py:618-688`），而
`verify_complete_bundle()` 逐一交叉驗證（`:747-824`）。這足以維持 **R13-R2 bundle
identity**，但 receipt 已明示 `pending_registration`，並不授權 admission。

所以本 verdict 不解除 historical 50-record non-admission，不開 R14、Entry-Regime
capacity、preregistration、B0 Phase 2、B1、C1 或 production。

## Minimum next card

此刻沒有可安全派發的「直接 registration implementation card」。先需要一張新的
authority-contract decision card，名稱建議：
`DECIDE-NEW-TOP10-BC-CP2-R13-R4-FORWARD-RECEIPT-AUTHORITY-CONTRACT`。

其精確 allowlist 僅限：

- `docs/tasks/2026-09-02_DECIDE-NEW-TOP10-BC-CP2-R13-R4-FORWARD-RECEIPT-AUTHORITY-CONTRACT.md`
- `docs/evidence/BC-CP2-R13-R4-FORWARD-RECEIPT-AUTHORITY-CONTRACT/01-contract-decision.md`
- 唯讀檢查 `app/research/ranking_provenance_admission.py`、
  `app/research/ranking_provenance_receipt.py` 與其對應 tests。

該卡必須先決定：是否將 committed bundle directory 視為 evidence source、其固定
repo-relative path/schema、如何把 receipt 轉為六個 admission lineage fields、以及如何
保持 R13 only。只有它結論為 GO，才可另開 implementation card；該 implementation
card 才能明列 code/tests、四個必要 committed bytes與新的 verification evidence。不得
修改 availability/feasibility historical sources，不得加入 registry/database/canonical writer，
不得重跑或複製 R13 bundle作為「驗證替代品」。

## Scope rationale and rollback

- **why_not_less**：只 commit manifest/receipt 不會改變 authority flag、讀取路徑或
  schema mismatch，任何 admission claim 都仍 fail closed。
- **why_not_more**：R13 的問題是 authority contract 缺口，不是 capture、model、ranking
  或 capacity 缺口；擴至 R14 或任何研究結果會越過尚未建立的邊界。
- **do_not_absorb**：不新增 registry、database、authority ledger、canonical writer、runtime
  adapter、production surface，也不把 historical evidence schema 擴成 forward authority。
- **rollback/removal path**：在 R13-R4 前沒有新行為可回滾。本 decision evidence 可單檔
  移除；若未來明確核准 authority implementation，必須使其只接受固定 bundle directory、
  預設 REJECT，並可透過移除該 reader/configuration 回復今天的
  `RECEIPT_AUTHORITY_CONFIGURED = False` fail-closed 狀態。

## Verification

- CodeGraph source decision completed before source inspection。
- Audit source bytes、sizes、hashes以 read-only `find`、`stat`、`shasum`核對。
- 主 checkout 的 bundle path 受 `.gitignore` 規則 `artifacts/*` 忽略，且 `HEAD` 未列出
  R13 output bytes；既有 R13 session evidence 是唯一已追蹤 reference。
- `git diff --check` passed after this file was added.

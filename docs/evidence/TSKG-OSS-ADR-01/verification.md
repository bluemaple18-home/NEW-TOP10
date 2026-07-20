---
card_id: TSKG-OSS-ADR-01
status: PROPOSED_CANDIDATE
verified_on: 2026-07-20
verification_kind: strict_architecture_decision
source_sha: 59917dd87dda448e77f5fc50ccfb3c1d05775aca
card_commit: ea5655efc5bf171f3584073ac04046699d0cc56e
---

# TSKG-OSS-ADR-01 verification

## 1. Preflight receipt

```text
worktree_path: <local-only-worktree verified in preflight>
git_dir: <repo-gitdir>/worktrees/<worktree-id>
independent_worktree: PASS
head: ea5655efc5bf171f3584073ac04046699d0cc56e
card_commit: ea5655efc5bf171f3584073ac04046699d0cc56e
source_sha: 59917dd87dda448e77f5fc50ccfb3c1d05775aca
head_parent: 59917dd87dda448e77f5fc50ccfb3c1d05775aca
source_to_card_ancestor: PASS
card_to_head_ancestor: PASS
clean_before_edits: PASS
git_metadata_writable: PASS by host-level permission probe
index_lock: absent
unrelated_dirty_paths: []
```

Sandbox 內的 `test -w <git-dir>` 只反映 restricted sandbox；host-level 唯讀 permission probe 對 git-dir existence、writability 與 no index lock 回傳 exit `0`，因此沒有把 sandbox 限制誤判為 lineage blocker。

## 2. Fixed-input completeness

已完整讀取任務卡列出的 11 份 fixed inputs；本卡未加入網路研究、金融 endpoint、外部 code、安裝或 runtime 執行。Substantive claims 只回指下列 fixed inputs：

- `docs/specs/TSKG_v1.1.md`
- `docs/handoff/handoff_20260720_tide_tskg_concepts.md`
- `docs/tasks/2026-07-20_UI-MFR-00_market_flow_radar_backlog.md`
- `docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md`
- `docs/research/TSKG-OSS-01_existing_asset_reuse_audit.md`
- `docs/evidence/TSKG-OSS-01/verification.md`
- `docs/research/TSKG-OSS-02_external_open_source_reference_scout.md`
- `docs/evidence/TSKG-OSS-02/verification.md`
- `docs/evidence/REVIEW-TSKG-OSS-01-02/review.md`
- `docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md`
- `docs/evidence/REVIEW-TSKG-OSS-ACCEPT-02/review.md`

## 3. Claim coverage ledger

| Claim ID | ADR claim | Fixed-input locator |
|---|---|---|
| C-01 | 未核准 source 必須 fail closed | TSKG v1.1 §3 AC-10、SRS-GOV-01/02、§11 |
| C-02 | observation 不是 RelationshipClaim／strategy／prediction | Tide handoff「Constraints & Preferences」、§1–3 |
| C-03 | FinMind caller 存在但無 dedicated verifier／source approval | OSS-01 §1、§3、§5–7；OSS-01 verification §2–5 |
| C-04 | direct T86 parser/status/verifier 存在，但粒度為市場總量 | OSS-01 §1、§3–6 |
| C-05 | 免費 T86 automation／rate／retention／redistribution 未批准 | MFO-SRC-01 §1、§5–8 |
| C-06 | TWSEMCPServer directness 只支持 reference，不支持 endpoint approval | OSS-02 §3.6；REVIEW-TSKG-OSS-01-02「Spec Axis」 |
| C-07 | FinMind code license 與 data/service-use 必須分層 | OSS-02 §3.1；REVIEW-TSKG-OSS-01-02「Spec Axis」 |
| C-08 | Theme observation 受 membership snapshot／aggregation blocker | Tide handoff §2、「建議後續切片」；UI-MFR-00「Blocking Edges」 |
| C-09 | source-neutral offline slice 不需等待 live source approval | TSKG v1.1 §3 BR-06、§14；Tide handoff「建議後續切片」 |
| C-10 | Top10／LLM 只能取得 explainable context，不得取得 score/signal/prediction | TSKG v1.1 AC-11、SRS-INT-01；Tide handoff §3 |
| C-11 | UI radar 仍是 BACKLOG／NOT AUTHORIZED | UI-MFR-00「Status」、「Current Frontier」、「Reactivate Condition」 |
| C-12 | acceptance cleanup/review 不等於 underlying source approval | REVIEW-TSKG-OSS-ACCEPT-01「Remaining risks」；ACCEPT-02「Remaining risks」 |

Claim coverage gate 要求 `C-01..C-12` 全部存在、沒有未映射或待補 locator，且 ADR 每一 substantive section 都有 fixed-input locator。

## 4. Decision consistency

| Gate | Required | Observed |
|---|---|---|
| Primary decision | exactly one `Primary decision:` | PASS：1 |
| Options | four options compared | PASS：4 |
| Matrix statuses | every asset exactly one allowed status | PASS：16 assets；每列 1 status；asset name unique |
| Next card | exactly one `Next implementation card:` | PASS：1；未建立 next-card file |
| Source blocker | live source layers remain blocked | PASS：adapter/live raw/source mapping/production integration 均 blocked |
| Top10/LLM boundary | prohibited strategy fields explicit | PASS：只允許 observation/date/freshness/provenance/warnings |

## 5. Scope and blocked boundaries

- Expected changed files：exactly the task card、ADR、this verification evidence。
- No code/test/fixture/config/requirements/runtime/API/UI/spec/contract/SourcePolicy changes。
- No ingestion approval；no next implementation card created。
- MOPS／TWSE／FinMind source approval、endpoint、rate、retention、redistribution、late correction remain blocked。
- ThemeFlow aggregation、graph diffusion、UI radar、Top10 ranking/model integration remain deferred。

## 6. Verification commands and exit codes

Post-edit commands與結果如下。第一輪 combined document gate 的 matrix 檢查器以空白而非 Markdown `|` 分欄，把多個 `Repo ...` asset 誤判為 duplicate，因此 combined exit `1`；改用 `awk -F'|'` 後，16 個 asset name 唯一且每列恰有一個 allowed status，exit `0`。ADR 本體沒有因此產生或掩蓋狀態衝突。

Final candidate SHA 不能在自身 commit 內自我引用，故由 external final receipt 綁定，沿用 `REVIEW-TSKG-OSS-ACCEPT-02` 已接受的 lineage pattern。

| Gate | Exit | Result |
|---|---:|---|
| claim coverage | 0 | PASS：C-01..C-12 共 12 列；11 份 fixed-input paths 全在 ADR 被引用 |
| initial combined document gate | 1 | EXPECTED REPAIR：matrix validator 的 Markdown 欄位解析錯誤；其餘子 gate 為 0 |
| corrected adoption matrix consistency | 0 | PASS：16 assets、unique names、每列 exactly one allowed status |
| single primary decision / four options | 0 | PASS：primary marker=1、option rows=4 |
| single next implementation card | 0 | PASS：marker=1、next-card file absent |
| exact allowlist | 0 | PASS：只列 task card、ADR、verification evidence |
| host-path raw scan | 1 | PASS：無 match；raw `rg` 的 no-match exit 為 1 |
| `git diff --check` before staging | 0 | PASS |
| staged exact allowlist / `git diff --cached --check` | 0 | PASS：staged paths exact 3、cached whitespace clean、unstaged changes absent、index lock absent；final rerun 由 external receipt 綁定 |

## 7. Acceptance status

```text
status: PARTIAL — local document gates pass; independent review remains pending
evidence: preflight、claim ledger、decision/matrix/next-card/scope/path/diff gates
acceptance_mapping: sufficient for PROPOSED_CANDIDATE only
missing_evidence: external final-SHA receipt、independent review、mainline acceptance
remaining_risk: independent review and mainline acceptance not yet performed
next_step: stage exact allowlist, run final cached diff gate, create one PROPOSED_CANDIDATE commit, bind SHA in external final receipt
```

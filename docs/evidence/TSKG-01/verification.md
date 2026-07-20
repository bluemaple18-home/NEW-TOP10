---
id: TSKG-01-verification
status: DELIVERED_CANDIDATE
type: verification-evidence
card: TSKG-01
verified_at: 2026-07-17
repair_card: REPAIR-TSKG-01
---

# TSKG-01 Verification Record

## 1. Verification scope

本卡與 Repair 均是 docs-only contract 交付，未實作也未執行 crawler、database、API、scheduler、benchmark 或任何外部網站／服務。驗證範圍是：規格的可判定 invariants、golden/negative contract cases、需求追溯、slice blockers、allowlist、whitespace 與 commit-range 完整性。`CONTRACT_PASS` 只表示文字契約可作唯一判定；一律搭配 `RUNTIME_NOT_RUN`，不得解讀為 runtime behavior PASS。

## 2. Preflight evidence

| Check | Command / evidence | Result |
|---|---|---|
| 平台獨立 worktree | `pwd`, `git rev-parse --show-toplevel`, `git rev-parse --git-dir`；cwd 為平台 Repair worktree，git dir 位於主 repo `worktrees/` metadata | PASS |
| Repair card commit | `git rev-parse HEAD`、log inspection | PASS；Repair 開始時 HEAD 為 `fecc175`，其 parent 是 base candidate `fad3955`；review commit 僅唯讀 |
| Repair 初始 workspace clean | `git status --porcelain=v1` | PASS；開始修改前輸出為空 |
| 無 index.lock | `test ! -e "$(git rev-parse --git-dir)/index.lock"` | PASS |
| 卡片實體與規則 | 原 candidate 完整閱讀 `AGENTS.md`、任務卡與所需規則；Repair 線另完整閱讀 AGENTS、Repair／原卡、candidate spec/evidence 與 review evidence | PASS as docs preflight |
| 外部存取禁令 | 本任務所有 command 僅讀寫 repo／本機規則與 git metadata，未呼叫網站、外部服務或套件安裝 | PASS |

平台 delegation envelope 提供來源 task ID，但目前可用 filesystem/tool 沒有提供本執行 task 的 thread ID 或 sidebar 狀態查詢；因此本紀錄不宣稱獨立驗證 Gate 2 的 UI 可見性。此項不影響 docs candidate 產出，須由主線 integration/review gate 留存平台證據。

## 3. Repair finding contract verification

| Finding | Deterministic invariant | Golden / negative contract case | Disposition |
|---|---|---|---|
| F-01 single supply/customer fact | Spec §6.4 固定 `SUPPLIES_TO(supplier,customer)`；`SUPPLIED_BY/HAS_CUSTOMER/CUSTOMER_OF` 只能 normalization/query labels；API key `(canonical_fact_id,claim_id,as_of,known_at)` 去重 | AC-03/TDS-RELATIONSHIP：四種同義方向輸入→一個 fact/compatible claim；方向不足、canonical legacy predicate promotion、duplicate API item 均 reject | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| F-02 conflict lineage | Spec §6.1–6.2 分離 `canonical_fact_id`、`assertion_id/assertion_version_id`、`claim_id`；ConflictSet/ResolutionDecision 必填 member、evidence、actor/time/policy 與 selected/rejected/superseded lineage | `TDS-CONFLICT-01`：OPEN→SELECT→歷史 `known_at` round-trip；跨 fact member、缺 decision metadata、集合重疊、覆寫舊 decision 均 reject | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| F-03 temporal wire | Spec §6.3 endpoint discriminator `KNOWN/UNKNOWN/UNBOUNDED`；business current 與 system current 唯一表示；system 禁 UNKNOWN；empty/illegal reject | TDS-TIME 六列 parser→authority→projection→API matrix；reversed/equal-exclusive、missing fields、UNKNOWN system、UNBOUNDED+timestamp 均 reject | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| F-04 verification integrity | 本表逐 finding 引用 invariant/case，所有 runtime 未執行項均帶 `RUNTIME_NOT_RUN`；ID count 只留 internal coverage | 本文件不得以章節存在、31/31 或 14/14 單獨推論核心正確性 | `CONTRACT_PASS`（本 evidence 靜態自檢；仍待 reviewer re-review） |
| F-05 confidence API | Spec §9.2 移除 public `min_confidence`；truth filter 只依 state/policy/evidence/review；provenance confidence 不跨 extractor 比較 | TDS-API-CONFIDENCE：deterministic/human null、mixed extractor、reviewed low confidence 不得被 truth score 錯誤排除；conflict 不得被 confidence 隱藏 | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| F-06 baseline provenance | Trace §1.1 固定 source task/turn/item、content prefix、canonicalization；14 BL rows各連 original section label；internal/independent coverage 分離 | 正確 digest 尚未依指定 NFC/LF contract capture；不得以不同 canonicalization digest 代替 | `PARTIAL/BLOCKED`：`baseline_sha256=PENDING_REPRODUCIBLE_CAPTURE`；依三次停損不得第四試 |
| F-07 performance acceptance | Spec §9.4 固定 `TSKG-BENCH-v1` generator/seed/count/distribution/topology/query expected sizes/cache state/measurement/run manifest；OQ-PERF-01 是 SLC-07 blocking edge | manifest 任一 hash/distribution/response/cache-hit/measurement 欄位不符即 invalid；reference environment 未核准時預期 blocked | contract `CONTRACT_PASS/RUNTIME_NOT_RUN`；SLO `BLOCKED_FOR_SLO_ACCEPTANCE` |

## 4. Executable-spec exit contract

| Gate | Evidence | Result |
|---|---|---|
| Problem／Goal／Actors／Scope | Spec §2 | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| BRS→US→SRS→Acceptance | Spec §3–4；trace §3–4 | `CONTRACT_PASS/RUNTIME_NOT_RUN`；31/31 只表示 internal trace |
| Canonical schema / ontology | Spec §5、§6.1、§6.4；AC-03 | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| Conflict / temporal | Spec §6.1–6.3；AC-04；TDS-CONFLICT/TIME | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| Evidence / extraction provenance | Spec §6.1、§6.5、§8.4 | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| Authority/idempotency/recovery | Spec §8 | `CONTRACT_PASS/RUNTIME_NOT_RUN`；ADR-01 尚待接受 |
| API/pagination/error/freshness/provenance | Spec §9.1–9.3；TDS-API-CONFIDENCE | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| Cache-hit `<300ms` | Spec §9.4；TDS-BENCH；OQ-PERF-01 | contract `CONTRACT_PASS/RUNTIME_NOT_RUN`；acceptance `BLOCKED_FOR_SLO_ACCEPTANCE` |
| Daily diff semantics | Spec §10 | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| Source governance | Spec §11 | `CONTRACT_PASS/RUNTIME_NOT_RUN`；未核准來源仍 blocked |
| Baseline independent reproducibility | Trace §1.1–2 | `PARTIAL/BLOCKED` pending canonical SHA-256 |
| Vertical slices/frontier | Spec §14 | contract inspection：SLC-01 only current；SLC-07 performance acceptance 明確受 OQ-PERF-01 阻擋 |

## 5. Static verification results

| Check | Command shape / evidence | Result |
|---|---|---|
| Internal SRS trace | extract/sort unique `SRS-*` from spec/trace，then `comm -3` | `CONTRACT_PASS`：31/31、sets equal；不代表 runtime/baseline correctness |
| Acceptance IDs | extract/sort unique `AC-*` | `CONTRACT_PASS`：AC-01..AC-12 |
| BL internal disposition | extract/sort unique `BL-*` | `CONTRACT_PASS`：BL-01..BL-14 且 14 rows 具 original section labels；canonical source digest仍 blocked |
| F-01 ontology | inspect canonical relationship table、normalization mapping、AC-03/API dedup/TDS case | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| F-02 lineage | inspect required identities、ConflictSet/ResolutionDecision fields、state transitions、known_at golden/negative cases | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| F-03 temporal | inspect endpoint legality、business/system current、matrix/negative cases | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| F-05 public API | route table has no public confidence filter；spec retains confidence only as provenance | `CONTRACT_PASS/RUNTIME_NOT_RUN` |
| F-07 blocker wiring | inspect §9.4, SC-07, SLC-07, OQ-PERF-01 | contract `CONTRACT_PASS/RUNTIME_NOT_RUN`；SLO blocked |
| Unsupported diagram facts | inspect diagram strings and normative context | `CONTRACT_PASS`：兩條示意鏈只出現在禁止當事實的聲明 |
| Runtime forbidden paths | Repair changed-file allowlist check | `CONTRACT_PASS`：沒有 `app/`, `scripts/`, `tests/`, `configs/` 或 runtime code/config |

## 6. Verification boundaries and downstream blockers

- 未執行 parser、authority、projection、API、database reconciliation、daily update、benchmark 或任何 project runtime；上述 behavioral cases 全是 executable contract，待後續 runtime 卡實作。
- 未驗證任何來源 terms、robots、rate、retention 或真實資料；OQ-SRC-01 阻擋 SLC-02/08 對應 adapter。
- 未驗證 2,000+ universe 實際 coverage；需 OQ-UNIV-01 的核准 manifest。
- baseline canonical SHA-256 受明確三次停損約束，F-06 維持 `PARTIAL/BLOCKED`；不得以本線先前不同 canonicalization 的 digest 代替。
- reference environment 與 executable digests 未核准；SLC-07 performance acceptance、SC-07、AC-12 維持 `BLOCKED_FOR_SLO_ACCEPTANCE`。
- 其餘 ADR、taxonomy、promotion、retention、API exposure 與 freshness decisions 仍按 Spec §15 阻擋對應 downstream slice。

## 7. Repair changed-file allowlist

Expected/allowed Repair files exactly：

1. `docs/specs/TSKG_v1.1.md`
2. `docs/evidence/TSKG-01/requirements_traceability.md`
3. `docs/evidence/TSKG-01/verification.md`
4. `docs/evidence/REPAIR-TSKG-01/repair.md`
5. `docs/tasks/2026-07-17_REPAIR-TSKG-01_executable_spec.md`（僅 status／Result）

Final staged set 與 successor parent range 必須完全等於上列；review evidence、原 TSKG task card 與 runtime paths不得變更。

## 8. Final commit verification slot

successor commit 建立後，以其 parent range 執行：

- `git diff --check <successor>^ <successor>`
- `git diff --name-only <successor>^ <successor>` 並精確比對 Repair allowlist
- `git status --porcelain=v1` 確認 clean

完整 successor SHA 與 post-commit 結果只由交付回報記錄；commit 內不嵌入自己的 SHA，以避免自參照。

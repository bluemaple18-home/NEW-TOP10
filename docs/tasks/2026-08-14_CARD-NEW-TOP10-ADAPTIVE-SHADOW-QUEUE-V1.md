---
id: CARD-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: architecture-implementation
priority: P1
owner: TOP10new research platform
role: implementation
cycle: 4
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: Card B 會把可信 evidence 轉成 queue priority，但規格已固定且禁止 live cutover，屬核心 bounded contract。
date: 2026-08-14
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
canonical_queue_change_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1/
---

# 建立 Adaptive Research Shadow Queue

## 工作名稱

把可信 native research evidence 轉成獨立、可稽核的 shadow queue。

## 已核准來源

- Source commit：`19db0c1c133030dec624bda79169179d33eefa82`
- Activation evidence：`docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-ACTIVATION-V1/capacity_and_real_canary.json`
- Native Evidence Activation：`GO`
- 兩個 real development-only 週期共 8 個 execution units，皆為 `SUCCEEDED / OBSERVED / EXACT / VALID / PROVEN_NON_SEALED`。
- 第二次 ingest 增量 0；eligibility 共 8 筆 `ADAPTIVE_ELIGIBLE`。
- Production、canonical queue、scheduler parity 未變；容量 startup gate 為 `GO`。

## Root question

能否只用可信 eligibility／learning projection，產生 deterministic、可解釋、可重建的 research shadow priority，而不改 existing manager selection 或任何 production surface？

## Ownership

### 允許修改

- `app/research/` 內 Card B shadow projection、schema、verifier 直接相關檔案。
- `config/research_shadow_queue_*`。
- `scripts/build_adaptive_shadow_queue.py`、`scripts/verify_adaptive_shadow_queue.py` 或等價 bounded CLI。
- 對應 targeted tests。
- `docs/evidence/CARD-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1/`。
- 本卡狀態與實作證據。

### 禁止修改

- `artifacts/autonomous_research/next_action_queue.json` 與 existing manager selection／ordering／quota／rerun／cooldown。
- `scripts/run_daily_research_quota.sh`、launchd／scheduler plist、背景服務。
- Production model、ranking、signals、promotion、LightGBM。
- Fog Map、weekend universe、dashboard、Optuna、dynamic refinement。
- Sealed、unknown、legacy、synthetic evidence 不得升格成 shadow priority。
- 使用者既有 dirty files：`scripts/build_weekend_universe_inventory.py`、`tests/test_weekend_universe_inventory_snapshot.py`、2026-08-02／03 storage task docs與既有 `.work/**`。

## Functional contracts

### `ASQ-FR-001`｜Fail-closed Card B admission

- Builder 前置驗證 activation evidence、capacity policy、eligibility與learning projection identity。
- 缺少兩個 real cycles、任一 receipt gate 非 100%、lineage 少於 2、matched catalog-adjacent contrasts 少於 3、capacity 非 GO或 parity drift時不得產生可用 shadow rows。
- Gate 失敗輸出 `NO-GO` 與 structured reason codes；不得 fallback 到 legacy、raw score或 synthetic fixture。

### `ASQ-FR-002`｜Projection-only queue

- 只建立 versioned `adaptive-shadow-queue.v1` projection與 immutable provenance。
- Canonical manager queue是 read-only parity lock；builder前後 hash必須一致。
- Shadow output不得被 existing daily runner、scheduler或production consumer讀取。

### `ASQ-FR-003`｜Deterministic evidence priority

- 每一列必須綁定 eligibility projection、learning projection、ledger snapshot、parameter catalog、scope、parameter、action與 supporting evidence IDs。
- 只接受 `ADAPTIVE_ELIGIBLE`、`PROVEN_NON_SEALED` 且符合 learning policy 的 evidence。
- Priority規則由 versioned policy明示；不得憑感覺新增權重。
- 相同輸入必須產生相同 row identity、順序與 semantic hash；時間戳不得影響 identity。

### `ASQ-FR-004`｜Explainability and collision safety

- 每列輸出 priority band、reason codes、evidence counts、distinct lineages、matched contrasts、scope限制與禁止泛化條件。
- Duplicate semantic action必須 dedupe；同 identity 不同 body 必須 collision/fail closed。
- `INSUFFICIENT_EVIDENCE`、`UNSTABLE`、`SHARP_PEAK/OVERFIT_RISK` 不得冒充高優先級。

### `ASQ-FR-005`｜Shadow comparison receipt

- 產生 shadow-vs-canonical comparison：新增、重疊、順序差異、無法映射與排除原因。
- Comparison只供觀察；不得 publish、transaction、tag、push或 live cutover。
- Production、queue、scheduler與容量 before/after receipt必須 PASS。

## Slices

### `ASQ-SLICE-001`｜Admission schema and gate

- 實作 strict Card B admission receipt與 verifier。
- 先用 fixtures覆蓋缺 cycle、sealed、unknown、duplicate、單 lineage、contrasts不足、capacity drift、queue drift。
- Gate：`schema_gate + recompute_gate`。

### `ASQ-SLICE-002`｜Deterministic shadow projection

- 從 official eligibility／learning projection產 shadow action rows。
- Policy、identity、dedupe、stable ordering、explanation與fail-closed。
- Gate：`recompute_gate`。

### `ASQ-SLICE-003`｜Builder, verifier and comparison

- 提供 bounded CLI、versioned output與 canonical queue parity comparison。
- 同輸入二跑 semantic identity一致；不寫 canonical queue。
- Gate：`cmd_gate + recompute_gate`。

### `ASQ-SLICE-004`｜Acceptance and rollback proof

- Targeted tests、受影響 regression、full verifier、`git diff --check`。
- 保存 before/after hashes、capacity、shadow receipt與rollback proof。
- 最終只交 candidate commit；不得 merge、push、deploy、啟 scheduler或宣稱 live。

## Acceptance

- Admission gate：PASS；所有負向 fixtures fail closed。
- Shadow rows只來自 eligible／non-sealed evidence，且 provenance完整。
- 至少一個 parameter/scope 有 `>=3` catalog-adjacent matched contrasts與 `>=2` lineages，否則合法輸出 `NO-GO_INSUFFICIENT_EVIDENCE`。
- 二跑 semantic hash、row IDs、排序完全一致。
- Canonical queue、production、scheduler hash零變更。
- Capacity持續在 `config/native_evidence_activation_policy_v1.json` budget內。
- `pytest`、CLI verifier、`py_compile`、JSON validation、`git diff --check` 全綠。

## Verification

```bash
<repo-root>/.venv/bin/pytest -q tests/test_adaptive_shadow_queue.py tests/test_research_eligibility_failure.py tests/test_parameter_learning.py
<repo-root>/.venv/bin/python scripts/verify_adaptive_shadow_queue.py --self-test
<repo-root>/.venv/bin/python -m app.research.native_evidence_activation --project-root <repo-root> --policy <repo-root>/config/native_evidence_activation_policy_v1.json
git diff --check
```

## Stop conditions

- 任何 production／canonical queue／scheduler mutation企圖：立即停止並回 `BLOCKED_SCOPE_VIOLATION`。
- Admission所需 real evidence無法由 committed evidence與 official projections重現：回 `BLOCKED_EVIDENCE_NOT_REPRODUCIBLE`，不得用 synthetic補數。
- Capacity、identity、collision、parity任一 gate失敗：`NO-GO`，不得繼續 activation。
- 同一 blocker第三次失敗：停止並交回主線。

## Deliverable

- Candidate commit SHA。
- Changed files、測試、CLI與evidence paths。
- `DELIVERED_CANDIDATE` 狀態；禁止宣稱 accepted、integrated或live。

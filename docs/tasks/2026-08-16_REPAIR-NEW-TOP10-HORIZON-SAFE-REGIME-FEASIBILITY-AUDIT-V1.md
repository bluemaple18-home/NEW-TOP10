---
id: REPAIR-NEW-TOP10-HORIZON-SAFE-REGIME-FEASIBILITY-AUDIT-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: code-repair
priority: P1
role: repair
cycle: 16
generation: 1
thickness: standard
risk: medium
model: gpt-5.6-terra
reasoning: medium
model_reason: Reviewer 已提供單一可重現 P1 與 bounded P2；沿用唯一 Repair thread，以 Terra medium 做限域修復。
date: 2026-08-16
base_sha: c2d137854d4f6fe66dec243e34e193589fed1db3
rejected_candidate_sha: 1565bafa158f9f1e2f7405361942472bef753521
production_change_allowed: false
network_allowed: false
---

# Repair Horizon-safe Regime Feasibility Audit V1

## 工作名稱

修復 feasibility audit 的巢狀 symlink authority bypass。

## Blocking finding

### `HSRF-P1-NESTED-SYMLINK-AUTHORITY-BYPASS`

- 位置：`app/research/shadow_replay_regime_feasibility.py::_safe_path`。
- 現象：路徑最終檔案不是 symlink，但父層 component 是 symlink 時，`_committed_record()` 仍接受。
- 風險：declared committed path 可透過巢狀 symlink alias 讀取另一實體，違反 authority fail-closed 契約。

## Included P2

### `HSRF-P2-UNSTRUCTURED-AUTHORITY-FAILURE`

- Invalid explicit authority-root 的 `CoveragePlanError` 未被 CLI 捕捉，會洩漏 absolute path traceback。
- 轉為結構化 `{"status":"FAIL"}`、受控非零 exit，且不得輸出 absolute path。

## Ownership

### 允許修改

- `app/research/shadow_replay_regime_feasibility.py`
- `tests/test_shadow_replay_regime_feasibility.py`
- `docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-REGIME-FEASIBILITY-AUDIT-V1/feasibility_audit.json`（僅 deterministic 必要變更）

### 禁止修改

- 其他 code、tests、evidence與所有 production／queue／scheduler／ranking surfaces。
- 網路、下載、materializer、replay、push、deploy、merge。

## Repair acceptance

- 從 authority root 到 target 的每一個既存 path component 均須拒絕 symlink。
- Internal與external nested symlink，對 `_committed_record`、`_authority_record`、`_authorized_evidence` 全部 controlled fail。
- 合法普通路徑保持 PASS；`..`、absolute path、root escape既有防線不得回歸。
- Invalid authority-root CLI只輸出 deterministic structured FAIL；不得含 traceback或 absolute path。
- 原14 tests、new regression tests、verifier、`py_compile`、JSON、`git diff --check`全通過。
- 修復後提交單一 repair candidate；不得整合或發布。

---
id: REPAIR-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: bugfix
priority: P1
role: repair
cycle: 13
generation: 1
thickness: standard
risk: high
model: gpt-5.6-terra
reasoning: medium
model_reason: 兩個 P1 finding 已固定，修復範圍 bounded；以 Terra medium 節省成本，保留 strict re-review gate。
date: 2026-08-15
reviewed_candidate_sha: 9008901b84010253064bb468b904b4b427f5071e
production_change_allowed: false
live_activation_allowed: false
---

# 修復 Shadow Replay Evidence Verifier

## 目標

關閉 Reviewer 對 candidate `9008901b84010253064bb468b904b4b427f5071e` 的兩個 P1 finding，不重跑 replay、不擴研究 scope。

## Findings

### `CARD-D-R1-F001`｜分類與 reason 可遭偽造

- `verify_evidence()` 必須重算／驗證 zero-unit `NO-GO` 的 classification 與 reason contract。
- `result.json`／`final_result.json` 不得互相矛盾又同時通過。
- Tampered `HORIZON_20_BETTER`、清空 required reason codes 必須 fail closed。

### `CARD-D-R1-F002`｜證據鏈未綁完整 sibling artifacts

- Verifier 必須要求並驗證 `execution_plan.json`、`run_receipt.json`、`batch_intent.json`、`execution_receipt.json`。
- 重算 canonical identities，端到端核對 plan、batch、run、attempt、receipt、commands 與 result binding。
- 同步偽造 identifiers 並重算 execution receipt hash仍必須 fail closed。

## 允許修改

- `app/research/isolated_shadow_plan_replay.py`
- `tests/test_isolated_shadow_plan_replay.py`
- `docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1/` 內必要的一致化 evidence。

## 禁止修改

- Proposal、catalog、queue policy、formal runner、scheduler、canonical queue、production model／signals。
- 研究矩陣、scope、horizon、SL／TP／exposure。
- 重跑 replay、synthetic evidence、merge、push、deploy。

## 驗收

- 兩個 P1 各有 targeted RED→GREEN test。
- Committed final evidence只有單一一致結論：zero-unit → `NO_COMPARISON`，structured `NO-GO_EVIDENCE_UNAVAILABLE`。
- 完整 sibling evidence identity／binding驗證通過；tampered classification、reason、plan、run、batch、receipt均失敗。
- 原 11 tests與新增 tests全綠。
- CLI verifier、py_compile、JSON validation、`git diff --check`全綠。
- 禁止路徑 diff為空；worktree clean。

## Deliverable

- 原子 repair commit SHA。
- 修復檔案、RED／GREEN、完整驗證與 finding closure mapping。
- 不得宣稱 approved、integrated或 live；交回原 Reviewer targeted re-review。

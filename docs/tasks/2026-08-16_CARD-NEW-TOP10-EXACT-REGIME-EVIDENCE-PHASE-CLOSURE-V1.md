---
id: CARD-NEW-TOP10-EXACT-REGIME-EVIDENCE-PHASE-CLOSURE-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: mainline-decision
cycle: 20
production_change_allowed: false
network_allowed: false
---

# Exact-Regime Evidence Phase Closure V1

## Root question

固定 `h20`、entry delay 1 與 exact identity 不變時，現有 current authority 或 legacy 三年資料，是否足以啟動 replay；若不足，外部回填是否仍是可證明有用的同 scope 下一步？

## 固定證據

- `docs/evidence/CARD-NEW-TOP10-RECONCILED-REGIME-FEASIBILITY-V2/feasibility.json`
- `docs/evidence/CARD-NEW-TOP10-LEGACY-REGIME-AUTHORITY-ADMISSION-AUDIT-V1/admission.json`

## 邊界

- 只讀已提交 evidence，禁止讀 ignored raw data作為 closure authority。
- 不改 horizon、entry delay、identity、episode、ranking、model或 production。
- 不下載、不回填、不執行 replay。
- evidence conflict、working-tree drift或不符合預期 status時 fail closed。

## 決策

- `GO_REPLAY`：current 或 admissible legacy authority 有 h20-safe exact identity。
- `NO-GO_CLOSE_EXACT_H20_PHASE`：兩條 evidence 均無可用 h20，且 legacy admission不可接受或無 episode。
- `BLOCKED_EVIDENCE_CONFLICT`：來源未提交、漂移、schema/status不符或結論互相矛盾。

## Fork

- replay：只有 `GO_REPLAY` 可啟動。
- external backfill：本卡只能判定 `NOT_JUSTIFIED_BY_AVAILABLE_EVIDENCE`；不得自動啟動。
- scope change：獨立 architecture candidate；不得在本卡選擇或實作。

## 產出與驗收

- `app/research/exact_regime_evidence_phase_closure.py`
- `tests/test_exact_regime_evidence_phase_closure.py`
- `docs/evidence/CARD-NEW-TOP10-EXACT-REGIME-EVIDENCE-PHASE-CLOSURE-V1/closure.json`
- 來源以 committed bytes＋SHA-256綁定；輸出 deterministic、無絕對路徑／timestamp。
- 驗證 false GO、source drift、legacy blocked、current no-go、feasible identity hostile cases。
- targeted pytest、verifier、py_compile、JSON與 `git diff --check`通過。

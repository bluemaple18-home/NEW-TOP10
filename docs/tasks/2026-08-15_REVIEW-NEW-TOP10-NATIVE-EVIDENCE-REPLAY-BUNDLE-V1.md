---
id: REVIEW-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: code-review
priority: P1
role: review
cycle: 7
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: 固定 candidate 含 2140 行 evidence exporter、CLI 與 immutable bundle，需 full correctness／regression／security／storage review。
date: 2026-08-15
base_sha: 448824c920cc2ce83c264e08b2a3475977306bfb
candidate_sha: 160823387689d3a5e557e7f004dbb46b6977d7eb
production_change_allowed: false
candidate_code_change_allowed: false
evidence_path: docs/evidence/REVIEW-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/
---

# 審查 Native Evidence Replay Bundle

## 工作名稱

獨立反證兩週期 replay bundle、verifier 與 parity／cleanup 證據。

## 固定範圍

- Base：`448824c920cc2ce83c264e08b2a3475977306bfb`
- Candidate：`160823387689d3a5e557e7f004dbb46b6977d7eb`
- 只審查 `git diff <base>..<candidate>` 與必要關聯入口。
- Candidate code 唯讀；不得修碼、merge、push、deploy、啟 scheduler或觸碰 production／canonical queue／主 ledger。

## Candidate 宣稱

- 兩個 development-only cycles 產生 2 + 6 valid units。
- 8 adaptive-eligible observations、4 distinct lineages、4 matched contrasts。
- Admission／verifier／capacity／cleanup／parity皆 PASS。
- Compact bundle 可在 isolated root cleanup 後獨立重算。
- Canonical queue、Research Spine、主 ledger、production、scheduler hashes不變。

## Review 視角

1. `correctness`：identity、semantic hash、dedupe、排序、eligibility／learning重算、tamper fail-closed。
2. `regression`：既有 Runner、activation、projection schema與CLI契約是否被破壞。
3. `security/path`：路徑穿越、絕對路徑、tmp ownership、cleanup越界、shell／JSON外部輸入。
4. `performance/storage`：是否無界載入、重複大檔、未清理 isolated DB、容量 receipt是否可信。
5. `test_gap`：tests是否真打到兩週期、tamper、duplicate、sealed／unknown、parity與post-cleanup重驗。
6. `maintainability`：559 行模組與439行CLI是否把 workflow複製成第二套引擎。

## 必做驗證

```bash
git diff --check 448824c920cc2ce83c264e08b2a3475977306bfb 160823387689d3a5e557e7f004dbb46b6977d7eb
<repo-root>/.venv/bin/pytest -q tests/test_native_evidence_replay.py
<repo-root>/.venv/bin/pytest -q tests/test_research_batch_owner.py -k isolated_native_evidence
<repo-root>/.venv/bin/python scripts/native_evidence_replay_bundle.py --help
<repo-root>/.venv/bin/python -m py_compile app/research/native_evidence_replay.py scripts/native_evidence_replay_bundle.py
```

- 獨立重算 manifest／bundle hashes與counts；不得只採信 candidate summary。
- 檢查 tracked evidence 無絕對路徑、秘密、tmp residue與大型 DB。
- 既有 activation suite 的 canonical queue 缺失須判定是否 pre-existing；若 candidate 新增或遮蔽風險才列 finding。

## Findings 契約

- 每項含 severity、category、`path:line`、觸發條件、證據、風險、建議修法、validation gap、confidence。
- 分開 Spec axis 與 Standards axis。
- P0／P1、production safety、證據可偽造或 cleanup越界：`REVIEW_CHANGES_REQUIRED`。
- 無阻塞 finding：`REVIEW_APPROVED`，仍列剩餘風險與驗證缺口。

## Deliverable

- Verdict。
- Findings 或明示無阻塞問題。
- 實跑 tests／verifier／hash／path／capacity結果。
- reviewed candidate SHA 必須精確等於 `1608233...`。
- 不修改 candidate code。

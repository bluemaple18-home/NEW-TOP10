---
id: REVIEW-RESEARCH-QUEUE-01-verification
status: REVIEW_NO_GO
type: review-evidence
reviewed_commit: fea9307224d3dccef28428773d09cf061491c5e0
base_sha: 2ca23b2d6157e3336ae69babe81cb0cefb6800bd
---

# REVIEW-RESEARCH-QUEUE-01 Verification

## Verdict

`REVIEW_NO_GO`

## Findings

### [P1] 第二次執行後仍可重跑的 partial topic 被移出唯一 queue

- Path: `scripts/run_autonomous_research.py:808-820`
- Evidence: topic 第二次仍為 `partial_needs_followup`、`run_count=2`，但 queue 被清空，第三次合法重跑無法發生。
- Required repair: next queue 必須依 post-run eligibility/actionability 建立，由 cooldown gate 阻止立即重跑。

### [P1] History fallback 把 dry-run selection 當成真實執行證據

- Path: `scripts/run_autonomous_research.py:502-516`
- Evidence: `execute=false` 的 history row 被當成 fallback timestamp，違反 fail-closed cooldown 契約。
- Required repair: fallback 只接受能證明真實 execution 的 row。

### [P2] Verifier 與 operator 文件仍保留已移除的 flag 語意

- Paths: `scripts/verify_autonomous_research.py:291-306`; `docs/architecture/AUTONOMOUS_RESEARCH_MANAGER.md:46,89-97`
- Evidence: verifier 的 legacy rerun checks 失敗，文件仍宣稱 `--rerun`／`--include-rejected` 可授權重跑。

## Verification

- 相關 unittest：17 tests passed。
- `scripts/verify_autonomous_research.py`：failed，對應上述 stale legacy checks。
- `bash -n scripts/run_fog_research_worker.sh`：passed。
- `git diff --check`：passed。

## Acceptance mapping

- Spec axis：queue lifecycle 與 fail-closed history requirement 未滿足。
- Standards axis：production/research boundary 保持，但 correctness findings 阻塞 acceptance。
- Required next step：另開 Repair card；reviewer 不修改 candidate。

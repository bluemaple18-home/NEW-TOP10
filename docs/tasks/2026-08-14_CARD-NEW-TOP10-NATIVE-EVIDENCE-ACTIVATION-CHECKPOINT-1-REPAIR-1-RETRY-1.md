---
id: CARD-NEW-TOP10-NATIVE-EVIDENCE-ACTIVATION-CHECKPOINT-1-REPAIR-1-RETRY-1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: repair
priority: P1
owner: TOP10new research platform
role: repair
cycle: 1
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: 固定 integration candidate 的 Runner authority 與隔離 evidence 閉環屬高影響 bounded repair；規格與單一 P1 已由 Reviewer 鎖定。
date: 2026-08-14
production_change_allowed: false
live_activation_allowed: false
replacement_authorized: true
replaces_thread_id: 019fff51-1922-7530-8861-5f0b7c55cbbd
---

# Native Evidence Activation Repair 1 Retry 1

## Replacement 原因

原 Repair task 連續三次因已回收／非 writable worktree 與 `apply_patch` 路由不一致而無法修改；沒有產生本 finding 的 diff 或 commit。使用者已明確核准 replacement。本卡延續同一 chain、role、cycle 與 finding，不重置 Repair 額度。

## 固定輸入

- Rejected integration candidate：`19cfc78fe27a45cf00a2cd4c1ae1a416b844fd67`
- Reviewer task（必須復用）：`019fff37-cb09-7403-bf98-332c37eeb8c5`
- Replaced Repair task：`019fff51-1922-7530-8861-5f0b7c55cbbd`
- Verdict：`NO-GO`
- Finding：`P1-ISOLATED-CANARY-BYPASSES-RUNNER`

## 問題

現有 focused canary 直接呼叫 `begin_topic_attempt()`／`finish_topic_attempt()` 產生 receipt，沒有經過 `scripts/run_autonomous_research.py` Runner。真 isolated CLI 無法在隔離 root 找到 Batch Intent，回 `BATCH_INTENT_MISSING`，因此尚未證明：

```text
Batch Intent → Runner → Receipt → Observation → Eligibility
```

## 唯一修復責任

1. RED：focused canary 必須呼叫真 Runner entrypoint，並重現現況 `BATCH_INTENT_MISSING`／receipt 0。
2. GREEN：將 Runner 的 output、spine、CAS、ledger、manager/history、logs、matrix/comparison 全部接到同一 pytest tmp root。
3. 只可 stub 昂貴 backtest、產題或選題；不得 stub Batch Intent、Runner authority、Receipt、matrix authority、ledger ingestion或 eligibility。
4. 需產 1 intent、1 attempt、1 terminal receipt；requested/executed exact match；executed units 2。
5. 第一次 ingest observations 2、第二次 0；`ADAPTIVE_ELIGIBLE` 2；sealed/unknown eligible 0。
6. canary 前後 canonical Research Spine、正式 ledger、manager/history與 production inventory path set/hash完全相同。

## Allowlist

- `scripts/run_autonomous_research.py`
- `tests/test_research_batch_owner.py`

需要其他 functional path 時，先回主線附證據並停止。不得修改 `docs/tasks/**`、production ranking、model、signals、strategy config、promotion、launchd、daily scheduler 或 Adaptive Queue。

## Required verification

```bash
uv run pytest -q tests/test_research_batch_owner.py tests/test_daily_research_batch_owner_shell.py
uv run pytest -q tests/test_autonomous_research_receipts.py tests/test_research_spine_daily_cutover.py
uv run pytest -q tests/test_research_batch_owner.py -k isolated_native_evidence
uv run python -m py_compile app/research/batch_owner.py scripts/publish_research_batch_intent.py scripts/run_autonomous_research.py
bash -n scripts/run_daily_research_quota.sh
git diff --check
```

`tests/test_native_evidence_activation.py` 的 `AUTONOMOUS_NEXT_ACTION_QUEUE` 缺失維持 `PRE-EXISTING`；不得補造 artifact。

## Acceptance／停止條件

- 真 Runner 閉環通過，counts、idempotency與 canonical inventory invariant 全部成立。
- Reviewed scheduler owner/hash/path forged 反例仍 fail closed。
- 單一 repair candidate commit；不得 push、merge、deploy、live 或 production write。
- 完成後送回既有 Reviewer task targeted re-review。
- 衝突、需要 allowlist 外檔案、identity/root 不明或同一 blocker再現即停止。

## Rollback

捨棄 replacement Repair candidate；保留 `19cfc78...`、Reviewer evidence 與正式 artifacts 不變。

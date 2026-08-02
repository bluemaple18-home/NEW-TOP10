---
id: FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01-REPAIR-02
status: CANDIDATE_READY
type: repair
ownership: repairer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
chain_id: FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS
cycle: 2
code_base_sha: 33309e921a6b460967c9c96f30da5fca5630b075
review_receipt_sha: 1c967b0539056d7b40ff353b82e57e5033ab3c40
---

# FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01 Repair 02

## Role

你是獨立 Repairer。只修 Review 的兩個 P1，交付新 candidate；不得自審、整合、deploy、
操作 LaunchAgent／circuit／live probe，或寫入真實 runtime artifacts/logs。

## Required inputs

- 原卡：`docs/tasks/2026-08-02_FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01.md`
- Review 卡：`docs/tasks/2026-08-02_FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01_review.md`
- NO_GO receipt：`.work/FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01/review/review_receipt.md`
- Rejected candidate：`33309e921a6b460967c9c96f30da5fca5630b075`

## P1-01 — identity confusion

default-v2 canonicalization 不得只憑 suffix 信任 row。當 `topic_id` 存在時，raw
`combo_id` 必須與該 raw topic＋dimensions 導出的 expanded identity 完全一致，才可映射到
base；不一致紀錄必須保持原 identity，不得終結另一題。history 缺 `topic_id` 的既有 replay
格式仍需以其自身 expanded combo 安全還原 base。

新增負向 regression test，必須重現 Review receipt 的 mismatched topic/combo probe 並轉綠；
同時保留 default-v2、non-default v2、lifecycle child 契約。

## P1-02 — cross-invocation replay

`NO_PROGRESS` 必須跨同日期 invocation 抑制相同 representative identity set 的 replay。
可重用既有 per-date progress artifact 作 durable guard；若前次為 no-progress 且本次 queue
identity 未改變，必須在啟動 replay command 前 fail closed，清楚記錄 blocked status/reason，
且不得再次執行同一 batch。queue identity 改變後必須可恢復。

新增離線雙 invocation regression：第一次執行一批後 `NO_PROGRESS`；第二次相同 identity
不得呼叫 replay；identity 改變後才允許重新嘗試。測試必須使用 temp/mocks，不得讀寫真實
`artifacts/**` 或 `logs/**`。

## Scope boundaries

- 不新增或修改 circuit、LaunchAgent plist、`scripts/run_fog_research_worker.sh`。
- 不處理 15 分鐘觸發本身；只確保相同 queue 不再重跑昂貴 batch。
- 不改 ranking、model、weights、promotion、topic supply 或 production 設定。
- 容量安全閘門通過前禁止 live run、deploy、schedule load。

## Exact changed-file allowlist

- `docs/tasks/2026-08-02_FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01.md`
- `docs/tasks/2026-08-02_FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01_repair-02.md`
- `.work/FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01/status.md`
- `.work/FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01/result.md`
- `.work/FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01/evidence/repair-02.md`
- `app/research/map_contract.py`
- `scripts/run_representative_replay_drain_worker.py`
- `tests/test_representative_replay_drain_worker.py`
- `tests/test_representative_replay_lifecycle.py`

Review card／receipt 只讀，禁止修改。若需要 allowlist 外檔案，停止並回報 scope request。

## Verification

- 先查 CodeGraph；無結果才限域 `rg`。
- 兩個 Review 負向 probes RED→GREEN。
- 原 targeted 與受影響 Fog/weekend suites。
- 全套 pytest；若只有既有 isolated evidence availability failure，須單獨重現並保存。
- changed Python `py_compile`、debug audit、exact allowlist、`git diff --check`、clean worktree。

## Exit

回報固定 base／candidate SHA、兩個 P1 的 RED→GREEN、changed files、tests、remaining risks，
並停在 `READY_FOR_RE_REVIEW`。不得 push、merge 或 deploy。

## Execution receipt

- P1-01 RED→GREEN：mismatched topic/default-v2 combo 不再誤映到 target base；lifecycle
  child 的 default/non-default v2 先驗證 raw identity，再映 parent。
- P1-02 RED→GREEN：第一次 no-progress 後，相同 identity 的第二次與第三次 invocation
  都在 replay 前 `BLOCKED / unchanged_no_progress_identity`；identity 改變後恢復嘗試。
- 驗證使用 temp/mocks，未讀寫真實 runtime artifacts/logs，未做 live、LaunchAgent、
  circuit、deploy、push 或 merge。
- `READY_FOR_RE_REVIEW`。

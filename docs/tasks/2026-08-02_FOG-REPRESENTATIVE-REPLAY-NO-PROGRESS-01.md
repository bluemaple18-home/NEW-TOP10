---
id: FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01
status: REPAIR_CANDIDATE_READY
type: repair
ownership: executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 跨 run-history canonicalization、weekend inventory 與 unattended drain 停損；錯誤會造成排程反覆寫入且容量風險升高
chain_id: FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS
cycle: 1
code_base_sha: ae187d286d70f1c5ffed86798e9a4a53abfb5103
---

# FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01

## Role

你是本卡 Executor。只交付 candidate，不自審、不整合、不 deploy、不載入或操作排程。

## Root question

如何讓 default-v2 representative replay 的既有完成證據正確終結對應 base/default
座標，並讓 drain 在沒有任何新 evidence 或 queue identity 變化時立即停止，避免同一
24 筆在單一週期被重播 6 次？

## Preserved failure evidence

- runtime artifact：`artifacts/weekend_training/representative_replay_drain_2026-08-01.json`
- 表面狀態：`OK / max_batches_reached`
- 實際結果：initial/latest queue `144 / 144`、6 batches、144 completed、
  `appended_run_history_count=0`、`progressed=false`。
- queue最前24筆已存在於`run_history.jsonl`：20筆`LOW_INFORMATION`、4筆`REJECTED`。
- 24筆皆為default-v2座標；`is_completed_v2_expansion_record()`回傳false，
  base/default scenario仍為pending。
- drain每批固定傳入`--start-index 0`，因此未到達其餘120筆。

Red-capable diagnostic：對上述artifact要求「多批成功時，queue identity或append至少一項
前進」會exit 1；此證據已保存於task workspace。

## Requirements

- `FR-01`：default-v2完成紀錄必須canonicalize到同一base/default scenario；不得同時
  重複計入base progress與v2 expansion progress。
- `FR-02`：非default-v2完成紀錄維持原combo identity與expansion計數語意。
- `FR-03`：inventory／queue重建後，已完成default-v2 replay不得繼續標成
  `PENDING / REPRESENTATIVE_REPLAY`。
- `FR-04`：drain每批必須以新增run-history evidence或representative combo identity
  變化證明前進；兩者皆無時第一批後立即停止，禁止跑滿max batches。
- `FR-05`：no-progress必須產生明確非`OK`的artifact status／stop reason，但以受控方式
  結束，不進行後續重播；不得以force append或重複history偽造進度。
- `SC-01`：既有lifecycle child canonicalization、non-default v2、base progress與queue
  bounded 144契約不退化。
- `SC-02`：不改production ranking、model、weights、promotion、topic supply或排程設定。
- `SC-03`：本卡只做離線code/tests；容量安全閘門通過前禁止live run、deploy或載入
  `com.new-top10.fog-research-worker`。

## Ranked hypotheses

1. default-v2歷史紀錄未canonicalize為base combo，是queue不終結的主因；若修正，
   initial linkage後最前24筆應退出pending queue且不增加v2 expansion count。
2. drain固定`start-index=0`不是單獨根因，但缺少progress invariant使上游分類退化時
   擴大為6批重播；加入identity／append停損後，fixture應在第一個零進度batch停止。
3. history根本不存在不是原因；現有24筆raw history已證明此假說為false。

## Slices

### `SLICE-RED`

- 新增單一RED fixture：default-v2 completed replay已在history，但canonical base scenario
  仍pending；drain第二批再次選到相同代表集合。
- RED必須因目標症狀失敗，不得用import error、缺fixture或live artifact作為測試依賴。

### `SLICE-CANONICALIZATION`

- 最小修正history canonicalization，使default-v2 evidence只計入base/default一次。
- 驗證non-default v2與lifecycle child不退化。

### `SLICE-DRAIN-STOPLOSS`

- 加入batch progress invariant與明確no-progress terminal status。
- 只停止本次drain；不得啟用排程、改LaunchAgent或清理runtime artifacts。

## Exact changed-file allowlist

- `docs/tasks/2026-08-02_FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01.md`
- `.work/FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01/**`
- `app/research/map_contract.py`
- `scripts/run_representative_replay_drain_worker.py`
- `tests/test_research_map_contract_boundary.py`
- `tests/test_representative_replay_drain_worker.py`
- `tests/test_representative_replay_lifecycle.py`

若根因要求allowlist外檔案，停止並回報scope request。

## Do not touch

- 主worktree目前未提交的`scripts/build_weekend_universe_inventory.py`與
  `tests/test_weekend_universe_inventory_snapshot.py`。
- `scripts/run_fog_research_worker.sh`、LaunchAgent plist、任何circuit state/context。
- `artifacts/**`、`logs/**`、ranking、model、weights、promotion與closed/sealed registry。

## Verification

- Phase 0 RED保存於`.work/FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01/evidence/phase0_red.md`。
- `.venv/bin/python -m pytest -q tests/test_research_map_contract_boundary.py tests/test_representative_replay_drain_worker.py tests/test_representative_replay_lifecycle.py`
- 受影響weekend／Fog map tests。
- `.venv/bin/python -m pytest`
- changed Python `py_compile`、`rg -n "DBG-|pdb|breakpoint\\("`、exact allowlist audit、`git diff --check`。
- 禁止以live Fog、schedule reload或容量清理作candidate驗證。

## Candidate exit

交付exact base／candidate SHA、RED→GREEN、changed files、完整驗證、remaining risks與
`READY_FOR_INDEPENDENT_REVIEW`；不得merge或deploy。

## Execution receipt

- Completed default-v2 records now canonicalize to the base combo even when raw replay history omits `topic_id`; non-default v2 records retain expansion identity.
- Drain batches now record representative identity sets and accept progress only from non-forced appended evidence or an identity-set change.
- A zero-progress successful command batch terminates immediately as `NO_PROGRESS / no_progress`; forced duplicate append does not satisfy the invariant.
- No live Fog run, artifact/log runtime write, schedule load, deploy, push, merge, ranking, model, weight, or promotion change was performed.

## Repair cycle 2 receipt

- default-v2 canonicalization now requires an exact raw topic/dimensions/combo match before
  mapping to base; mismatched normal and lifecycle-child rows retain their raw combo identity.
- The per-date progress artifact now durably blocks a later invocation with the same
  representative identity before replay. Repeated blocked invocations remain blocked; an
  identity-set change resumes the attempt.
- Both review P1 probes were captured RED and turned GREEN using offline temp/mocks only.
- Full suite: `633 passed, 254 subtests passed, 1` pre-existing isolated evidence-availability
  failure, reproduced alone.
- `READY_FOR_RE_REVIEW`.

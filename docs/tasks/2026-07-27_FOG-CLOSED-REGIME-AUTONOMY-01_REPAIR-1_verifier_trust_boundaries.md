---
id: FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1
status: READY_TO_DISPATCH
type: repair
chain_id: FOG-CLOSED-REGIME-AUTONOMY-01
repair_generation: 1
ownership: repair_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
base_candidate_sha: 5e1de6aa170f7c2446e5da76fadfa75a88495e54
review_card_commit: 82db063e706207ed5dbcbacd1bf103f672a2b037
evidence_path: docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1/
---

# FOG-CLOSED-REGIME-AUTONOMY-01 Repair-1：封閉 verifier 信任邊界

## Root question

如何讓 processed-ID、daily runtime receipt 與 production hash 三個 recovery gate
分別使用獨立、可信、可重算的 authority，確保偽造 inventory、陳舊 receipt 或已變更的
production artifacts 都無法取得 recovery approval？

## Review disposition

原 Reviewer 與替補 Reviewer 的背景任務均遭平台中止，未能建立正式 review commit；
不得把這件事解讀成 `GO`。原 Reviewer 已在可見 Review task
`019fa3e3-6289-7c60-80a5-0e3760f15851` 實際重現下列三項阻斷結果：

1. inventory 中一個已 processed ID 被 forged ID 取代後，processed verifier 仍回
   `OK` 且 `difference=[]`。
2. 日期為 1999、identity 偽造且缺少 `state_transition` 的 runtime receipt，daily
   verifier 仍回 `COMPLETED`。
3. production model 內容與 hash 已改變時，production hash gate 只回傳新的當下
   hash，沒有與可信 baseline 比較。

因此主線裁定為 `NO_GO_PENDING_REPAIR_1`；candidate 不得整合或進入 live acceptance。
Repair 必須把上述回報固化成可重現的 red tests，不得只依文字修補。

## Findings

### R1-P1-01：Processed-ID verifier 缺少獨立 artifact comparison

- verifier 的 map／inventory 集合不可由同一份 run-history comprehension 同源產生。
- 必須分別讀取實際 research-map artifact 與實際 inventory artifact，再以同一個
  completion predicate 正規化，最後比較兩個獨立集合。
- 任一 artifact 缺失、schema／contract／source hash 不符、重複 ID、forged ID、
  missing ID 或非 completed row 均須 fail closed。
- receipt 必須保存兩邊 artifact path、content hash、source lineage、set count 與
  bounded symmetric-difference sample。

### R1-P1-02：Daily runtime verifier 接受 stale／forged receipt

- receipt 必須綁定預期的 run date、queue owner、runner identity、schema、
  contract hash、history hash、exact regime、state transition、topic runs 與
  production-impact declaration。
- 日期不符、identity 不符、欄位缺失、額外未知 schema、future/stale receipt、
  artifact path/hash drift 均須 fail closed。
- `COMPLETED` 不能只由狀態字串或使用者可控 payload 判定。

### R1-P1-03：Production hash gate 沒有 trusted baseline

- recovery 前必須建立 immutable baseline receipt，列出受保護 production
  model／baseline／ranking／weight／promotion artifacts 的 canonical path、
  content hash、git/source identity 與建立時間。
- recovery verifier 必須把當下重算結果與該 trusted baseline 逐項比較；只回傳
  當下 hash 不構成 gate。
- baseline 缺失、可被待驗 runtime 同步覆寫、path set 增減、hash drift 或 source
  identity 不符均須 fail closed。
- 不得把 baseline 放在 runtime 可任意重寫後仍視為可信的同一 receipt。

## Phase 0：必須先紅

修改 production code 前新增三組 deterministic attack tests：

1. 在獨立 fixture 中，以 forged ID 替換 inventory 的一個 processed ID；舊 verifier
   必須錯誤放行而測試呈紅，修後必須拒絕並列出 missing／unexpected ID。
2. 建立 `1999-01-01`、偽 identity、缺 `state_transition` 的 receipt；舊 verifier
   必須錯誤回 `COMPLETED` 而測試呈紅，修後逐欄拒絕。
3. 保存 baseline 後修改一個受保護 model fixture；舊 gate 只回新 hash而測試呈紅，
   修後必須因 hash drift 拒絕 recovery。

Red evidence：
`docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1/phase0-red.md`。

## Requirements

- 保留 candidate 已完成的 closed-regime public wiring、queue ownership、fail-closed
  history mutations與 processed completion predicate。
- verifier 的 authority input 必須可由 fixture 注入，測試不得讀寫 live state。
- 所有 path 必須 repo-relative 或明確 runtime root；不得寫入跨機絕對路徑。
- recovery approval 必須是三個 trust gates 全綠的 AND；任一 exception／missing
  evidence 都是拒絕。
- 新增 regression tests 覆蓋合法 receipt／artifact／baseline，避免只會拒絕。

## Allowlist

- `scripts/verify_weekend_universe_inventory.py`
- `scripts/build_weekend_universe_inventory.py`（僅必要的 artifact lineage）
- `scripts/verify_daily_research_quota.py`
- candidate 新增的 bounded runtime／recovery verifier
- `scripts/run_controlled_grid_drain_host_runner.py`（僅 verifier input wiring）
- 直接相關的 `tests/test_*.py`
- `docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1/**`
- 本卡狀態／receipt 更新

## 禁止範圍

- 不修改 research policy、statistical gates、ranking、模型內容、權重、promotion、
  API、UI 或外部資料。
- 不操作 live retry state/context、LaunchAgent、queue 或 production artifacts。
- 不 merge、push、deploy、kickstart 或執行三輪 live acceptance。
- 不以 count equality、當下 self-reported hash、receipt status string 或同源集合
  取代獨立驗證。

## Verification

至少執行：

```bash
cd <repo-root>
.venv/bin/python -m pytest -q \
  tests/test_weekend_universe_inventory_snapshot.py \
  tests/test_daily_research_quota_verifier.py \
  tests/test_fog_closed_regime_runtime.py
.venv/bin/python -m pytest -q
bash tests/test_fog_research_retry_circuit.sh
bash tests/test_research_lock_contention.sh
bash -n scripts/run_daily_research_quota.sh
bash -n scripts/run_fog_research_worker.sh
git diff --check
```

另需保存三個 red→green 攻擊輸出、changed-files allowlist、candidate SHA，以及
production model／baseline／ranking／weight／promotion artifacts 在 repair 前後的
hash（內容必須 unchanged）。

## Success criteria

- `SC-R1-01`：forged／missing processed ID 使 verifier fail closed，並正確列出
  symmetric difference。
- `SC-R1-02`：stale／forged／缺欄 receipt 無法取得 `COMPLETED` 或 recovery approval。
- `SC-R1-03`：trusted baseline 可偵測 protected artifact hash/path/source drift。
- `SC-R1-04`：合法 fixture 全綠，full suite 與 shell gates 通過，protected
  production artifacts hashes unchanged。

## Delivery

- 只交付 `DELIVERED_REPAIR_1_CANDIDATE`。
- Repair candidate 必須回到同一獨立 Review chain 進行 re-review。
- Reviewer `GO_FOR_MAINLINE_RUNTIME_ACCEPTANCE` 前不得整合或操作 live runtime。
- 同一 blocker 失敗三次立即停手，不得第 4 次盲重試。

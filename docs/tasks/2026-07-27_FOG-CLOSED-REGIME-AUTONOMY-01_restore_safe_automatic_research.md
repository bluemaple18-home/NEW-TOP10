---
id: FOG-CLOSED-REGIME-AUTONOMY-01
status: RUNNING
type: implementation
chain_id: FOG-CLOSED-REGIME-AUTONOMY-01
successor_of:
  - FOG-RECOVERY-01
  - REGIME-RESEARCH-AUTONOMY-01
ownership: implementation_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 需統一跨 research-map／inventory 的 processed 語意、接上 default-off 的 closed-regime contract，並安全恢復 launchd retry circuit；涉及跨模組狀態一致性與高回退成本。
source_sha: f59e781c5742ec995206b3c3ec6aefe346670818
evidence_path: docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01/
traces_to:
  - FR-FOG-CR-01
  - FR-FOG-CR-02
  - FR-FOG-CR-03
  - SC-FOG-CR-01
  - SC-FOG-CR-02
  - SC-FOG-CR-03
  - SC-FOG-CR-04
---

# FOG-CLOSED-REGIME-AUTONOMY-01：恢復安全的自動盤勢研究

## Root question

如何讓 Fog research worker 使用同一份可重算的 processed-combination 語意建立
research map 與 weekend inventory，接上已接受的 closed-regime research contract，
並在 deterministic gates 通過後安全恢復每 15 分鐘的自動研究？

這是 `FOG-RECOVERY-01` 達 Repair-2 上限後的 successor chain，不得建立或偽裝成
Repair-3；舊 chain 維持 `BLOCKED_REPAIR_LIMIT`。

## 已知事實與 failure evidence

- `REGIME-RESEARCH-AUTONOMY-01` 已於 main `f59e781` 完成 acceptance。
- 新模式 `--closed-regime-research` 為 default-off，且必須提供
  `--market-regime-history`。
- 現行 `scripts/run_daily_research_quota.sh`／Fog worker 未傳上述兩個參數，故目前
  自動執行的是 legacy research mode。
- 2026-07-27 自動 worker 已成功執行 3 批、每批 2 個 topic；研究本體成功，
  downstream controlled-grid linkage 失敗。
- `run_controlled_grid_drain_host_runner.py` 在 refresh／verify map 後仍得到：
  - research map `expanded_processed=33358`
  - weekend inventory `current_processed_count=33360`
  - 固定差異 `2`
- 同一 fingerprint 已連續失敗 3 次：
  `logs/fog_research_retry_20260727.state` 為 `circuit_open=1`。
- LaunchAgents 均已載入、每 900 秒喚醒；Fog worker 因 circuit open 正確 fail
  closed，PM harness 因 queue owner 是 `fog_worker` 正確跳過。

## 可證偽假說

1. `H-SEMANTICS`：research map 的
   `completed_v2_expansion_count()`／run-history folding 與 weekend inventory
   的 current-status folding 對兩個 combination IDs 定義不同。若為真，列出逐 ID
   symmetric difference 後，兩條 recompute 應可歸一為同一集合與 count。
2. `H-RACE`：來源在 inventory build 期間前進。若為真，固定 immutable fixture
   不應重現差 2；若固定 fixture 仍重現，排除 race、不得以 sleep／retry 掩蓋。
3. `H-WIRING`：strict mode 未啟用只是 runtime wiring 缺口。若為真，加入受契約
   驗證的 regime-history resolution 與 CLI args 後，public worker receipt 必須含
   `closed_regime_research=true` 與 exact-regime lineage；缺 history 時 fail closed。

## Requirements

### FR-FOG-CR-01：Processed semantics authority

- 建立單一 deterministic recompute authority，讓 research map、weekend inventory
  與 verifier 對 processed combination IDs 使用相同定義。
- Evidence 必須列出修前差異的兩個實際 combination IDs、來源 row 與分類原因。
- 不得用 `abs(delta) <= 2`、硬編碼補 2、忽略 mismatch、sleep 或無限 retry。

### FR-FOG-CR-02：Closed-regime runtime wiring

- 只有 queue owner `fog_worker` 執行研究；不得讓 PM harness 與 Fog worker 同時
  mutation 同一 queue。
- daily/Fog public path 必須能取得當日可信 `market_regime_history.v2` artifact，
  並明確傳入：
  - `--closed-regime-research`
  - `--market-regime-history <artifact>`
- history 缺失、日期超前、exact regime 不可用、transition／`UNKNOWN` 時 fail
  closed；不得回退 legacy mode。
- runner receipt 必須保存 contract hash、history hash、exact regime、topic runs、
  state transition 與 production-impact declaration。

### FR-FOG-CR-03：Auditable circuit recovery

- circuit open 時不得自動刪除 retry state。
- 只有 processed recompute、inventory verifier、closed-regime canary、targeted
  tests 與 production-hash gate 全部通過，才可使用既有 explicit recovery path
  輪替 state/context。
- recovery 後 kickstart Fog LaunchAgent；不得啟用 PM harness queue mutation。

## Allowlist

- `scripts/build_weekend_universe_inventory.py`
- `scripts/verify_weekend_universe_inventory.py`
- `scripts/run_controlled_grid_drain_host_runner.py`
- `scripts/run_daily_research_quota.sh`
- `scripts/run_fog_research_worker.sh`
- `scripts/run_top10_fog_map_handoff.py`
- `scripts/run_autonomous_research.py`（僅在 public wiring 無法由 wrapper 完成時）
- `scripts/build_market_regime_history.py`（僅限可信 artifact resolution）
- `scripts/verify_daily_research_quota.py`
- 直接相關的 `tests/test_*.py`／shell regression tests
- 新增 bounded runtime verifier／canary
- `docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01/**`
- 本卡狀態更新

## 禁止範圍

- 不修改 production ranking、模型、權重、promotion、API 或 UI。
- 不下載新資料、不呼叫外部 AI、不發 Discord／通知、不交易。
- 不宣稱 legacy 2,866,752 expanded grid 已成為可信 closed-regime universe；
  strict contract 仍以已接受的 720 authority 與 profile coverage 為準。
- 不降低 Bonferroni、sealed OOS、episode、cooldown 或 queue eligibility gates。
- 不刪除、覆寫既有 retry state／context；只允許驗證後可稽核輪替。
- Executor 不得 merge、push、deploy、acceptance 或自行宣稱 production recovery。

## Phase 0：Red-capable feedback loops

修改前必須先保存並重跑：

1. 固定 source fixture，重現 map `33358`／inventory `33360` 的逐 ID difference；
   測試修前必須紅，且能辨識錯誤語意，不只比 count。
2. public daily/Fog command test：修前 receipt 缺
   `closed_regime_research=true`／history lineage，修後必須存在。
3. missing／future／transition regime history mutation tests，均須 fail closed。
4. circuit recovery regression：任一 gate 紅時不得輪替；全部綠才允許 recovery。

Red evidence 寫入：
`docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01/phase0-red.md`。

## Vertical slices 與 blocking edges

### S-SEMANTICS（frontier）

統一 processed-ID authority，讓 research map／inventory／verifier 對 immutable
fixture 得到相同集合與 count。

### S-WIRING（blocked by S-SEMANTICS）

把 queue owner 的 daily/Fog public path 接到 closed-regime mode；缺可信 history
時 fail closed，不可 legacy fallback。

### Checkpoint 1

重跑逐 ID recompute、inventory、host-runner order、daily quota、queue ownership、
closed-regime targeted tests與 `git diff --check`。任何紅燈不得進 circuit recovery。

### S-RUNTIME-ACCEPTANCE（blocked by Checkpoint 1）

1. 保存 recovery 前 retry state/context hash。
2. 執行 verifier-approved explicit circuit recovery。
3. kickstart `com.new-top10.fog-research-worker`。
4. 觀察連續 3 個 scheduler cycles；每輪 quota budget 為 5，總 budget 為 15。
   cooldown／eligibility 可使實際 topic 數低於 15，但必須以 deterministic receipt
   說明，不得繞過 policy 製造工作。
5. 至少 1 個真實 closed-regime topic 完成 public path；若目前無 eligible topic，
   必須用已接受 canary 證明 runtime，並將 live 狀態標成
   `HEALTHY_NO_ELIGIBLE_WORK`，不得偽稱已執行研究。

## Success criteria

- `SC-FOG-CR-01`：修前兩個差異 IDs 已定位；修後 map／inventory processed-ID
  symmetric difference 為 `[]`。
- `SC-FOG-CR-02`：controlled-grid linkage、inventory verifier、research-map
  verifier 全部 `OK`，沒有容忍差值。
- `SC-FOG-CR-03`：Fog public receipt 證明 strict mode、可信 history lineage、
  exact regime 與 fail-closed mutations。
- `SC-FOG-CR-04`：circuit 經 gate 後恢復；連續 3 個 scheduler cycles 無相同
  fingerprint，production model／ranking／weights hashes unchanged。

## Verification

至少執行：

```bash
cd <repo-root>
bash -n scripts/run_daily_research_quota.sh
bash -n scripts/run_fog_research_worker.sh
.venv/bin/python -m py_compile \
  scripts/build_weekend_universe_inventory.py \
  scripts/run_controlled_grid_drain_host_runner.py \
  scripts/run_autonomous_research.py
.venv/bin/python -m pytest -q \
  tests/test_weekend_universe_inventory_snapshot.py \
  tests/test_controlled_grid_host_runner_order.py \
  tests/test_daily_research_quota_verifier.py \
  tests/test_regime_research_autonomy.py
bash tests/test_fog_research_retry_circuit.sh
bash tests/test_research_lock_contention.sh
.venv/bin/python -m pytest -q
git diff --check
```

另需保存：

- red→green commands／outputs
- processed-ID symmetric difference
- circuit state/context before／after hashes
- 3-cycle runtime receipts
- production model／baseline／ranking hashes before／after
- changed-files allowlist 與完整 candidate SHA

## 停損

- 同一 blocker 累計失敗 3 次，第 3 次立即停；不得進第 4 次。
- 無法建立逐 ID red-capable test、需要放寬 statistical/sealed gate、或需要修改
  production paths 時，標記 `BLOCKED` 回主線。
- Candidate 只交付 `DELIVERED_CANDIDATE`；後續必須另開 independent Review，
  Review GO 後才由主線 acceptance／整合。

## Dispatch receipt

- Card commit：`c2ed61956524385779bd9383cb9faa0c5beaa099`
- Provisioning source kind：`commit`
- Provisioning source SHA：`c2ed61956524385779bd9383cb9faa0c5beaa099`
- Source branch：`main`
- Source clean：是
- Git metadata：可用
- `index.lock`：不存在
- unrelated dirty paths：`[]`
- Client receipt：
  `client-new-thread:ea75ef0c-5ab8-467e-a435-70f1725556e3`
- Formal thread：`019fa3ce-33fc-7291-a9f0-a5ca549d0628`
- Thread title：`修復 FOG closed-regime 自動研究鏈`
- Thread status：`active / inProgress`
- Worktree／cwd（local-only）：
  `/Users/mattkuo/.codex/worktrees/35c4/TOP10new`
- Main cwd（local-only）：`/Users/mattkuo/TOP10new`
- Worktree exists：是
- Initial worktree HEAD：`c2ed61956524385779bd9383cb9faa0c5beaa099`
- Initial branch：`detached`（Executor 交付前建立 `codex/` branch）
- Workflow：
  `CARD_DRAFTED → QUEUED → THREAD_CREATED → RUNNING`
- Gate 1 card contract：`PASS`
- Gate 2 visible thread／isolated worktree：`PASS`
- Gate 3 candidate delivery：`PENDING`
- Gate 4 independent Review：`PENDING`
- Gate 5 mainline acceptance：`PENDING`

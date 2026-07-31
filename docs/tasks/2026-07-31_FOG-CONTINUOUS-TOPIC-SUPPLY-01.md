---
id: FOG-CONTINUOUS-TOPIC-SUPPLY-01
status: READY_FOR_INDEPENDENT_REVIEW
type: implementation
ownership: executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: queue ownership、exact-regime eligibility、持續題目補充與 sealed/production 邊界跨越 scheduler、manager 與 research contract，需 strict 契約與獨立審查
chain_id: FOG-CONTINUOUS-RESEARCH-AVAILABILITY
base_sha: 8cff3d0acbe2cea94f198166cc3a9a581b21319a
---

# FOG-CONTINUOUS-TOPIC-SUPPLY-01

## Role

你是本卡 Executor，不是 Reviewer 或 mainline Integrator。

- 在獨立 clean worktree／branch 建立 RED、實作、驗證並產生單一 candidate commit。
- 不得自行宣告 Review GO、整合 `main`、push `main`、deploy 或操作 live scheduler。
- 完成後停在 `READY_FOR_INDEPENDENT_REVIEW`，由主線另開 strict Reviewer。

## Root question

為什麼 scheduler 明明仍有可執行 development 題目，卻回報
`NO_EXECUTABLE_TOPIC`；以及固定 ranking artifact × validation profile 題庫真正
用完時，如何由 repo-owned coverage gaps 持續產生 bounded、可重現、
development-only 的新研究題目？

## Confirmed blocker evidence

2026-07-31 實際 artifact 已確認：

- development registry：125 題；33 題已跑、92 題仍是 `candidate`。
- 當日 exact-regime eligible：42 題。
- 其中 9 題為 `run_count=0`、`manager_status=candidate`，且全部位於
  `next_action_queue`。
- `write_topic_bank(... queued_ids=...)` 會排除 queue 中的題目。
- Fog worker 預設 `TOP10_RESEARCH_FROM_QUEUE=0`，只讀 active bank。
- 結果：queue 有 9 題、active bank 為 0、scheduler 回報
  `NO_EXECUTABLE_TOPIC`。

這是 queue ownership deadlock，不是題目耗盡。

## Requirements and traceability

### FR-ROUTING-01 — 單一可執行題目仲裁

Scheduler 必須以 deterministic queue-first、active-bank fallback 仲裁題目：

- current exact-regime、manager lifecycle 與 cooldown gate 仍是 authority。
- queue 中 actionable 題目不得因同時被 active bank 排除而失去所有執行路徑。
- stale／ineligible／已完成 queue row 不得阻擋 active-bank fallback。
- 同一輪同一 topic 最多選一次。

### FR-SUPPLY-01 — Bounded 題目補充

當 queue 與 active bank 都沒有 executable topic 時，系統必須從 repo-owned
research contract、coverage gaps、既有 ranking artifact inventory 與合法
validation dimensions 產生 deterministic development-only 題目。

- 題目 ID 由 canonical hypothesis tuple 穩定推導。
- 必須對 registry、history、queue 與同輪候選去重。
- 每輪有明確上限；禁止無限 loop、隨機權重與不可重現生成。
- 只允許現有 runner 能執行、且有 exact-regime ranking date 交集的題目。
- 無合法新題時回報穩定 `TOPIC_SUPPLY_EXHAUSTED` 與原因計數，不得假造題目。

### FR-SAFETY-01 — Development-only 安全邊界

題目補充與初篩：

- 只讀 immutable development episodes。
- 排除 validation、embargo 與 sealed episodes。
- 不寫 closed experiment registry。
- 不產生 formal candidate、不 promotion、不改 production ranking/model/weights。
- sealed validation 仍須 fresh sealed episode，且 fail closed。

### SC-01 — 現況 deadlock 解除

fixture 中存在 9 個 current eligible、未跑且已 queued 的題目時，scheduler
至少選出 1 題，不能回報 `NO_EXECUTABLE_TOPIC`。

### SC-02 — Queue fallback

queue 全為 stale／ineligible 時，active bank 有合法題目仍能選出；兩者同時含
同一題時只選一次。

### SC-03 — 題目補充

當兩條既有路徑皆空、但 legal parameter universe 仍有 uncovered executable
combination 時，補充器至少產生 1 個 stable、novel、development-only 題目；
相同輸入重跑不新增重複 ID。

### SC-04 — 真正耗盡可解釋

當不存在任何 legal novel executable hypothesis 時，輸出
`TOPIC_SUPPLY_EXHAUSTED`、候選／排除原因計數與 evidence refs，worker 正常
exit 0，不開 retry circuit。

## Slice plan

### SLICE-ROUTING-RED

- `traces_to`: FR-ROUTING-01, SC-01, SC-02
- frontier：是。
- 先建立會重現「queued actionable > 0 但 selected = 0」的 public behavior
  regression；測試必須先 RED。

### SLICE-ROUTING-GREEN

- `traces_to`: FR-ROUTING-01, SC-01, SC-02
- blocked_by：SLICE-ROUTING-RED。
- 實作 queue-first＋active fallback 與單輪去重，保持 manager gate。

### CHECKPOINT-1

- focused routing tests 全綠。
- 驗證 worker default 與 CLI `--from-queue` 語意一致。

### SLICE-SUPPLY-RED

- `traces_to`: FR-SUPPLY-01, FR-SAFETY-01, SC-03, SC-04
- blocked_by：CHECKPOINT-1。
- 建立「existing routes empty、coverage gap 非零、現況仍無新題」RED。

### SLICE-SUPPLY-GREEN

- `traces_to`: FR-SUPPLY-01, FR-SAFETY-01, SC-03, SC-04
- blocked_by：SLICE-SUPPLY-RED。
- 實作 bounded deterministic topic replenisher、stable ID、四處去重與明確
  exhaustion receipt。

### CHECKPOINT-2

- routing＋supply＋development boundary targeted tests 全綠。
- hostile fixture 證明 sealed／registry／promotion 仍 fail closed。

## Must read

1. `AGENTS.md`
2. `.work/current/status.md`
3. `.work/current/handoff.md`
4. `.work/current/context_manifest.md`
5. 本卡
6. `docs/tasks/2026-07-28_FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01_handoff.md`
7. `docs/tasks/2026-07-27_REGIME-RESEARCH-AUTONOMY-01_closed_regime_parameter_research.md`

## Bootstrap and activation

初始 turn 只做唯讀 preflight：

- 回報 formal thread ID、projectId、cwd、HEAD、branch、clean state。
- 確認 cwd 為獨立 worktree且不等於 main cwd。
- 確認 HEAD 精確等於 dispatch required SHA。
- 未收到與 dispatch key 相符的 activation token 前，禁止改檔、跑測試、
  commit、push 或建立 replacement。

Activation 後先執行：

1. `worktree_capability_preflight.sh --check --root <repo-root>`
2. graph 非 ready 才 `--prepare --with-codegraph`
3. `codegraph_context` 查 selection／manager／worker routing，再由 source 確認。

## Exact changed-file allowlist

- 本卡的 evidence／狀態欄位
- `scripts/run_autonomous_research.py`
- `scripts/run_fog_research_worker.sh`
- `scripts/run_daily_research_quota.sh`
- 可選新增：`scripts/fog_continuous_topic_supply.py`
- `tests/test_autonomous_research_topic_bank.py`
- `tests/test_regime_research_autonomy.py`
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_fog_runtime_time_wiring.sh`
- 可選新增：`tests/test_fog_continuous_topic_supply.py`
- `docs/evidence/FOG-CONTINUOUS-TOPIC-SUPPLY-01/**`
- `.work/FOG-CONTINUOUS-TOPIC-SUPPLY-01/**`

若需要修改 allowlist 外檔案，停止並回報主線修訂卡片。

## Forbidden scope

- production model、ranking code、weights、baseline、promotion state
- `artifacts/market_regime_history.json`
- closed experiment registry、sealed split、validation／embargo artifacts
- installed LaunchAgent plist
- retry state／context／circuit
- live autonomous research artifacts
- `main`、merge、deploy、branch/worktree cleanup

禁止執行：

- `launchctl load/bootstrap/kickstart`
- live Fog `--execute`
- 清除／旋轉 retry circuit
- 修改 production ranking/model/weights
- push `main` 或自行整合

## Verification

至少執行並保存：

- Phase RED receipts：routing、supply 各一個。
- queue-first／active fallback／dedupe hostile tests。
- 9 queued actionable fixture 可選題。
- stale queue 不阻塞 fallback。
- novel deterministic topic supply 與重跑去重。
- true exhaustion receipt 與 exit 0。
- development-only episode boundary hostile tests。
- affected targeted suites。
- full `pytest`。
- shell syntax／`py_compile`（依 changed files）。
- `git diff --check`。
- exact changed-file allowlist audit。
- `rg -n '\\[DBG-'` 無殘留。

證據寫入：

`docs/evidence/FOG-CONTINUOUS-TOPIC-SUPPLY-01/verification.md`

## Candidate exit

只交付：

- base SHA 與 candidate full SHA
- changed files
- RED→GREEN evidence
- targeted／full suite結果
- safety boundary evidence
- 未驗證項目與剩餘風險
- `READY_FOR_INDEPENDENT_REVIEW`

不得自審、整合、push `main`、deploy 或操作 live runtime。

## Executor result

- Routing RED 已重現 9 個 queued actionable topics、active bank 為空時
  `selected_topics=[]`／`NO_EXECUTABLE_TOPIC`。
- Routing GREEN 改為 deterministic queue-first、active-bank fallback 與單輪
  dedupe；worker default 與顯式 `--from-queue` 使用相同仲裁。
- Supply RED 已證明既有流程沒有任何 coverage-gap replenishment 能力。
- Supply GREEN 由 repo-owned contract、exact-regime ranking inventory 與 coverage
  records 產生 bounded、stable-ID、development-only topics，並對 registry、
  history、queue、same-round candidates 去重。
- 真正耗盡時輸出 `TOPIC_SUPPLY_EXHAUSTED`、原因計數與 evidence refs，main
  exit 0；worker 將其視為 terminal no-more-work，不進 retry circuit。
- Targeted：`100 passed`；full：`611 passed, 1 failed, 4 warnings, 246 subtests
  passed`。唯一失敗為獨立 worktree 缺少未版控 research component evidence
  artifacts；相關 builder／verifier／test 相對 base SHA 無 diff。
- Live worker、LaunchAgent、circuit、closed/sealed registry、promotion 與 production
  ranking/model/weights 均未操作。
- Candidate SHA 由本卡單一 commit 完成後以 `git rev-parse HEAD` 取得。
- 狀態：`READY_FOR_INDEPENDENT_REVIEW`。

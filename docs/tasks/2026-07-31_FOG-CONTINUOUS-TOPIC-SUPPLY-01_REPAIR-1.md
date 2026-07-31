---
id: FOG-CONTINUOUS-TOPIC-SUPPLY-01-REPAIR-1
status: ACCEPTED
type: repair
ownership: repairer
thickness: standard
risk: high
model: gpt-5.5
reasoning: medium
model_reason: 三個finding已有高信心重現與明確修復契約，但跨selection、bounded scan及quota verifier三個既有介面，適合standard多檔Repair並由原Reviewer重審
chain_id: FOG-CONTINUOUS-RESEARCH-AVAILABILITY
parent_card_id: FOG-CONTINUOUS-TOPIC-SUPPLY-01
review_card_id: REVIEW-FOG-CONTINUOUS-TOPIC-SUPPLY-01
parent_candidate_sha: 1674e293daeb759888b950be59d8c30d6020e833
review_sha: 21ff2a386f1563fa2be965c2ce20f85ac928df22
repair_generation: 1
---

# FOG-CONTINUOUS-TOPIC-SUPPLY-01-REPAIR-1

## Role

你是本卡 Repairer，不是 Reviewer或 mainline Integrator。

- 只修獨立 Review已開出的三個 finding，不擴大功能。
- 依 RED→GREEN建立可觀察 regression並產生單一 repair candidate commit。
- 完成後停在 `READY_FOR_REREVIEW`，回交原 Reviewer關閉finding。
- 不得自審、整合main、deploy或操作live runtime。

## Fixed review inputs

- Original base：`8cff3d0acbe2cea94f198166cc3a9a581b21319a`
- Parent candidate：`1674e293daeb759888b950be59d8c30d6020e833`
- Independent review：`21ff2a386f1563fa2be965c2ce20f85ac928df22`
- Verdict：`REVIEW_NO_GO`

## Repair requirements

### RR-P1-001 — Preserve non-execute topic-index preview

Closes：`FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P1-001`。

- `execute=false`、`from_queue=false`、single-topic preview必須保留legacy
  `topic_index`語意。
- actionable queue不得覆蓋指定index。
- manager rejected／cooldown不得讓非執行診斷preview消失。
- execute default與explicit queue仍維持queue-first、active fallback與dedupe。
- 必須檢查`main`傳入selection的topic source，確保preview使用既有active-bank
  語意，execute才使用完整current-eligible universe。

### RR-P2-002 — Bound and cache supply scan

Closes：`FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P2-002`。

- ranking eligibility inventory不得在combination × template迴圈重複掃描相同
  candidate／baseline／horizon／as-of。
- 每輪candidate evaluation必須有明確、可測的attempt budget與receipt計數。
- attempt budget未完成完整search時，不得誤報
  `TOPIC_SUPPLY_EXHAUSTED`；使用不同、穩定且fail-safe的outcome。
- hostile fixture：720 legal combinations、3 templates、supply limit 1、
  no-exact-date，eligibility實際呼叫量必須有明確上限，不能是2160次重掃。

### RR-P2-003 — Preserve exhaustion observability

Closes：`FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P2-003`。

- quota verifier不得依賴`from_queue=true`才辨識no-more-work。
- `TOPIC_SUPPLY_EXHAUSTED`必須輸出穩定專用research value status。
- `NO_EXECUTABLE_TOPIC`與真正supply exhaustion的observable reason不得混淆。
- `PARTIAL_NO_MORE_WORK`、failed count 0、exit 0、worker no-retry／no-circuit
  語意保持成立。

## Slice plan

### SLICE-PREVIEW-RED

- `traces_to`: RR-P1-001
- frontier：是。
- 建立non-execute＋actionable queue＋nonzero index及manager-blocked preview
  regression，先證明parent candidate RED。

### SLICE-PREVIEW-GREEN

- `traces_to`: RR-P1-001
- `blocked_by`: SLICE-PREVIEW-RED
- 最小修復preview分支與caller topic source；execute arbitration不得退化。

### CHECKPOINT-1

- preview regressions與原queue-first/fallback/dedupe tests全綠。

### SLICE-SCAN-RED

- `traces_to`: RR-P2-002
- `blocked_by`: CHECKPOINT-1
- 建立multi-template/no-exact-date最壞路徑與attempt receipt RED。

### SLICE-SCAN-GREEN

- `traces_to`: RR-P2-002
- `blocked_by`: SLICE-SCAN-RED
- 加入eligibility cache、attempt budget與不冒充true exhaustion的outcome。

### SLICE-OBSERVABILITY-RED

- `traces_to`: RR-P2-003
- `blocked_by`: SLICE-SCAN-GREEN
- 以新terminal decisions跑quota verifier／worker observable RED。

### SLICE-OBSERVABILITY-GREEN

- `traces_to`: RR-P2-003
- `blocked_by`: SLICE-OBSERVABILITY-RED
- 補齊stable status、exit 0與no-retry語意。

### CHECKPOINT-2

- 三個finding regression全綠，原100個targeted tests不得退化。

## Must read

1. `AGENTS.md`
2. 本卡
3. `docs/tasks/2026-07-31_FOG-CONTINUOUS-TOPIC-SUPPLY-01.md`
4. `docs/tasks/2026-07-31_REVIEW-FOG-CONTINUOUS-TOPIC-SUPPLY-01.md`
5. `docs/evidence/FOG-CONTINUOUS-TOPIC-SUPPLY-01/verification.md`
6. `docs/evidence/FOG-CONTINUOUS-TOPIC-SUPPLY-01/independent_review.md`
7. `.work/FOG-CONTINUOUS-TOPIC-SUPPLY-01/review/review_state.jsonl`

## Exact changed-file allowlist

- 本Repair卡狀態欄位
- `scripts/run_autonomous_research.py`
- `scripts/run_fog_research_worker.sh`
- `scripts/run_daily_research_quota.sh`
- `scripts/verify_daily_research_quota.py`
- `tests/test_autonomous_research_topic_bank.py`
- `tests/test_fog_continuous_topic_supply.py`
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_fog_runtime_time_wiring.sh`
- `docs/evidence/FOG-CONTINUOUS-TOPIC-SUPPLY-01/repair_1.md`
- `.work/FOG-CONTINUOUS-TOPIC-SUPPLY-01/repair-1/**`

需要allowlist外檔案時停止並回報主線，不得自行擴張。

## Forbidden

- 改寫或關閉Reviewer findings／independent review evidence
- 新增與三個finding無關的topic功能
- closed experiment registry、sealed split、validation／embargo artifacts
- production ranking/model/weights、promotion、regime history
- live worker、LaunchAgent、retry circuit
- merge／rebase main、push main、deploy、cleanup任何thread／branch／worktree

## Verification

至少保存：

- 三組Phase RED receipts。
- RR-P1三個preview regressions與既有queue arbitration tests。
- RR-P2 multi-template hostile call bound、cache與budget receipt tests。
- RR-P2 terminal verifier／worker observable tests。
- affected targeted suites。
- full pytest；若仍只有已知artifact缺失，需重新保存完整disposition，不得宣稱
  full green。
- shell syntax、runtime wiring、`py_compile`。
- `git diff --check`、allowlist audit、`rg -n '\\[DBG-'`。

Evidence：

`docs/evidence/FOG-CONTINUOUS-TOPIC-SUPPLY-01/repair_1.md`

## Exit

只交付：

- repair base與candidate full SHA
- finding ID → regression → fix對照
- RED→GREEN、targeted／full suite結果
- changed files與allowlist audit
- remaining risks
- `READY_FOR_REREVIEW`

不得自審、關閉finding、整合main、deploy或操作live runtime。

## Mainline closure

- Repair candidate：
  `d166fa1483d2ca2288cda50ea204631cd8b0b972`
- 原Reviewer重審：`REVIEW_GO`
- P1-001、P2-003：resolved
- P2-002：nonblocking backlog
- Mainline full：`617 passed, 4 warnings, 246 subtests passed`
- 自然排程runtime acceptance：PASS

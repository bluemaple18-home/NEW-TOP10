---
id: FOG-TOPIC-SUPPLY-BUDGET-STATUS-01
status: BACKLOG_READY
type: maintenance
ownership: executor
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
parent_card_id: FOG-CONTINUOUS-TOPIC-SUPPLY-01
source_finding_id: FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P2-002
---

# FOG-TOPIC-SUPPLY-BUDGET-STATUS-01

## Goal

完整傳遞 `TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED`，避免罕見的
budget-incomplete search被降成確定的 `NO_EXECUTABLE_TOPIC`。

## Scope

- `scripts/run_autonomous_research.py`保留top-level budget-incomplete decision。
- quota verifier輸出專用、非no-more-work狀態。
- worker不得把budget-incomplete視為true exhaustion terminal。
- 補main → verifier → worker observable regression。

## Boundary

- 不重做本次已接受的queue-first、topic supply或exact-regime邏輯。
- 不操作live worker、LaunchAgent、retry circuit、promotion、production ranking
  或model。
- 本卡為非阻塞 P2 backlog；不得回溯否定
  `FOG-CONTINUOUS-TOPIC-SUPPLY-01` 的 mainline runtime acceptance。

## Acceptance

- budget-incomplete不映射為`NO_EXECUTABLE_TOPIC`。
- verifier與worker皆不宣稱no-more-work。
- true `TOPIC_SUPPLY_EXHAUSTED`仍保持terminal、exit 0、no retry。
- affected tests、full suite、shell wiring與`git diff --check`通過。

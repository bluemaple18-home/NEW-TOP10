---
id: FOG-TOPIC-SUPPLY-BUDGET-STATUS-01-GOAL
status: ACCEPTED
type: mainline
---

# Goal

當topic supply在單輪內達到attempt budget，但尚未證明真正耗盡時，完整保留
`TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED`，使verifier與worker把它視為
exit 0、可重試、非no-more-work，下一個bounded batch可以繼續。

true exhaustion與一般no-executable語意維持不變。

---
id: FOG-TOPIC-SUPPLY-BUDGET-STATUS-01-BRIEF
status: ACCEPTED_MAINLINE_RUNTIME
type: mainline
---

# Brief

修正先前P2：main會把罕見的attempt-budget incomplete receipt降成
`NO_EXECUTABLE_TOPIC`，verifier再標成`PARTIAL_NO_MORE_WORK`，使worker
提早停止。

現在main保留decision，verifier輸出`PARTIAL_RETRYABLE_TOPIC_SUPPLY`，
worker會繼續下一bounded batch。獨立Review為`REVIEW_GO`，自然排程已完成
一題且LaunchAgent exit 0。

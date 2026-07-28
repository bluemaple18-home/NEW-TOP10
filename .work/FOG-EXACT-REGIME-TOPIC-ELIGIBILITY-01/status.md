---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-STATUS
status: READY_FOR_INDEPENDENT_REVIEW
type: candidate
---

# Candidate status

## Root question

Closed-regime scheduler為何仍會選到沒有 exact-match regime ranking日期的
strategy-matrix topic？

## Root cause

Topic generation只把 ranking file count、current regime identity與 coverage
納入 eligibility，沒有檢查 candidate/baseline inventory與 canonical
development episode dates的交集。上游誤標為 `ELIGIBLE` 後，index、fallback、
queue都會信任該值。

## Current state

- Dispatch SHA：`d565fdd932576505ee9612954e5c4f8c52c24d7d`
- Implementation candidate SHA：`3969aba5c62171ef52d5c54856f0c0821b750627`
- Targeted：`86 passed`
- Full：`585 passed, 4 warnings, 246 subtests passed`
- `py_compile`：PASS
- `git diff --check`：PASS
- LaunchAgent：unloaded
- Retry circuit：`attempts=3`、`circuit_open=1`

## Next step

由獨立 Reviewer檢查完整 `33aee4d..candidate`；Executor不自審、不整合。

## Waiting conditions

等待 strict independent Review結果。Review GO並整合後，I5線才可另行判斷
是否恢復 circuit與 scheduler acceptance。

## Limits

禁止第四次 live probe、LaunchAgent load/kickstart、circuit recovery、production
model/ranking/weights/baseline/promotion變更，以及任何 main整合。

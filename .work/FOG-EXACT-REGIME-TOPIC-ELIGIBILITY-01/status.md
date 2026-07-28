---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-STATUS
status: GO_LOCAL_DETERMINISTIC
type: mainline
---

# Mainline status

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
- Repair candidate SHA：`51c084cd077cd4e997873e4a924f73e3dca2ba3d`
- Review GO SHA：`0b1373bdea3d02b6a92c07a121f664949e4f48f2`
- Local integration SHA：`374792652b8bee8a869052228da78f7a0d4558b4`
- Targeted：`88 passed`
- Full：`587 passed, 4 warnings, 246 subtests passed`
- `py_compile`：PASS
- `git diff --check`：PASS
- LaunchAgent：unloaded
- Retry circuit：`attempts=3`、`circuit_open=1`

## Mainline result

- Initial Review：`REVIEW_NO_GO`
- Repair-1：`51c084cd077cd4e997873e4a924f73e3dca2ba3d`
- Targeted re-review：`REVIEW_GO`
- Local integration：`374792652b8bee8a869052228da78f7a0d4558b4`
- Main checkout hostile probes：`16/16`與`7/7`
- Targeted：`88 passed`
- Full suite：`587 passed`

## Waiting conditions

等待是否 push／開 PR的明確授權。I5恢復 circuit與 scheduler acceptance仍是
獨立 live決策，不包含在本 deterministic acceptance。

## Limits

禁止第四次 live probe、LaunchAgent load/kickstart、circuit recovery、production
model/ranking/weights/baseline/promotion變更，以及未授權的 push／deploy。

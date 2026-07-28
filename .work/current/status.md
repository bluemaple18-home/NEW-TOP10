---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-STATUS
status: REPAIR_RUNNING
type: mainline
---

# Current Status

## Root question

Closed-regime scheduler為何仍會選到沒有 exact-match regime ranking 日期的
strategy-matrix topic？

## Blocker

Independent Review以 hostile probe重現 P1：
repo內 `ranking_YYYY-MM-DD.csv`若為指向 repo外 regular file的 symlink，
eligibility仍回 `ELIGIBLE`，matrix並會讀到外部內容。

## Fork

無。正式 canary mode只保留為候選方案；本卡先修正已被證明的 eligibility
缺口，不另外擴卡。

## Current state

- Main base：`33aee4d`
- Source-lineage candidate：`be9bb74`
- Stacked parent／evidence tip：`5e6c0385fc8d93a89561583c79981d273c44fde6`
- Source-lineage targeted：`69 passed`
- Full suite：`576 passed, 4 warnings, 246 subtests passed`
- I5：`NO_GO`
- LaunchAgent：unloaded
- Circuit：open
- Live retry budget：已達三次上限
- Candidate：`684d3adf3916100a7eb9bb57c6164f3b67a58064`
- Independent Review：`REVIEW_NO_GO`
- Review commit：`e50022a9db130832d9855846d12168a79d454cef`
- Blocking finding：`FOG-EXACT-REGIME-REVIEW-P1-001`

## Next step

由獨立 Repair Executor依
`docs/tasks/2026-07-28_FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01_REPAIR-1_symlink_authority.md`
先建立 file-level symlink RED，再關閉 P1並停在 `READY_FOR_REVIEW`。

## Waiting condition

Repair-1正式 task `019fa778-8623-70b1-840d-a542a9a2e46d`執行中；
candidate完成後交回原 Reviewer task做 targeted re-review。

## Restrictions

不准第四次 live probe、不准重啟 LaunchAgent、不准清 circuit、不准修改
production model／ranking／weights／baseline／promotion。

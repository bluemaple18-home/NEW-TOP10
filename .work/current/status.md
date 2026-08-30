---
id: ISSUE-10-WEEKDAY-SCHEDULER-CLOSEOUT-status
status: COMPLETE
type: mainline
---

# Current Status

- Root question 已完成；`main/origin/main=0dd74e7d620fa26527f65218ecd4ce1e32c92d8b`。
- Commits：`005c70d` weekday-only plist；`0dd74e7` reject ambiguous Day/Month keys。
- `tests/test_scheduler_ownership.py`：11 passed；`plutil` OK。
- Storage measure PASS：`free_bytes=39115104256`；installed daily plist matches repo。
- launchd：enabled、loaded、not running、`runs=0`、`never exited`；exact Weekday 1..5 at 17:30。
- 2026-08-30 Sunday：no run、no send；next natural run：2026-08-31 17:30。

---
id: FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01-status
status: CARD_DRAFTED
type: task_status
---

# Root question

如何讓default-v2 replay正確終結queue，且任何零進度batch不再重播？

# Current state

- RED-capable artifact diagnostic：exit 1。
- 根因候選已定位於history canonicalization與drain progress invariant。
- 主worktree有兩個overlap dirty files，實作必須使用獨立clean worktree。
- Runtime：LaunchAgent未載入；容量閘門`NO-GO`，本卡禁止啟用。

# Frontier

`SLICE-RED`

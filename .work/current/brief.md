---
id: FOG-CONTINUOUS-TOPIC-SUPPLY-01-BRIEF
status: ACCEPTED
type: mainline
---

# Brief

Fog scheduler存在 queue ownership deadlock：目前有 9 題 exact-regime eligible、
尚未執行且已排入 next-action queue，但 active topic bank會排除 queued topic，
worker又預設不從 queue取題，因而回報 `NO_EXECUTABLE_TOPIC`。

本卡先修 deterministic queue-first／active fallback，再補上有界、可重現且只限
development範圍的持續產題機制。

自然排程已由0題空轉改為選出並完成1個development topic；主卡已接受。

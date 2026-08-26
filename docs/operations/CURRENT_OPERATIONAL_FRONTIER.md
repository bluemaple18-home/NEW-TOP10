# NEW-TOP10 Current Operational Frontier

更新：2026-08-27

狀態：`P0 DAILY PUBLISH RECOVERY`

目前唯一 operational frontier：

- `#9 INCIDENT-NEW-TOP10-DAILY-PUBLISH-RECOVERY-AND-HARDENING-V1`

Research Spine：

- `#2 A0 Precheck and Prior Art` 暫停派工，等待 #9 完成 immediate recovery 與 no-regression gate。
- `#3–#8` 維持 blocked。

Authority：

1. GitHub Issue #9 的 scope / acceptance。
2. `docs/operations/DAILY_PUBLISH_INCIDENT_20260827.md` 的 confirmed repo risks。
3. `docs/RESEARCH_SPINE_BACKLOG.md` 在 #9 close 後恢復 A0-only frontier。

Operational incident 可以修 scheduler、runtime path、publish boundary、health/status 與通知 adapter；不得順手修改 ranking math、模型、backtest、Research Spine identity 或 Card B/C。

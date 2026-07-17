---
id: ARCH-UPGRADE-03
status: ready_for_review
type: context_manifest
---

# Context manifest

- Parent candidate：`a74f931`
- Allowed paths：Daily V2 parity module/CLI/tests/docs、control-plane verification mapping、本 workspace。
- Do not touch：production entrypoint、launchd、notification、ranking weights、model。
- Local-only evidence inputs：`artifacts/automation_status.json` 與 `artifacts/shadow/daily_v2/`；跨機重現以 focused tests 為準。

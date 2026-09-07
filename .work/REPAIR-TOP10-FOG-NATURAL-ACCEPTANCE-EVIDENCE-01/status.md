---
id: REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01
status: candidate-green-deploy-blocked
type: status
---

# Status

root question：Fog 是否能以 exact invocation artifact 與 archive cadence 完成 fail-closed natural acceptance？

blocker：worker artifact 尚未與 Storage Guard receipt 綁定；PPID=1 不是 natural origin proof。

fork：若現有 plist＋archive cadence 無法形成 deterministic verifier，停回 Mainline，不自行新增 scheduler authority/ledger。

目前狀態：`CANDIDATE_GREEN / DEPLOY_BLOCKED_BY_RESTART_DENIAL / NATURAL_ACCEPTANCE_PENDING`。

已完成：單一 Worker 實作、Repair 1、兩名獨立盲審重驗與 Mainline 本機 acceptance。

Owner 已授權 commit／deploy；Mainline 可提交本地修補。但 production preflight 發現既有 Fog marker：invocation `fog-research-worker-20260907T090500Z-80610` 因 `REGISTERED_WRITE_OUTSIDE_METER` 停止，child exit `143`、final process group quiescent。由於本卡明確禁止清 marker，activation 不得執行。

下一步：另開 bounded root-cause card 處理 Fog 與 17:40 external-review-preflight 的 cross-job write attribution／隔離；證據完成並取得明確 marker-clear authority 後，才可重跑 deployment preflight。

限制：不 kickstart、不清 marker、不 deploy、不 push、不回填舊 receipt、不碰 ME-D1。

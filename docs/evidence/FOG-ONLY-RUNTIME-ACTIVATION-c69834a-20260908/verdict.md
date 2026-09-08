# Fog-only runtime activation verdict

日期：2026-09-08（Asia/Taipei）

狀態：`DEPLOYED / NATURAL_ACCEPTANCE_PENDING`

## Fixed identity

- Source／runtime commit：`c69834ae85f7cdc57761f35ce29eca129b420e98`
- Detached runtime：`/Users/mattkuo/TOP10-runtime-automation-c69834a`
- Previous runtime：`/Users/mattkuo/TOP10-runtime-automation-bb55fc4`
- Production target：`com.new-top10.fog-research-worker`
- Activation entrypoint：`scripts/activate_automation_runtime.py --job fog-research-worker --activate`

## External write

- GitHub：`origin/main` 已由 `89bcb5c` fast-forward 至 `c69834a`。
- Operation level：`write_action`。
- Owner confirmation：已明確授權 `push + Fog-only production deployment`。

## Preflight gates

- Runtime validator：`RUNTIME_CHECKOUT_GO`；同一 canonical repo、detached HEAD、exact commit。
- Runtime dependency：`uv sync --frozen` 完成。
- Mutable state：只以 `--ignore-existing` 合併 previous runtime 的 `data/artifacts/models`；未複製 `logs`、lock 或 denial marker。
- Fog storage measure：`PASS`；project bytes=`1,351,922,700`、files=`13,463`、host free=`38,169,714,688`、memory pressure=`2`。
- Candidate runtime affected suite：`218 passed, 38 subtests passed`。
- 代表性 workload：`c757cf2` 的兩個完整週期均 `OK`；`c757cf2..c69834a` 未修改 Fog workload，只新增 activation selector、測試與 evidence。
- Activation failure-state review：兩名 blind reviewer re-review 均 `GO`，無 P0/P1/P2。

## Activation result

- CLI exit：`0`。
- Receipt：`activation.json`；SHA-256=`3ea89f9d920ce4bf3ed8c535971099fca8bffa2e12a8eca2dc484ccdcc7ad572`。
- Receipt status：`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`；failure=`null`；signal count=`0`；rollback／mask restore errors 均為空。
- Receipt `target_labels` 與 `jobs` 只含 Fog。
- Fog plist SHA-256：`455d31a77173f2f09635349ca56ce4c0bc276c8e73954520c7247102fd994d61`。
- Postcheck：Fog loaded、not running、run interval 3600 秒，ProgramArguments 全部指向新 runtime。
- Nonblocking acquisition 證明 Fog storage lock 已釋放。

## Out-of-scope invariants

- daily plist SHA-256 維持 `17b9f9fb601ec7c58aa68e9b276515d1d5af907812f82900953cdf265d14176a`。
- external-review-preflight plist SHA-256 維持 `6460bf33924aad1d2b74140c3ff58a17f2a17b358670ca859eb2445db10c4fc3`。
- daily 與 external-review-preflight 仍 loaded、not running，ProgramArguments 仍指向 previous runtime `bb55fc4`。
- Previous runtime Fog marker SHA-256 在 activation 前後皆為 `b3453cbba53bdb5fd73f230114ba2f0c82f7968e9b87fe18a68b585b7edc02e9`。
- 新 runtime Fog marker absent。
- 未執行 manual run、kickstart 或其他 job activation。

## Remaining acceptance

部署只完成安全切換，不代表 Fog natural acceptance。必須等待新 runtime 的兩個自然週期同時通過 invocation-bound artifact、cadence provenance、artifact date、child exit、process-group quiescence、marker／lock absence與連續計數，才可宣告 `ACCEPTED`。既有 `top10-fog` heartbeat 本輪未建立、未恢復；由原監控對話依既有安排觀察。

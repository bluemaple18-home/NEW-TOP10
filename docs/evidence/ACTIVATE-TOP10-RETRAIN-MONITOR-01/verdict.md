# Retrain monitor production activation verdict

日期：2026-09-11（Asia/Taipei）

狀態：`DEPLOYED / NATURAL_ACCEPTANCE_PENDING`

## Fixed identity

- Activation commit：`8fe93667e2673a366239aa84b36f481fba79d89e`
- Detached runtime：`/Users/mattkuo/TOP10-runtime-automation-8fe9366`
- 唯一 target：`com.new-top10.retrain`
- 唯一 command：`/bin/bash <runtime>/scripts/run_with_storage_guard.sh retrain-monitor /bin/bash <runtime>/scripts/daily_retrain.sh monitor --trigger scheduled`
- Schedule：每日 02:00；`RunAtLoad=false`。

## Failure and repair lineage

- 第一次 production precheck：`PRECHECK_FAILED`；installed legacy direct plist 無 storage identity，未發生 mutation。Receipt：`activation.json`，SHA-256=`3f57b20cde42298e93ec7552286466d61c7d8cef467764ee42bf01671f991158`。
- Repair 2 `64402be`：兩名 Reviewer 均因 generic identity fallback 的 namespace bypass 判定 `NO-GO`。
- Repair 3 `8fe9366`：retrain label 只接受兩個 exact prestate argv；wrong／unknown／path-like identity與 child drift 全部 fail closed。兩名原 Reviewer re-review 均 `GO`。

## Validation

- Fixed runtime activation suite：`95 passed`。
- Fixed runtime storage suite：`100 passed, 39 subtests passed`。
- retrain-monitor capacity measure：`PASS`；host free=`26,373,304,320`、project bytes=`3,241,729,137`、project files=`30,962`、memory pressure=`2`。
- Runtime HEAD detached、tracked tree clean；locked dependencies 105 packages audited。

## Activation result

- CLI exit：`0`。
- Receipt：`activation-repair3.json`；SHA-256=`daf37ead100ddab135f9a580619931c26c9875cea78ae0283407e32a71a955d7`。
- Receipt status：`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`；failure=`null`；rollback／mask restore errors 均為空。
- Receipt target 與 jobs 只含 `com.new-top10.retrain`／`retrain-monitor`。
- Installed plist SHA-256：`f924c257846a152783e4d6396d22baa23094e7acfadd6150b50fecc658f90871`。
- Postcheck：enabled、loaded、not running、runs=`0`，calendar event為 02:00，ProgramArguments 全部指向 fixed runtime。
- 新 runtime denial marker absent；`retrain-monitor.lock` nonblocking acquisition 成功，證明 transaction lock 已釋放。
- `activation-repair3.prestate/com.new-top10.retrain.plist` 是 transaction 保存的舊 installed plist exact bytes；其中 5 個 whitespace-only lines 原樣保留，檔案 SHA-256 仍精確等於 receipt 的 `old_sha256`。因此格式檢查只對此 immutable raw snapshot 作明示排除；其餘 delivery diff 全數通過 `git diff --check`。

## Out-of-scope invariants

- baseline-harness=`028bad4857e71a36080b3b382724b4516d50c9d8f2a0e9fb669f703078cb30ed`
- daily=`17b9f9fb601ec7c58aa68e9b276515d1d5af907812f82900953cdf265d14176a`
- external-review-preflight=`6460bf33924aad1d2b74140c3ff58a17f2a17b358670ca859eb2445db10c4fc3`
- external-review=`ac9f7357fee7d11853c60d7081241f94cd5ced5dcf19ed643de87f6f2fe2d48e`
- Fog=`455d31a77173f2f09635349ca56ce4c0bc276c8e73954520c7247102fd994d61`
- pm-research-harness=`3a5473313bb6bfbcacc0f76cdde8b09a127e99a3d82dd7e507d618b384d25499`
- reference=`6f1d7bf81db236e03a288467c10de45b515ad7bf3e0a7a5e027e1a6bd2b3527e`
- 所有 out-of-scope plist hash 與 transaction prestate 相同；未執行 Fog 或其他 job mutation。

## Remaining acceptance

- 2026-09-11 查核時 launchd：enabled／loaded／not running，`runs=3`、`last exit code=0`；installed plist SHA-256 仍為 `f924c257846a152783e4d6396d22baa23094e7acfadd6150b50fecc658f90871`，runtime 當下仍為 detached clean `8fe93667e2673a366239aa84b36f481fba79d89e`。
- 2026-09-09、10、11 三份 post-activation receipt 都在 02:00 後 `4s / 1s / 2s` 出現，均 `status=OK`、child exit `0`、terminal process group quiescent；目前 retrain-monitor restart-denied marker absent。這證明成功執行，不足以單獨證明 calendar natural fire。
- 獨立 review 找到三項 P1：目前觀測無法區分 02:00 附近的 `kickstart`；archive/latest 同步改寫時沒有獨立 digest anchor；驗收當下的 loaded plist/runtime identity 無法證明三輪期間的歷史 identity continuity。另有一項 P2：launchd unload/reload 或 login generation 變更可能重置 `runs`，aggregate count 不能當永久累積證據。
- 因此先前本機產生的 natural-acceptance verifier 與 `ACCEPTED` evidence 已撤回，不作 canonical evidence。後續 acceptance 需要每輪由 runtime receipt tree 之外的 observer 保存可區分 calendar fire / kickstart 的 cadence provenance，並綁定 loaded job identity、service generation、runtime SHA 與 receipt digest。
- 三輪 workload 的 model health report 為 `WARN`，包含 factor monitor warning／industry momentum monitor reject；這些是模型監控觀察，不授權模型重訓或 promotion。

本卡維持 `NATURAL_ACCEPTANCE_PENDING`。後續仍不得以本卡 authority 執行 manual run、`kickstart`、模型重訓、其他 job activation、marker 清除或 runtime 切換。

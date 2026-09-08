# Retrain monitor production activation verdict

日期：2026-09-08（Asia/Taipei）

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

目前 runs=`0` 是部署後尚未到下一個 02:00 的預期狀態，不等於自然週期已通過。不得 manual run 或 `kickstart`；下一步只讀驗證首次自然 invocation、monitor terminal result、storage receipt、marker／lock狀態，再依既有 acceptance contract累積自然週期證據。

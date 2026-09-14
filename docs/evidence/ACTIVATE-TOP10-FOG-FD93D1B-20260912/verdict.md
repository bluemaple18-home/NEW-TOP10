# Fog-only fd93d1b activation verdict

日期：2026-09-12（Asia/Taipei）

狀態：`DEPLOYED / NATURAL_ACCEPTANCE_PENDING`

## Identity 與範圍

- runtime：`/Users/mattkuo/TOP10-runtime-automation-fd93d1b`
- commit：`fd93d1b4e2438fa3878b22e3c4f0facfed988aa2`
- target：`com.new-top10.fog-research-worker`
- previous runtime：`/Users/mattkuo/TOP10-runtime-automation-c69834a`
- Owner 已明確授權 Fog-only activation；未授權 push，且本輪未 push。

## Preflight

- runtime checkout：`RUNTIME_CHECKOUT_GO`，detached exact commit。
- host capacity：`PASS`；project bytes `1,351,926,356`、files `13,464`、host free `58,489,454,592`、memory pressure level `1`。
- 代表性驗證：兩週期皆 `OK`，summary verdict `PASS_CANDIDATE`。
- affected suite：`111 passed, 39 subtests passed`。
- activation transaction suite：`95 passed`。
- activation entrypoint SHA-256 與已取得兩名 Reviewer `GO/GO` 的 `8fe9366` 版本相同；`fd93d1b` 只改 Fog sampling headroom 與直接測試。
- Rule 25 不適用：本卡未建立 production canary，也未執行 create/publish/transaction/tag/push chain。

## Activation 結果

- receipt：`activation.json`
- receipt status：`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`
- failure：`null`
- rollback errors／mask restore errors：空
- signal count：`0`
- installed Fog plist SHA-256：`2f00f23d172baa6491f83c1675f2dec9dad6a1df5a82e32b656c814ee294e4f2`
- launchd：enabled、loaded、not running、run interval `3600` 秒、`runs=0`、last exit `(never exited)`；ProgramArguments 全部指向 `fd93d1b`。
- 新 runtime denial marker absent；舊 runtime denial marker SHA-256 保持 `11e0ba0ddc59dcecaeafba84cb0a3c4caf52824390ba22c57c3c1693c4e56cc5`。
- Fog storage lock nonblocking acquisition：`FOG_STORAGE_LOCK_RELEASED`。

## Out-of-scope invariants

- daily plist：`17b9f9fb601ec7c58aa68e9b276515d1d5af907812f82900953cdf265d14176a`
- external-review-preflight plist：`6460bf33924aad1d2b74140c3ff58a17f2a17b358670ca859eb2445db10c4fc3`
- retrain plist：`f924c257846a152783e4d6396d22baa23094e7acfadd6150b50fecc658f90871`
- 未 manual run、未 kickstart、未修改其他 job、未執行 model retraining。

## Remaining acceptance

此結果只證明安全 activation，不代表自然排程 acceptance。須等待 `fd93d1b` 的自然 StartInterval 週期，驗證 invocation-bound receipt、child exit、process-group quiescence、denial marker absent、lock released 與連續自然週期計數後，才可宣告 Fog `ACCEPTED`。

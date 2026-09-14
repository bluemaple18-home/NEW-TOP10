# Fog-only 67f2d28 activation verdict

日期：2026-09-14（Asia/Taipei）

狀態：`DEPLOYED / NATURAL_ACCEPTANCE_PENDING`

## Fixed identity

- commit：`67f2d28c9825973eac1beb62d40b7d20c6304d47`
- runtime：`/Users/mattkuo/TOP10-runtime-automation-67f2d28`
- previous runtime：`/Users/mattkuo/TOP10-runtime-automation-fd93d1b`
- target：`com.new-top10.fog-research-worker`

## Preactivation evidence

- affected/activation suite：`207 passed, 39 subtests passed`；resource-budget shell、compile與 diff check 通過。
- exact commit 兩輪代表性驗證：兩輪 guard/child exit 皆 `0`、status `OK`、process group quiescent、無 unknown writes；verdict `PASS_CANDIDATE`。
- fresh capacity：`PASS`；project `1,446,722,989 bytes`／`13,313 files`、host free `50,265,235,456 bytes`、memory pressure `2`。
- activation entrypoint SHA-256 `65860b2f5d02557b91a26b76a6385705864e7eb0b1f3a0f75fc13c953547fdea`，與既有雙 Reviewer `GO/GO` 的 `8fe9366` 版本相同。
- Rule 25 不適用：本次不建立 canary，不執行 publish/tag/push。

## Activation result

- 首次 receipt `activation.json`：`PRECHECK_FAILED`；原因是從 candidate cwd 呼叫，`source_root` 與 runtime 相同。events 空、canonical commit 為空，證明在 mutation 前拒絕；production plist與 old marker hash未變。
- authoritative success receipt：`activation-retry1.json`；CLI exit `0`，status `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`，failure `null`，rollback／mask restore errors皆空，signal count `0`。程序 exit `0` 完成 signal teardown attestation。
- postcheck：Fog loaded、not running、StartInterval `3600`、runs `0`、last exit `(never exited)`，ProgramArguments 全部指向 `67f2d28`。
- old denial marker SHA-256 維持 `84b73c62ac203891c613c37f62139aba37aa09008552e7c49df35efa5625de68`；new runtime marker absent；old/new storage locks均可非阻塞取得。
- out-of-scope plist hashes與 receipt prestate相同；daily、external-review、external-review-preflight、retrain皆未修改或啟動。
- 未 manual run、未 `kickstart`、未 push。

## Remaining acceptance

目前只完成安全 activation。須等待 `67f2d28` 的自然 StartInterval 週期，依 invocation-bound receipt、child exit、process-group quiescence、denial/lock absence與連續自然週期計數驗收；在此之前不得宣告 Fog `ACCEPTED`。

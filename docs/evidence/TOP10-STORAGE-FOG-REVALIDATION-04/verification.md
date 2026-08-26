# TOP10-STORAGE-FOG-REVALIDATION-04｜Verification

## 收卡狀態

`READY_FOR_REVIEW / FOG_NO_GO_SWAP_GROWTH_BUDGET_EXCEEDED`

Cycle 1 在代表性 batch 1 中由 guard reason-coded 停止；workload 未完整完成，依 strict 契約
禁止 retry 且 cycle 2 未執行。Fresh restart denial 保留，production `launch_verified=false`，
八個 launchd labels 維持 disabled／not loaded。

## Root question 判定

`fog-research-worker` 無法在固定 swap ceiling 內完成第一個代表性週期，因此不能支持兩週期
`PASS_CANDIDATE`。Raw guard 的唯一 stop reason 是 `SWAP_GROWTH_BUDGET_EXCEEDED`；post-run
重算另確認 live sampler cadence contract 失敗。這兩項都不改變 trusted runner、Seatbelt、write
scope、bytes/files、RSS 或 host reserve 的既有證據，也不能被解讀為可重跑。

## Fresh trusted execution

- reviewed source：`001e2dbe7f3a5743a3542c2a36680a3fac8a9fc9`。
- fresh marker／contract／entrypoint／runner digest：
  - marker：`9fbe2790dd164b6f4d6484c1a4452c92cea5faa79a1ed6b0b2426d0b4b1bb968`
  - contract：`d010144130c0cac4f6dca0155d172147977b8b2c6e227105b743874e87f9b0b8`
  - entrypoint：`661b9a1b10dc8f932eb7c99afa7502cea34f416c07758ccb8cbe8615494427cd`
  - runner：`2780a484e51950b2a6c30089d16111051f5bb3db71fe14e4be74d71923c8ae17`
- sandbox 無 `.git`、symlink、bind mount或 source-tree bytecode；exact `/dev/null`、scope outside、
  hostile environment、runner bytes、`$0`／cwd與 meter invariant probes 全部通過。
- `unknown_changed_paths=[]`；`registered_unmetered_changed_paths=[]`；fresh digests 與前代只讀
  marker／restart denial digests在 cycle 後都不變。

## Cycle 1 runtime evidence

Guard：

- status：`STOPPED`
- guard exit：`70`
- child exit：`0`；不得解讀為 validation PASS
- stop reason：`SWAP_GROWTH_BUDGET_EXCEEDED`
- elapsed：`125.67089915275574` seconds
- live samples：`3`；全部有有效 RSS 與 swap
- peak process-tree RSS：`1085718528` bytes，低於 `4294967296`
- swap delta：`2964848640` bytes，高於固定 `2147483648` ceiling
- project：`711514382` → `625251267` bytes，未超過 `2147483648`
- file count：`13886` → `7944`，未超過 `30000`
- host free delta：`-2053648384` bytes；final receipt 為 `39276392448` bytes，仍高於
  runtime reserve `24510719590.4` bytes
- observed project growth：`0.0` bytes/hour
- initial allowlisted reclaim：`151684204` bytes／`5964` files；removed-path list digest
  `36d32d036203a7fc6f3ea74a8650ec05b57ccbbb0c1b5f2a033ae5ed13eb48dd`
- target PGID `36672` post-guard member count `0`；target process scan無殘留，沒有 TOP10
  open-deleted file。

Fresh restart denial：

- `automatic_clear_allowed=false`
- reason：`SWAP_GROWTH_BUDGET_EXCEEDED`
- denial digest：`5d926ebd12a574b30a287f6940fc250bf218f85c932db6e0d8d8bc2b263dd557`

Bounded machine receipt：`cycle-1.json`，`5363` bytes，SHA-256
`4341084c5d42e96d7564eccf1e202584259a83eaa8a0e1924413b676dbf72694`。
Raw local-only evidence 保留於 fresh sandbox，未提交：

- guard receipt：`1049535` bytes，
  `8addb6729eddf0cca4efccd303c2c81daa951878ce3cc6c746d810a5891c7781`
- guard log：`963` bytes，
  `1c69cd8a85b40ba1bd2fe25a766bad398a0fe7f724d4029c237eb4dec4e92082`
- restart denial：`180` bytes，
  `5d926ebd12a574b30a287f6940fc250bf218f85c932db6e0d8d8bc2b263dd557`

## Post-run cadence finding

Committed 三筆 live sample timestamps 的兩段 gap 精確重算為 `60.485444` 與
`61.7187129` 秒，最大值 `61.7187129` 秒，均超過固定 `60` 秒 ceiling。因此另記
`LIVE_SAMPLE_CADENCE_EXCEEDED`；這是 bounded evidence 的 post-run finding，不是改寫 raw guard
receipt 或 restart denial 的 reason。Raw `reasons=[SWAP_GROWTH_BUDGET_EXCEEDED]` 仍精確保留。

本次監控契約亦判定失敗。Cycle 2、retry 與任何 fresh workload 均禁止；必須先通過本 Repair 的
targeted Review，且由主線另行取得新的 fresh activation，才可能重跑。

## Cycle 2 與 retry

Cycle 1 receipt 非 `OK` 且 `representative_complete=false`；因此
`cycle_2_authorized=false`、`retry_authorized=false`。沒有建立 `cycle-2.json`、沒有再次執行
trusted entrypoint，也沒有清除或修改 fresh output／denial。

## Protected／production 收尾

- `<main-checkout>` dirty path 集合仍為前代三檔，三個 SHA-256 與 preflight 完全相同。
- `<previous-sandbox>` marker digest仍為
  `6c0af0aa838fea1e65524cd87f17f9ace19293ee4d84f3ea3dd3b29ec65d058e`，restart denial
  digest仍為 `eea4c1027f1b944b96ffba9c9ee7abcedaacb81fedaf35d10919d17409ea91bb`。
- fresh marker、contract、entrypoint與runner digest cycle 後不變；sandbox symlink／`.git`／
  source-tree pycache 均為 `0`。
- 八個 live launchd labels全部 `disabled`、`NOT_LOADED`；其他七個 job未執行或修改。
- 未碰 production data/artifacts/models、browser/provider/其他專案；未 merge、push、deploy。

## Tests 與 checks

Reviewed affected suites（preflight在 worktree與fresh sandbox各一次；收尾再一次）：

```text
46 passed, 16 subtests passed
```

Full suite：

```text
1 failed, 679 passed, 4 warnings, 270 subtests passed in 87.98s
```

唯一 failure 是前代已記錄且本卡未修改的
`tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`
ledger evidence gap。Policy／cycle JSON validation 與 `git diff --check` 通過。

## Acceptance mapping

- SC-001 fresh trusted execution：`PASS`；pinned bytes執行、writes受治理、前代 sandbox不變。
- SC-002 兩個代表性週期：`FAIL`；cycle 1因 swap hard ceiling停止，cycle 2依約未執行。
- SC-003 誠實逐 job判定：`PASS`；保留精確 reason-coded NO-GO，沒有把 child exit `0`、
  未完整 workload或單週期當 PASS。
- SC-004 production fail closed：`PASS`；八個 job未轉綠，launchd維持 disabled/not-loaded。

## Changed files

- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-04/preflight.md`
- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-04/cycle-1.json`
- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-04/verification.md`

本 implementation 只產出 candidate evidence，不自審、不建立 Reviewer、不 merge／push／deploy或
啟用排程。

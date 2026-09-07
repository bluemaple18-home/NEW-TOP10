# Fog cross-job repair runtime activation verdict

日期：2026-09-07 19:03（Asia/Taipei）

狀態：`PARTIAL / NATURAL_ACCEPTANCE_PENDING`

## Fixed identity

- Source commit：`bb55fc4c1b316c43398774133d9f6b73ecb53dbe`
- Detached runtime：`/Users/mattkuo/TOP10-runtime-automation-bb55fc4`
- Previous runtime：`/Users/mattkuo/TOP10-runtime-automation-26c8834`
- 正式入口：`scripts/activate_automation_runtime.py --activate`

## Pre-activation gates

- 新 runtime 由同一 canonical repo 的 detached linked worktree 建立，runtime validator `GO`。
- 使用 `uv sync --frozen` 建立獨立 `.venv`。
- active runtime 的 `data/artifacts/models` 只合併到新 runtime 的 absent paths；新 commit 已追蹤檔案不覆蓋，
  `logs`、lock 與 denial marker 不遷移。
- 新 runtime 執行 Storage Guard、Fog natural acceptance、Fog storage validation 與 activation
  failure-state：`198 passed, 38 subtests passed`。
- 即時主機容量：

| job | project bytes | files | host free | memory pressure | verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| fog-research-worker | 1,290,459,358 | 13,408 | 35,420,925,952 | 2 | PASS |
| daily | 3,180,262,139 | 30,906 | 35,421,179,904 | 2 | PASS |
| external-review-preflight | 67,408 | 21 | 35,421,179,904 | 2 | PASS |

- 三條 installed jobs 在 mutation 前均 loaded、`not running`，且指向 previous runtime。
- 新 runtime 三個 denial markers 均 absent；activation receipt path fresh。

## Activation result

- CLI exit：`0`。
- Receipt：`activation.json`。
- Receipt SHA-256：`651ff482454b3719d7697e9f9d0384f56688ed24f9fb7e47379d25d7d56aed31`。
- Receipt status：`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`；failure=`null`；signal count=`0`；
  rollback errors 與 mask restore errors 均為空。
- 三條 plist 都完成 staged lint、bootout、atomic replace、bootstrap 與 post-activation verification。
- 三份 prestate plist 已保存於 `activation.prestate/`。
- 全量 `git diff --check` 只回報 `activation.prestate/com.new-top10.daily.plist` 的既有 trailing
  whitespace；該檔是 rollback 用 exact-byte snapshot，SHA 必須與 receipt 的 `old_sha256` 一致，
  因此不得格式化。排除三份 immutable prestate 後，deployment evidence diff check 為 PASS；前一個
  product candidate commit 的全量 diff check 已為 PASS。

## Marker 與 postcheck

- Previous runtime Fog marker 原檔保留，SHA-256 為
  `c751e59f7410e3b1f0a729b8f9e3f582cd20be7ec75bc0d3efedf7fa405bdaf9`。
- Transaction 只將該 bytes hash-bound mirror 到新 runtime，驗證後清除 transaction-owned mirror；
  previous runtime 原檔未變。
- 3 秒後三條 jobs 均 loaded、`not running`，ProgramArguments 全部指向新 runtime；新 runtime
  denial markers 均 absent；runtime validator 再次 `GO`。
- 未 manual run、未 kickstart、未送 provider、未 push。

## Remaining acceptance

本 activation 只證明安全切換，不證明 Fog recurring acceptance。後續只由既有 `top10-fog` heartbeat
唯讀觀察；只有新 runtime receipt 同時滿足 invocation-bound terminal evidence、cadence、artifact date、
child exit、process-group quiescence、marker/lock absence，並明確達成
`acceptance_status=ACCEPTED`、`accepted_natural_cycles>=2`，才可宣告完成。

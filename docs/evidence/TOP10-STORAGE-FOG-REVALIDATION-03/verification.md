# TOP10-STORAGE-FOG-REVALIDATION-03｜Verification

## 收卡狀態

`READY_FOR_REVIEW / FOG_NO_GO_MISSING_VALID_LIVE_RESOURCE_SAMPLE`

Cycle 1 沒有完成代表性 workload；依卡片禁止 retry，cycle 2 未執行。Production
`launch_verified` 維持 `false`，八個 launchd label 維持 disabled／not loaded。

## Trusted entrypoint RED／GREEN

Clean RED：

```text
PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -B -m pytest -q \
  tests/test_fog_storage_validation.py
3 failed in 0.03s
```

三項都只因 `scripts/storage_validation/fog_research_worker.py` 尚未存在而失敗。

Minimal GREEN 建立單一 Python adapter：

- contract 只接受 `--runner-sha256 <digest>`；raw command remainder 於 runner 執行前拒絕。
- adapter 驗證無 `.git` scope、固定 fog runner path 與 runner SHA-256，再以固定
  `/bin/bash <runner>` 執行既有 business logic。
- 所有 inherited `TOP10_*`、`PYTHONHOME`、`PYTHONPATH` 都被移除；quota、batch、replay 與
  no-retry 環境固定。
- `HOME`、`TMPDIR`、`TMP`、`TEMP`、`TEMPDIR`、`UV_CACHE_DIR`、全部 `XDG_*`、Matplotlib、
  joblib、pip、Numba 與 Hugging Face cache 全部固定到 sandbox 的
  `logs/storage_safety/runtime/fog-research-worker/`。
- `logs`／`artifacts` 由 runner 在 sandbox cwd 使用相對路徑；`.venv` 固定為 sandbox
  `.venv/bin/python`。

主線補充後的 entrypoint suite：

```text
PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -B -m pytest -q \
  tests/test_fog_storage_validation.py
4 passed in 0.11s
```

`.git scope` 與 runner digest mismatch 為兩個獨立測試，各自驗證精確拒絕理由；HOME/cache
收斂另以 hostile inherited environment 驗證。

既有 trust／scope／TOCTOU targeted GREEN：

```text
10 passed in 0.38s
```

涵蓋 raw shell、scope 外寫入、未登記／digest mismatch、contract spawn 前 TOCTOU、
`python -c` dynamic command、Seatbelt probe failure、protected-root mutation 與新的 fog adapter。

## Cycle 1 evidence

Sandbox：local-only
`/private/tmp/TOP10-STORAGE-FOG-REVALIDATION-03.ZzRlh2`。它由 provisioning HEAD tracked
source、final cycle 前的 trusted adapter 與 bounded production input copy 建立；沒有 `.git`、
沒有 symlink。copy 後：

- logical size：`2651344 KiB`
- total files：`46263`（policy meter 初始值為 `711514382` bytes／`13886` files）
- host free：高於 start threshold；swap metric 可讀
- contract digest：`06e868d086e22ebcecb056bc48f167e69b2f8a07aa2801ca1c9e828f397ba45d`
- executed entrypoint digest：`81954c2b41e33d255dfcd5d12413659431c3d5cfba95e4b0f5de53f9b5227d2a`
- pinned fog runner digest：`2780a484e51950b2a6c30089d16111051f5bb3db71fe14e4be74d71923c8ae17`

Guard 結果：

- status：`STOPPED`
- reason：`MISSING_VALID_LIVE_RESOURCE_SAMPLE`
- child exit：`0`
- elapsed：`2.391587018966675` seconds
- samples：一筆 `preflight`、兩筆 `final`；沒有合格 `live` sample
- project delta：`-151683670` bytes／`-5962` files（pre-spawn allowlisted reclaim）
- host-free delta：`+171585536` bytes
- swap delta：`0`
- unknown writes：`[]`
- target process rescan：無存活 fog／validate-run／handoff／replay process
- open-deleted：無
- restart denial：已寫入，`automatic_clear_allowed=false`

Guard log 顯示 runner 兩次對 `/dev/null` 的 redirect 被 Seatbelt 拒絕，接著 lock acquisition
fail closed 並以 0 結束。這不是完整 workload，也沒有 RSS／swap live evidence，不能當 PASS。
依卡片 cycle 1 未完整通過即禁止 cycle 2，沒有 retry 或第二次啟動。

Bounded machine receipt：
`docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/cycle-1.json`。
Raw local-only digests：

- raw receipt：`f701d3ba54be91e758fae2d7f3f6932540598913e36182391c5b3c45d9ee1156`
- guard log：`0b5c7b508d54bca14a1cf2d9e66abc158cff426e12f5ec424ba0977e82ff4993`
- restart marker：`eea4c1027f1b944b96ffba9c9ee7abcedaacb81fedaf35d10919d17409ea91bb`

Sandbox 保留，避免自動清除 restart denial；沒有清理 production data／artifacts／models。

## Post-cycle HOME/cache tightening

主線提醒在 cycle 1 失敗後送達。Final candidate entrypoint digest 為
`0ba3dd78d56517c322a7d63d5dc07f1f9975a64fcae3657af752c7c65140c194`；HOME/cache tightening
已有獨立單元測試，但依 no-retry 契約沒有再執行代表性 workload。Final candidate digest 與
cycle 1 executed digest 不同，因此 cycle 1 更不能支持 candidate PASS。

## 主機、protected state 與 production fail-closed

- Main checkout dirty path 集合仍是原三檔，三個 SHA-256 與 preflight 完全相同。
- 八個 launchd label 收尾全部 `disabled` 且 `NOT_LOADED`。
- 沒有 target process、TOP10 open-deleted file 或 scope 外 mutation。
- Policy ceiling 與 `launch_verified=false` 未修改；其他七個 job 未執行、未修改。
- 沒有 browser/provider、merge、push、deploy 或外部訊息。

## Tests 與 checks

Affected suites：

```text
PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -B -m pytest -q \
  -p no:cacheprovider tests/test_storage_safety.py \
  tests/test_fog_storage_validation.py
39 passed, 16 subtests passed in 4.56s
```

Full suite：

```text
PYTHONDONTWRITEBYTECODE=1 <main-venv-python> -B -m pytest -q -p no:cacheprovider
1 failed, 672 passed, 4 warnings, 270 subtests passed in 59.99s
```

唯一 failure 是 parent 已記錄且 allowlist 外的 environment/evidence gap：
`tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`。
本卡沒有修改該 ledger 或其 evidence。

## Acceptance mapping

- SC-001 trusted entrypoint：code／targeted tests `PASS`；代表性 runtime `NO-GO`，因沒有有效
  live sample，且 final digest 未跑 full cycle。
- SC-002 兩週期：`FAIL`；cycle 1 非代表性，cycle 2 依契約未執行。
- SC-003 逐 job 判定：`PASS`；fog 精確判為
  `NO-GO / MISSING_VALID_LIVE_RESOURCE_SAMPLE`，沒有把短 child 當 PASS。
- SC-004 production fail closed：`PASS`；policy 未轉綠，八個 launchd 維持 disabled。

## Remaining risk／next step

本 implementation 不自行開 Reviewer。Reviewer 應先審查 final trusted adapter 與 cycle 1
reason-coded evidence；若要修正 Seatbelt `/dev/null` compatibility 並重新驗證，必須由主線建立
新的 repair／revalidation 卡與新的 activation，不得在本卡清 marker或 retry。

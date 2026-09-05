# NEW-TOP10 GUI launchd 重開前交接

## Root question

三條核心 automation 是否能在隔離 runtime `ab7c4180422b028a6a2a39fa311ea0ba591d561e` 完成 A5 自然排程驗收。

## Blocker

2026-09-04 21:54:20 的 Restart 由 `osascript`／System Events 觸發，21:55:05 因 `cmux` 無法結束而中斷。GUI launchd domain 已先進入 on-demand-only mode，卻未在 Restart 中斷後恢復；Fog 21:57:26 的 interval event 回 response `36`，到 2026-09-05 10:40 仍為 `runs=7`、`pended nondemand spawn=interval`。

## Candidate fork

Development checkout 另有進行中的 Storage Guard forensics／repair；它不是這次 host-session blocker 的修法，不得在重開前後混入 production runtime。

## Completed actions

- Fog 原 marker 已保存，SHA-256：`f5f99e687dd87bbe89212bb399aee0392ef709628c0c4e626220438f0cb40a2f`。
- Owner 授權後只清除 Fog 單一 marker；清除前 capacity=`PASS`、runtime SHA 正確、無 Fog process、lock 未持有。
- Marker 清除後未復生；未 manual run、未 kickstart、未 reload launchd。
- launchd／loginwindow unified log 已定位 domain-wide root cause。
- RCA 與 canonical frontier 已提交於 `fb7022e`；未 push。

## Active state

- 專案：`<repo-root>`；branch=`main`，HEAD=`fb7022e`，相對 `origin/main` ahead 2。
- Runtime local-only 路徑（不可跨機照抄）：`/Users/mattkuo/TOP10-runtime-automation`，detached SHA=`ab7c4180422b028a6a2a39fa311ea0ba591d561e`。
- Fog marker：不存在。
- Fog latest receipt：仍停在 2026-09-04 21:42:26；worker log 停在 20:12:14。
- Development checkout 有未提交、由其他工作產生的 `app/storage_safety.py`、`docs/operations/top10-storage-policy.json`、`scripts/run_with_storage_guard.sh`、`scripts/storage_safety.py`、`tests/test_storage_safety.py` 與 `.work/P0-NEW-TOP10-STORAGE-GUARD-FORENSICS-20260905/`；不得 reset、覆寫或順帶提交。

## Next step

Owner 已明確授權整台 Mac 正常重新開機。重開後回到本對話：

1. 唯讀確認新的 GUI launchd domain 已建立，Fog job 仍指向 fixed runtime。
2. 確認 marker 仍不存在、沒有 stale Fog process／lock。
3. 不 kickstart；立即監看下一個自然 900 秒 interval。
4. invocation 一結束就保存 receipt、marker（若有）、worker log 與 launchctl state，再依 A5 判決。

## Waiting conditions

- Fog 第 8 次 invocation 必須由自然 interval 建立。
- 單次成功仍只算第一個 accepted natural cycle；A5 需連續兩次。

## Limits

- 不 manual run、不 kickstart、不用單次 plist／loaded 狀態冒充 acceptance。
- 不再次清 marker；若新 marker 出現，先保存並停止重試。
- 不改 installed plist、runtime SHA、其他五條 disabled jobs，不 push。

## Evidence

- `docs/evidence/P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY-A5-NATURAL-20260905/a5-fog-marker-clear-launchd-domain-no-go.md`
- `docs/operations/CURRENT_OPERATIONAL_FRONTIER.md`
- `docs/tasks/2026-09-03_P0-NEW-TOP10-AUTOMATION-RUNTIME-RECOVERY.md`

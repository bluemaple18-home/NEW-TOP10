# A5 Fog 第一個自然週期判決

日期：2026-09-05

狀態：`NO-GO / BLOCKED_WITH_REPRODUCIBLE_EVIDENCE`

## Facts

- A4 activation 後，Fog launchd owner 指向 fixed runtime `ab7c4180422b028a6a2a39fa311ea0ba591d561e`。
- Fog 第一次自然啟動：2026-09-04 20:07:26 +0800。
- Child 已進入 batch 1，之後收到 SIGTERM 15。
- Persistent marker 建立時間：2026-09-04 20:12:24 +0800。
- Marker 原始理由：`LIVE_SAMPLE_CADENCE_EXCEEDED`。
- 到 2026-09-04 21:42:26，共 7 次 launchd invocation；後續 6 次由 `PERSISTENT_RESTART_DENIED_MARKER` fail closed，last exit `75`。
- 查核時無 Fog supervisor/child，lock 檔未被持有；沒有 stale-alive 問題。
- Daily 與 External Review Preflight 在查核時間 2026-09-05 02:11 +0800 均尚未自然執行。

## Red-capable probe

對 runtime 的 `fog-research-worker_latest.json` 斷言 `status=OK`、`child_exit_code=0`、reasons 為空，實際 exit `1`。這個 read-only probe 會在真正成功 receipt 出現後轉綠。

## Hypotheses checked

1. 「目前固定 sampler 或 repo snapshot 必然超過 60 秒」已證偽：現場 `take_sample(process_pid)` 為 0.39 秒，完整 repo write snapshot 為 1.13 秒。
2. 「20:07–20:12 主機 sleep/wake 導致 monotonic gap」未獲支持：該時間窗的 power log 沒有 Sleep/Wake/DarkWake event。
3. 尚未證明的剩餘假說是第一個 active batch 期間的 transient host/I/O scheduling stall。Spotlight `mds` 有一段 4 分 50 秒 BackgroundTask 在 20:12:25 結束，時間與 marker 高度接近，但只能算關聯，不能當成因果證明。

## Evidence gap

第一次 STOPPED 的 detailed latest receipt 已被後續 persistent-denial invocation 覆寫；目前保留的是 original marker reason、worker log 與最後一次 denial receipt，因此不能還原第一次 sample 的 duration、RSS、swap 與完整 process-group details。

## Preserved artifacts

- `fog-research-worker.restart-denied.20260904T201224+0800.json`：SHA-256 `f5f99e687dd87bbe89212bb399aee0392ef709628c0c4e626220438f0cb40a2f`
- `fog-research-worker.latest.20260904T214226+0800.json`：SHA-256 `0037a324b016a6623fe1ee2788b03a6ba0ed890f22df9972c89eb2125d454fef`
- `fog-research-worker.log.through-20260905T021144+0800.txt`：SHA-256 `3867ea5a421029cb2c034efaeac2ee569d050637fbda56f7919620595a0f3946`

## Next decision

未取得新的 production 授權前維持 marker。若授權 bounded recovery，只清 Fog marker並等待下一次自然 15 分鐘 cadence；不做 manual run 或 kickstart。若再次 cadence failure，停止重試並以新 receipt 建立最小 repair。

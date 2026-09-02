# R17 External Fog Revalidation Decision

- overall status: `NO-GO`
- runtime status: `PASS_CANDIDATE`
- outer lifecycle status: `NO_GO: budget exceeded`
- source commit: `abb97d81eb48e38fa073c84931b9d88a6f0fb540`

## Runtime evidence

| cycle | status | topic runs | elapsed | peak RSS | pressure | swap delta | unknown writes | quiescent |
| ---: | --- | ---: | ---: | ---: | --- | ---: | --- | --- |
| 1 | `OK` | 1 | 2712.25s | 771,194,880 B | 1 → 1 | -452,984,832 B | `[]` | true |
| 2 | `OK` | 1 | 1860.61s | 810,205,184 B | 1 → 1 | -67,108,864 B | `[]` | true |

R17 證明 representative workload 與 weekend inventory RSS 修復已 external GREEN；launchd 維持未啟用，沒有 production activation。

## Remaining blocker

Lifecycle helper 在 child 成功後以 exit `2` fail closed。唯讀重算顯示原 clean-room copy baseline 為 `3,710,152,782 bytes / 58,458 files`，超過既定 `50,000` file count；不是 5 GiB byte limit，也不是 fog runtime meter。

本機修復將 model-experiment 複製改為兩個 explicit regime authorities，並排除可再生的 weekend staging／歷史 replay outputs；projected baseline 為 `3,319,144,297 bytes / 48,707 files`。整體仍不得宣稱 GO，須以 R18 完整兩輪與 lifecycle cleanup exit `0` 驗證。

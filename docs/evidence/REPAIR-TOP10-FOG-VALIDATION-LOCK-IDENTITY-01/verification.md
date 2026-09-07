# 驗證紀錄

## 根因

Fog runner 的 A3 lock identity 固定透過 `/bin/ps -o lstart=` 取得 start token；macOS Seatbelt 即使使用 `allow default` 仍拒絕執行 `/bin/ps`。因此代表性 validation child 雖正常啟動，仍在 workload 前安全停止，receipt 為 `MISSING_VALID_LIVE_RESOURCE_SAMPLE`。

## 修復邊界

- production 預設 `PROCESS_IDENTITY_MODE=ps`，原行為不變。
- trusted validation entrypoint 固定注入 `validation-libproc`，以 macOS `proc_pidinfo(PROC_PIDTBSDINFO)` 取得 PID 與 start time。
- helper 使用已由 contract digest 驗證、在 sandbox 外 materialize 的唯讀 entrypoint；不讀 sandbox 內可替換 helper。
- `libproc` 回傳大小、PID 或 start time 任一不符即拒絕，不退化成 PID-only。

## 已取得證據

- 實際 Fog Seatbelt profile 內可查詢自身與同 sandbox 父 Bash 的 start token。
- `/bin/ps` 在相同 profile、`allow process*` 與 `allow default` 下皆被拒絕。
- macOS SDK C layout 與 Python `ctypes` layout 完全一致：size=136、PID offset=12、start sec/usec offsets=120/128。
- targeted entrypoint/revalidation tests：17 passed。
- Bash syntax、Python compile、`git diff --check`：通過。

## 第一輪 review finding

- Reviewer A：`GO`，無 P0/P1；P2 建議補 materialized helper 路徑的 end-to-end assertion。
- Reviewer B：`NO_GO / P1`；完整 identity 建立後若 helper 在 cleanup 階段失敗，舊 fallback 只比 PID 便刪鎖，且 terminal 仍可能成功。
- Repair 1：partial identity 與 established identity 分流；只有前者可做 PID-only 半鎖清理。後者驗證失敗時保留 lock，若主流程原本成功則 terminal exit code 改為 70。
- Repair 1 完整 affected suite：105 tests、38 subtests passed。
- Fog shell contracts：8 組通過，含完整 identity 後 cleanup failure 的 RED/GREEN。
- A/B re-review：均 `GO`；B 明確判定原 P1 closed。

固定 commit 的兩輪 runtime validation 尚待完成。

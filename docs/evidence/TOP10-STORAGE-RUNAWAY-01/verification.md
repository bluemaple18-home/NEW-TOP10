# 驗證紀錄與最終判定

## 已通過

- bounded archive RED／GREEN：舊版 4 檔失敗，修正版兩週期固定 2 檔。
- storage policy schema：八 job 欄位完整，且全部 `launch_verified=false`。
- preflight 注入：policy 未驗證、bytes／file count 超額、低啟動空間、swap 不可讀都 fail closed。
- runtime 注入：低執行空間、未登記寫入、持續超速增長、未穩定／未回收、RSS＋swap 同升、
  RSS 不可讀都有停止訊號。
- 兩個 bounded guard 週期：兩次 exit 0、receipt 存在、輸出恰為 `xx`、沒有 restart marker。
- 隔離停損 drill：注入低磁碟使 target process group exit 70，marker 持久化；第二次嘗試
  exit 75；獨立 `sleep` 程序仍存活。
- guard internal-error 與 SIGTERM drill：兩者都停止 fixture child、exit 70 並留下 persistent
  marker；獨立程序不受影響，後續嘗試拒絕。
- allowlisted reclaim：fixture bytes 與 file count 實際下降，scope 外 protected hash 不變。
- 八個 plist 都經 storage guard，launchd stdout／stderr 都改為 `/dev/null`，且沒有 KeepAlive。
- wrapper 將 TMP／uv／XDG／Matplotlib／joblib cache 收斂到 job-specific project path。
- 最終 code review 補掉四個 fail-closed 缺口：環境變數不得替換 guard Python、policy boolean
  嚴格驗證、未登記刪除也算 mutation、監控／log 例外與 TERM／INT 都會停止尚在執行的 child
  並留下拒絕重啟 marker。
- 目前八個 live launchd job 仍 disabled；沒有 load、kickstart、enable、restart、deploy、push 或 merge。

主要測試命令：

```bash
.venv/bin/python -W error::ResourceWarning -m unittest tests.test_storage_safety
```

結果：12 tests passed。另執行受影響 verifier／tests、shell syntax、Python compile、plist parse
與 `git diff --check`；最終結果以本卡完成時的收尾紀錄為準。

全套 pytest 在不掛載 live `artifacts/`／`data/` 的 isolated worktree 得到 645 passed、
1 failed、270 subtests passed。唯一失敗是
`test_verifier_accepts_generated_ledger` 的 `evidence_exists`：測試本身依賴未納入 git 的
live evidence files；相同單測在未修改的 main checkout 為 1 passed。這不是本 diff 的產品
回歸，也沒有為了讓測試轉綠而複製或修改 forbidden live artifacts。

另有既存 shell test `tests/test_research_failure_fingerprint.sh` 在 worktree 與 main 都會於
immutable time context 前失敗，原因是測試把 `TOP10_DAILY_PYTHON=/bin/false`，同一變數現在
也被 time-authority 使用。本卡沒有修改該 wrapper／測試，記為 pre-existing unrelated
test debt；其餘 fog time wiring、retry circuit、research lock 與本卡 affected tests 通過。

## 未通過／禁止啟動

AC-3 要求每個功能以代表性資料跑兩個完整週期，記錄容量、檔數、RSS、swap、每小時增長、
一小時／一天／保留期峰值。這會執行 live-like TOP10 workload，而卡片同時要求所有 live
排程維持停用；本輪只被授權 bounded fixture，沒有代表性 live 週期證據。

因此八個 budget 仍是 provisional，`launch_verified=false`，最終判定為 **NO-GO**。
不得用目前主機已回到約 60 GiB 可用空間、fixture 兩週期或 swap 已降至約 653 MiB 取代
AC-3。

## 解除 NO-GO 的必要條件

1. 另取得明確授權，在排程仍 disabled 的前提下，以 guard 手動執行每個 job 兩個代表性週期。
2. 保存每次 receipt 的完整 samples 與實際回收結果，推估一小時／一天／保留期峰值。
3. 以實測修訂 provisional ceiling，通過審查後才將逐 job `launch_verified` 設為 true。
4. 再跑 affected tests、storage gate 與 `git diff --check`。
5. 啟用 launchd 是另一個外部控制面變更，仍需使用者另行明確授權。

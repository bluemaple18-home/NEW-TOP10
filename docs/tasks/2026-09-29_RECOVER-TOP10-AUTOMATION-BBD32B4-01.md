# RECOVER-TOP10-AUTOMATION-BBD32B4-01

## 目標

以 `bbd32b4f017498b413a32a1171aec76f426441a3` 建立 detached 固定候選 runtime，完成 production activation 前的有界驗證。

## 範圍

- 候選 runtime 總量上限：6 GiB。
- 兩輪完整 Daily 隔離週期與資源／程序群組證據。
- 受控安全停止、restart-denied marker recovery 與精確 rollback 驗收。
- 真實 Google Chrome 的 Gemini probe-only；不得填入或送出 review packet。
- 保留 production launchd、plist 與既有 denial marker 原狀。

## 禁止事項

- 不切換 launchd。
- 不清除 production marker。
- 不執行 production Daily。
- 不送出任何外部 review packet。
- 不 push、merge 或 deploy。

## 驗收結果

1. **PASS**：runtime 為同 repo、detached HEAD、exact accepted commit，tracked tree clean；實際約 1.98 GB，低於 6 GiB。
2. **PASS**：Foundation important-usage 扣除 6 GiB 後為 28,995,299,209 bytes，高於 24,510,719,590 bytes reserve；Daily guard fresh measure PASS。
3. **PASS**：兩輪 Daily 隔離週期成功，外送關閉，final process group quiescent，沒有 unknown write。
4. **PASS**：fresh fixture 的安全停止留下 hash-bound marker；後續 invocation 在 child 前 exit 75；latest 可由 marker 精確還原；rollback tests 5/5 PASS。
5. **REPAIR VERIFIED／NEW CANDIDATE + GUI PROBE PENDING**：真實 Chrome 的精確 profile／tab／composer readiness 與 `review_packet_sent=false` 已證明。舊 `Invalid Gemini window/tab identity` 根因為 Chrome dictionary 將 bare `tab` 解讀成 class token；working tree 已改用 `|` 並通過 20 tests／11 subtests、shell syntax 與 diff check。`bbd32b4` 固定候選未改動；目前 Native2 command context 沒有有效 GUI／XPC session，尚缺新 exact candidate 的真實 script-level probe。
6. **PASS**：production plist／launchctl 仍指舊 runtime；production marker SHA-256 與 precheck 一致；candidate marker absent。

## 裁決

`PREACTIVATION_PARTIAL_PASS_PRODUCTION_NO_GO`

Identity parser 的程式缺口已關閉於 working tree，但尚未 commit／materialize 成新 exact candidate，也尚未在有效 GUI host session 取得修補後的 script-level PASS。真實 Chrome 唯讀 readiness PASS 不能取代新候選 acceptance。不得切 production。

## 證據

- [收斂報告](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/report.md)
- [Evidence manifest](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/manifest.json)
- Candidate 原始 Daily receipts 與歷史失敗 logs 保留於固定 runtime，未刪除或改寫。

## 狀態

`PREACTIVATION_PARTIAL_PASS_PRODUCTION_NO_GO`

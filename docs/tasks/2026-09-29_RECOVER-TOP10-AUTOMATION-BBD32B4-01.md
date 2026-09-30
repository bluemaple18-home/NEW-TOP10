# RECOVER-TOP10-AUTOMATION-BBD32B4-01

## 目標

以 `bbd32b4f017498b413a32a1171aec76f426441a3` 為原驗證基線；identity repair 的 `1f3aa307b3a2e61f2220e6cc48809b7151ba0b77` 已整合至本機 main，使用既有 canonical linked worktree 完成 production activation 前核對。

## 範圍

- 候選 runtime 總量上限：6 GiB。
- 兩輪完整 Daily 隔離週期與資源／程序群組證據。
- 受控安全停止、restart-denied marker recovery 與精確 rollback 驗收。
- 真實 Google Chrome 的 Gemini probe-only；不得填入或送出 review packet。
- 原 preactivation 階段保留 production 原狀；2026-09-30 Owner 已明確核准核對通過後正式修復，僅准入 Daily／provider preflight 切換。舊 denial marker 保留。

## 禁止事項

- 未獲授權前不切換 launchd；2026-09-30 核准的兩個 job 切換已完成，不延伸至其他 job。
- 不清除 production marker。
- 不執行 production Daily。
- 不送出任何外部 review packet。
- 不 push、merge；deployment 僅限 2026-09-30 已核准的兩個 job／exact candidate。

## 驗收結果

1. **PASS**：runtime 為同 repo、detached HEAD、exact accepted commit，tracked tree clean；實際約 1.98 GB，低於 6 GiB。
2. **PASS**：Foundation important-usage 扣除 6 GiB 後為 28,995,299,209 bytes，高於 24,510,719,590 bytes reserve；Daily guard fresh measure PASS。
3. **PASS**：兩輪 Daily 隔離週期成功，外送關閉，final process group quiescent，沒有 unknown write。
4. **PASS**：fresh fixture 的安全停止留下 hash-bound marker；後續 invocation 在 child 前 exit 75；latest 可由 marker 精確還原；rollback tests 5/5 PASS。
5. **EXACT CANDIDATE GUI PROBE PASS**：修補已成為本機 commit `1f3aa307b3a2e61f2220e6cc48809b7151ba0b77`。2026-09-30 11:41 +08:00 改用 Codex 本機 host exec（受審核的 `require_escalated` 通道），同一候選腳本 exit 0、`ok=true`、`phase=execute`、`readiness=input_ready`、`hasComposer=true`。未改程式、未帶 packet、未輸入或送件；tracked tree 維持 clean。Native2 兩次失敗保留為歷史證據，不再視為當前 GUI blocker。
6. **ACTIVATION READBACK PASS**：2026-09-30 14:42 的 production plist／launchctl 已指向 canonical `1f3aa30` runtime；兩個 job loaded／enabled，schedule 不變。舊 production marker SHA-256 與 precheck 一致，新 runtime marker absent；其他服務 plist 全數未變。

## 裁決

`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`

Identity parser 修補、canonical candidate 與 GUI probe 已通過。Owner 清理容量後明確授權正式修復；14:41 +08:00 重測原 6 GiB 預算仍有約 3.34 GB margin，launchd 通道實測載入／卸載及清理通過，遂以既有 transaction 完成兩個 job 的正式切換。切換 exit 0，獨立回讀 PASS。probe 的 `hasSendButton=false` 不代表外送已驗收；自然 Daily 與 provider preflight 仍待原排程執行。

## 證據

- [收斂報告](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/report.md)
- [Evidence manifest](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/manifest.json)
- [Host 通道 exact-candidate probe 與 production 前後核對](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/gemini-host-channel-probe-20260930.json)
- [正式 activation receipt](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/activation-1f3aa30.json)
- [本次重核、真實 launchd 通道與切換後獨立回讀](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/activation-precheck-20260930.json)
- Candidate 原始 Daily receipts 與歷史失敗 logs 保留於固定 runtime，未刪除或改寫。

## 狀態

`ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`

最新：2026-09-30 14:41:40 +08:00 已完成 Daily／provider preflight → canonical runtime `/Users/mattkuo/TOP10-runtime-automation-bbd32b4`、HEAD `1f3aa307b3a2e61f2220e6cc48809b7151ba0b77`。14:42:58 回讀兩者 loaded、enabled、not running、runs=0；保留平日 17:30／每日 17:40 排程，未 kickstart、未人工 Daily。舊 production marker SHA-256 未變，新 runtime marker absent，非目標 plist 全數未變，回退快照已保存。等待自然來源、當日 artifacts／送出 receipt 與資源終端證據，不用切換成功冒稱完整恢復。以下為本次切換前的歷史核對。

2026-09-30 續作：本機 main 精確為 `1f3aa30`；canonical candidate 沿用 `/Users/mattkuo/TOP10-runtime-automation-bbd32b4`，HEAD 已更新至相同 SHA 並通過同 repo／detached／clean 驗證。新候選 20 tests／11 subtests 及 GUI probe PASS，既有 Daily／rollback 程式與原驗收基線相同。正式 Daily 與 provider preflight 的切換、失敗回退與自然驗收方案已寫入原報告，未執行 activation。

11:58 的歷史 Foundation 量測在原 6 GiB 預留後曾不足 **168,243,200 B**，當時保持 `NO_GO`。Owner 其後完成容量清理並核准修復；14:41 重測與正式切換結果以上方最新狀態為準。該次不足的原始證據保留，不再當作當前待辦。

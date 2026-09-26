# REPAIR-AI-CORE-NESTED-SANDBOX-TEARDOWN-01

## Objective／交接狀態

- 工作名稱：修復受管 sandbox 巢狀程序的停止／清理安全缺口。
- 狀態：HISTORICAL_INTAKE_SUPERSEDED；下方為 9/22 初始派卡內容，不能當目前狀態。ai-core 後續已實機證實 RED、交付保守防護，但正常 nested 完成仍未達；接線與 ES 研究沿用唯一接線卡，ES／Apple 路線於 9/26 被 Owner 關閉。最新全鏈裁決見 `docs/evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/recheck-report-2026-09-26.md`，沒有新的修復／試跑授權。
- Owner 要求：2026-09-22「開卡給我，我拿去 ai core」。本輪只建卡，由 Owner 帶到 ai-core 接手；沒有自動派工或跨專案修改。
- 目標專案：`<ai-core-root>`。TOP10 保留自己的 Mainline，這張卡不移交 TOP10 全專案責任。
- 使用者故事 US-01：作為受管驗證的操作者，我需要工作中斷時先確認本輪程序已安全停止，再清理其目錄，避免運算尚存活卻刪掉工作目錄，且不影響其他專案。
- 成功條件：修補後以可重跑的正向與負向測試證明 US-01；缺少程序歸屬或停止證據時 fail closed，不能宣告 cleanup PASS。

## Evidence／已知失敗路徑

本卡來自 TOP10 完整隔離 Daily 試跑的前置檢查；**不是 Sept 9 容量事故根因，也不是已發生的誤刪事故**。

既有組合：ai-core `tmp_artifact_lifecycle.py run` → TOP10 `scripts/storage_safety.py validate-run` → digest-pinned `scripts/storage_validation/daily.py`。

1. ai-core `scripts/tmp_artifact_lifecycle.py` 的 `run_child`（本輪約 991 行）只追蹤自己建立的程序群組；TERM 後等待 1 秒便升級 KILL（約 1037–1047 行）。
2. TOP10 `app/storage_safety.py` 的 `_spawn_verified_process_group`（約 1218 行）把真正運算 child 放入另一個 session。
3. TOP10 `interrupt_guard`（約 1913 行）收到 TERM 後進入異常收束；`terminate_process_group`（約 1179 行）可等待 5 秒 TERM＋5 秒 KILL。
4. 外層可能先殺掉 guard，內層 child 不在外層群組中。外層 `cleanup`（約 689 行）沒有再次核對這個 nested child，可能開始清理 owned root。

因此存在「外層退出／被殺 → 內層仍存活 → root 開始被清理」的來源可成立路徑。主線與獨立 worker 的唯讀判讀一致；**尚未 runtime 重現**，第一步必須用受控 fixture 驗證，不能直接把假設升為確認事故。

來源 SHA-256（接手需重查，行號只供定位）：

| 根目錄與相對路徑 | SHA-256 |
|---|---|
| `<ai-core-root>/scripts/tmp_artifact_lifecycle.py` | d465b6be34d0dbc28c532da6c00774e2fdc81de6f59abc969a947bc35fabc2c4 |
| `<top10-root>/app/storage_safety.py` | 7a74c41b618a0113dd21195845d75c5461e397ada7f653820de79d73df51a52e |

## Scope／Constraints

- In scope：既有 tmp artifact lifecycle 的有界停止、程序歸屬判定、清理准入及必要回歸測試。先確認是否已有安全接縫，優先最小修補。
- ai-core 可唯讀 TOP10 guard 作相容性依據；若必須修改 TOP10 caller，回報所需最小契約，交回 TOP10 Mainline，不自行跨 repo 修改。
- 不新增第二套 runner、通用 supervisor、registry、DB 或常駐 watcher；不硬編 TOP10 特例。
- 不只把 1 秒調大當作解決；修法必須涵蓋失去 owner、逾時、signal、部分啟動與清理失敗。
- 不為通過測試放寬容量／TTL／程序 identity 邊界，也不直接使用 unmanaged full-repo sandbox。
- 不以全機程序名稱搜尋或廣泛 kill 代替本輪 ownership；不得殺其他 repo、Chrome、Codex 或既有工作。
- 不清理歷史、foreign 或 ownership 不明的 tmp；保留唯一工作與未提交改動。
- Out of scope：TOP10 production marker、runtime/plist、排程、Daily 補跑、Gemini 實機操作、retrain sync、external-review 啟用、Discord／任何外送、push／部署。
- 為何不更少：只調時間或 TTL 無法證明跨 session 收束；為何不更多：這是既有生命週期的有界缺口，不需要新的程序管理平台。

## Acceptance／必須交付的證據

以下均追溯 US-01；實作選型由 ai-core 決定，不把設計假設當需求。

| ID | 情境與可驗證結果 |
|---|---|
| AC-01 RED | 建立受控外層／guard／另 session child；child 延遲或忽略 TERM。以同步事件而非碰運氣 sleep，重現舊版的收束／cleanup 次序問題；若無法重現，交付反證與實際控制流，不強改。 |
| AC-02 正常完成 | owned 工作完成、程序停止可證明、證據匯出成功後，exact owned root 才消失；exit code 與 cleanup receipt 相符。 |
| AC-03 中斷與停損 | 分別覆蓋 SIGTERM、SIGINT、TTL、bytes／file-count 停損；每條路徑都能證明已知 owned nested child 已收束，或明確 BLOCKED 並保留 root，不得誤報 PASS。 |
| AC-04 失去 guard | guard 異常退出或遭 KILL、nested child 尚存活時，不得把外層 group 消失當作全體停止。測試保留 unrelated sentinel，證明沒有跨 scope 終止或刪除。 |
| AC-05 identity 不明 | PID 重用、ownership／session 證據缺失或程序查詢失敗，禁止猜測性 kill／cleanup；保留安全復原所需證據與原始失敗。 |
| AC-06 清理失敗 | 部分啟動、停止失敗、匯出／cleanup 失敗或重複 signal，不掩蓋原始錯誤，不留下偽 PASS；依既有 isolation/recovery 契約處理，不新建平行機制。 |
| AC-07 相容性 | 既有單群組、正常成功、失敗、同 repo admission 與容量政策測試維持有效；針對 TOP10 已知巢狀拓撲提供 fixture 相容性證據，不跑真實 Daily。 |

執行前列出 trap／handler 的副作用與各 failure state。依既有 teardown 規範，由兩名互不參照 verdict 的 Reviewer 獨立執行關鍵驗證，以重現證據裁決；不能只審 fixed diff。

## Handoff／開工與交回契約

1. 在 ai-core 核對自身 AGENTS、工作樹、來源 SHA／相關 CodeGraph query 及既有測試；來源變更則重判，不盲套行號。
2. 列出本輪控制的 PID／PGID／SID 與 cleanup 順序，設計可確實收束的 synthetic RED。若 fixture 的安全回收本身無法保證，停下回報，不先啟動真實長跑負載。
3. RED 成立後沿既有接縫最小修補，完成上表 GREEN、受影響回歸、`git diff --check` 與兩份獨立 verdict。
4. 交回：修改檔案、基準與候選 SHA/digest、重跑命令、RED/GREEN 原始證據、程序停止與 root 消失／保留證據、未影響 sentinel 證據、回退方式、未解限制。
5. 終態只宣告 `SAFE_FOR_TOP10_ISOLATED_VALIDATION` 或 `BLOCKED_WITH_EVIDENCE`；前者僅代表 fixture 所證明的隔離入口可用，不代表 TOP10 已恢復或獲准上線。

技術待辦由 ai-core 負責：是否已有安全替代接縫、何種最小 ownership／teardown 修補足夠、能否受控重現。若判斷需新全域治理或擴大產品範圍，回 Owner 裁決，不自行吸收。

## TOP10 接回時必讀

- `<top10-root>/docs/tasks/2026-09-22_REPAIR-TOP10-DAILY-PROVIDER-01.md`
- `<top10-root>/docs/evidence/REPAIR-TOP10-DAILY-PROVIDER-01/report.md`
- `<top10-root>/docs/evidence/INVESTIGATE-TOP10-AUTOMATION-END-TO-END-01/report.md`

TOP10 現況：Daily／Gemini local candidate 已修補並複審；完整兩輪 ETL 尚未執行，production 未恢復。整組測試曾 183 passed、1 failed、50 subtests passed；失敗為既有 guard 取樣次數差異，單獨重跑通過，不可宣稱全綠。

ai-core 交回後，由 TOP10 重新量測 Foundation admission／容量，依當時有效 policy 進行兩輪完整隔離試跑。`project_sandbox_policy.json` 本輪 defaults 為 800 MiB，舊容量取樣不可挪作新准入；部署、清 marker、provider 實機與外送仍各受原有邊界約束。

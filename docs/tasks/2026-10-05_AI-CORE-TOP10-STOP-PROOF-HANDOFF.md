# AI Core 接回卡：TOP10 巢狀停止證明與外接隔離契約

1. objective：沿既有 `REPAIR-AI-CORE-NESTED-SANDBOX-TEARDOWN-01` 接回可驗的巢狀停止／證據保全交付，讓 TOP10 能判斷是否可進行 Fog 代表性驗證；不是重開容量案。
2. scope：ai-core 既有 teardown／handoff 接點與受控測試；TOP10 僅唯讀參考，必要的 TOP10 接線修改交回原主線。
3. constraints：不新增共用 runtime、不降容量門檻、不清標記、不恢復 Daily／正式服務、不清理未知程序或證據、不部署／push／外送；沿用既有修復次數與成本核准。
4. acceptance：實機受控拓樸的正常／失敗／中斷停止證據、未知時拒絕清理、證據匯出失敗保留原件；提供版本、命令、receipt、兩名獨立盲審結果及可回退方式。
5. status／handoff：`READY_FOR_OWNER_HANDOFF`，尚未送出或由 ai-core 接受；交回本卡所列 evidence refs，不以單次 PASS 解除 TOP10 的 `LIVE_BLOCKED`。

## 既有狀態與證據

以下是 TOP10 截至 2026-10-04 的交付紀錄，不是 10/05 新容量或正式狀態量測。接手必須核對當前檔案與版本。

- TOP10 工作樹基線 `2534843`，交付含未提交修改；不得只 checkout 該 SHA 就宣稱拿到修補。完整檔案 SHA、回歸命令及限制見下方證據報告。
- 正常 storage guard 的外接暫存／快取受控接線已有證據；Fog 已實際接回 CLI→guard→共享唯讀 source／既有 interpreter，不再複製整庫與 `.venv`。owned output 上限 256 MiB。
- source manifest 已補目錄成員、optional ledger、external-review 候選／真正選中內容釘版。254 passed、2 deselected、41 subtests；兩名 Reviewer 關閉這次 P1。這不證明完整 runtime inputs 已閉合或來源為原子 snapshot。
- native 四種微型情境通過，但使用 synthetic representative 與合成 host 准入，只能證明該受控拓樸，不能取代真實巢狀工作所有後代全停證明。
- Daily 最後核對為 not running／runs 3／exit 75，正式服務設定與 restart_denied 雜湊未變；本卡不授權解除。
- 舊 ai-core 交回路徑 `docs/evaluations/REPAIR-AI-CORE-NESTED-SANDBOX-TEARDOWN-01/handoff.md` 在上輪 TOP10 查核時未找到。先找回原交付及版本；找不到即明示缺件，不從先前「105 tests／兩名 Reviewer」的文字推定已驗收。

## 責任與範圍

### AI Core 要交回的單一成果：可驗的停止／隔離接回契約

- 找回既有 repair 的有效版本、原 findings、修復上限與未解條件；只針對已量測缺口補最小修改。不能用本卡新名稱重置修復額度。
- 從既有 trap／handler 逐一列出實際副作用與 failure state：停止請求、程序觀測、證據匯出、清理、回退。明確說明正常巢狀工作如何證明所有受管後代停止，而不只證明父 PID 或單一 process group 消失。
- 用隔離、小型、受管且可停止的實機探針覆蓋實際拓樸；包含會重設 session／process group 或父程序先退出的情境（若該平台可能發生）。不可為取得證明先啟動仍依賴缺失停止保證的完整 Fog 工作負載。
- 程序查詢錯誤、身分／歸屬未知、停止逾時、匯出失敗一律保留證據與封鎖；不把 unknown 當已停止，也不廣泛 kill／清理全機程序。
- 對外接消失／不可寫，交回既有隔離入口如何 fail closed、如何保持歸屬與停止／回退契約的具體介面或不支援裁決。不能只建議清除環境變數或解除 sandbox。

### 留在 TOP10 的工作，不轉嫁給 AI Core

- `EXTERNAL_CACHE_ISOLATION_UNSUPPORTED` 是目前 shared isolated Fog 的明確保護；接回 ai-core 契約後，TOP10 才沿自己的 guard／sandbox profile／output 入口實作相容。不授權 ai-core 改 TOP10 code 或接管 TOP10 Mainline。
- 內建、cache image、外接 backing 各自 fresh 容量准入與代表性 workload 驗收，由 TOP10 接回後執行。外接空間充足不抵銷內建保留線；sensor unknown 不等於零容量。
- toolchain 沿 `<ai-core-root>/config/toolchain_paths.sh`；共用快取維持既有 20 GiB 硬上限。缺碟不得回寫內建，不另建快取 runtime。

## 驗收與交回格式

交回原 ai-core evidence／handoff 落點即可，不建立第二套 registry、ledger 或狀態機。至少包含：

1. **版本**：repo／branch／commit、未提交差異與受影響檔案 SHA；與原 repair 的連續性。
2. **停止證據**：正常、失敗、取消／中斷、逾時各自的命令、程序身分／後代關係、觀測結果及最終未決項。沒有可觀測證明時報 `BLOCKED_WITH_EVIDENCE`。
3. **保全／回退**：匯出失敗不刪原件、查詢錯誤不清理、外接消失不回落內建的反例及結果；只能清理已證明歸屬且全停的受管測試資料。
4. **獨立驗證**：沿原兩名盲審責任線實跑，區分原 finding resolved 與剩餘風險；不拿 Reviewer 文字批准取代 runtime receipt。
5. **最小接回介面**：TOP10 應呼叫／提供什麼、會得到何種成功／拒絕／未知結果、哪些輸出允許清理；列出精確檔案及命令，不要求 TOP10 自行猜測。
6. **裁決**：可接回範圍、不可接回範圍、容量量測是否新鮮、剩餘 blocker。即使 ai-core 局部 PASS，Daily 與正式服務保持原樣。

## 下一步與停止條件

- 接手先唯讀核對原卡／handoff 與本卡引用證據，再沿已有 seam 工作；不重跑泛查或開新容量／平台專案。
- 本卡製作屬 minimal 文件工作；接收端涉及 teardown 的執行屬 strict，規格固定時依既有路由選最低足夠模型與獨立驗證，不改使用者選定模型。
- 同類連兩次無進展或同一 blocker 第三次失敗即停止；成本額度用盡或需要新平台能力／擴張權限，回報最小缺口並向 Owner 取得決策，不自行繞過。
- 完成後將證據交回 TOP10 原主線做整合裁決；本次「拿去 ai-core」是局部接回責任，不是 TOP10 完整開發／Mainline 轉交。

## Evidence refs

以下均相對 `<TOP10-root>`，ai-core 接手時從 TOP10 工作樹讀取；不要把 ai-core HEAD 當成 TOP10 修補版本。

- `docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/external-cache-wiring-20261004.md`：完整證據、SHA、命令、容量與剩餘限制。
- `docs/tasks/2026-10-01_TOP10-FOG-BOUNDED-VALIDATION-INPUT-OUTPUT-01.md`：Fog 原卡及 FOG-IO-002。
- `docs/tasks/2026-10-04_TOP10-EXTERNAL-CACHE-WIRING.md`：外接接線範圍。
- `docs/tasks/2026-09-29_RECOVER-TOP10-AUTOMATION-BBD32B4-01.md`：原恢復鏈與成本／停止條件。

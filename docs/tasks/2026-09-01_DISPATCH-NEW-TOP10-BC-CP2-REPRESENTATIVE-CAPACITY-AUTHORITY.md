# BC-CP2 代表性容量樣本 Authority 派工卡

工作名稱：BC-CP2 代表性 E3 樣本 Authority 與容量量測

任務簡介：判定現有 committed authority 是否足以建立不依賴 B1／B2 implementation 的代表性合法樣本；只有 authority 可追溯時才執行隔離、有界 E3 容量量測，否則交 missing-authority receipt。不得用便利樣本、單一 scenario 或數學列舉自行升格為代表性證據。

來源與依賴：slice_id=`BC-CP2-RCA-01`；traces_to=`B0P1-BC-002 / B0P1-BC-004 / B0P1-BC-005 / C0P2-CAP-004`；canonical main `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`；B0 Phase 1 repaired fixed SHA `1e9ed61e2e5c86adf2159e095ff241ef13127e80`；C0 Phase 2 `a61f143ea5223b6af812e27aac0082121f781343`；Issue #13／#14；`docs/RESEARCH_SPINE_BACKLOG.md`。

執行規範：你是 GPT-5.5 high strict/core-bounded 證據工作者；Sol 只做 Mainline 裁決與驗收。只做唯讀 authority reconciliation 與必要的隔離暫存量測；不得建立 canonical TrialSpec／CandidateDecision authority，不得修改 code、config、workflow、queue、runner、scheduler、backtest、production 或既有 evidence，不得 merge、push、改 Issue、執行 external write，亦不得准入 B0 Phase 2、B1 或 C1。

驗收與交接：只新增 `docs/evidence/BC-CP2-REPRESENTATIVE-CAPACITY-AUTHORITY/01-sample-authority-and-capacity-receipt.md`。若 GO，必須固定 sample selection authority、coverage rationale、immutable inputs、命令、wall time、candidate/sec、CPU、peak RSS、I/O、cleanup 與禁止外推邊界；若 NO-GO，必須固定缺失 authority、blocking edge 與最小後續卡。需通過 trace preflight、範圍核對、`git diff --check` 與獨立 fixed-SHA review；完成後只用繁中回報固定 SHA、verdict、驗證與下一個 frontier。

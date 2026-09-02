# C0 Phase 2 容量與切換設計派工卡

工作名稱：C0 Phase 2 容量量測與控制切換證據

任務簡介：依 BC-CP1 的 `ADMIT_C0_PHASE_2` 裁決，以 B0 已接受的 `720 / E2=NOT_PROVEN / E3 / E4=REQUIRED_BUT_UNCHARACTERIZED` 為固定輸入，完成容量與 execution-control gap 證據；不得啟動 C1、B1 或任何 runtime mutation。

來源：canonical main `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`；B0 Phase 1 `d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98`；C0 Phase 1 `c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba`；AI Core baseline `21801303adff285268f7646df94dc53da31a835f`；Issue #14；`docs/RESEARCH_SPINE_BACKLOG.md`。

執行規範：你是 GPT-5.5 high strict/core-bounded 證據工作者；Sol 只負責 Mainline 裁決與驗收。只做唯讀研究及隔離、有界、暫存式量測；不得修改 code、config、workflow、queue、runner、scheduler、model、backtest、production 或 A6 bridges，不得 merge、push、改 Issue 或執行其他 external write。若沒有代表性樣本 authority，只能交 missing-authority receipt；非代表性量測不得外推為完整 720 或每日容量。

交付與驗收：只交 Phase 2 的 `05`–`10` 六份 evidence 與本卡。每項重大主張須固定 source SHA／range 並具完整 claim schema；容量證據須分開記錄已量測事實、推估與未知，包含 sample authority、wall time、candidate/sec、CPU、peak RSS、I/O、reuse、暫存邊界及可重跑命令。需通過範圍核對、`git diff --check` 與獨立 fixed-SHA review。完成後只回 candidate SHA、changed files、verification、remaining unknowns 與 C1 blocker recommendation，不得自行准入後續卡。

目前狀態：`RESUMED_BY_OWNER`。只續做 Mainline 已指出的容量量測 bounded repair。

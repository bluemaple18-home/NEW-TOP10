# 交給 ai-core：TOP10 Daily 內建碟容量回收與分卷修復

## 任務名稱 → 正在做什麼 → 現在狀態

TOP10 Daily host capacity recovery → 盤點並安全回收內建碟空間，釐清外接盤實際可用容量 → `NO-GO`；尚未執行清理或搬移。

## Root question

使用者已購買並接上外接硬碟，為何 TOP10 Daily 仍在內建碟容量閘門停跑？ai-core 請負責主機／分卷容量處置與可稽核回收；TOP10 production marker、Daily 和 Discord 驗收仍由 TOP10 正式流程負責。

## 已確認事實

- 正式 Daily runtime：`~/TOP10-runtime-automation-3b6ff80-20261015`，HEAD `3b6ff80f5efac9207861ad9c7586b6338a7486b5`。10/16 自然週期 STOPPED；10/19 `launchctl` last exit 75，persistent restart-denied marker 仍在。不得用手動執行或舊日 receipt 代替自然週期。
- 10/16 開跑時 Foundation important-usage 內建可用 27,826,817,344 bytes；結束時 24,319,625,536 bytes。runtime 保留線 24,510,719,590 bytes，跌破 191,094,054 bytes。同輪全系統 swap 增約 3.33 GB，TOP10 meter 專案檔案只增約 22.6 MB。swap 是全系統數值，現有 receipt 無法歸因特定程序。
- 10/19 調查時 Foundation 可用 23,531,924,643 bytes，比保留線低 978,794,947 bytes；VM 卷約 15 GB。這是時間點數據，執行前必須重測。若按 10/16 的 3.51 GB 主機容量跌幅估算，僅補目前約 0.98 GB 缺口不足以支撐同級週期；需要實測尖峰與持續餘裕。
- 外接接線只承接 TOP10 tmp／uv／XDG／Matplotlib／joblib 快取，正式 runtime 的 `data`／`artifacts`／`logs` 仍在內建卷。`~/Storage-Relief-20261012` 約 24 GB，含先前由外接搬回內建的四組封存；各自 relocation receipt 在該目錄。`<repo-root>` 約 11 GB，其中 `docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/` 多份完整驗證 sandbox 副本約 5.9 GB，`.codegraph` 約 2 GB；六組 TOP10 runtimes 約 5.5 GB。`du` 包含 APFS clone/shared blocks，不能當作可回收物理量。
- 外接 VibeCode 的 APFS 底層 container 調查時僅約 13 GB 未配置，卷配額／Finder 可用值不同；不得直接把 24 GB 整包搬回。`/Volumes/AICoreCache` 是獨立 21.5 GB 快取映像，不是無限外接空間。內建、外接均未見 APFS snapshots，也未見大型 open-deleted file。
- 外接快取另有 `EXTERNAL_CACHE_RETENTION_EXPIRED`：TOP10 Daily root 留有一個過期 Matplotlib fontlist（350,264 bytes）。這是另一張應由 TOP10 修復的 cache lifecycle 缺口；容量回收卡不得靠放寬 retention gate 解決。

## Scope／授權邊界

1. **先唯讀盤點**：以主機原生 Foundation important-usage、raw free、APFS container／卷、VM／swap、實際寫入根與引用者建立基線；同時量測外接目標卷的物理、Foundation、配額與 image cap。內建與外接不得跨卷抵扣。
2. **列 exact-owned 候選清單**：依冷封存、完整驗證副本、可重建索引、舊 runtime 分類；逐項註明 owner、是否唯一資料、活躍引用／symlink、大小、hash、預計回收的物理 bytes、保留與回退方式。`Storage-Relief` 內含非 TOP10 專案資料，不得因本卡直接清理。
3. **提出最小可行回收／搬移方案**：先選可證明可重建或已有驗證副本的 exact-owned 資料；若搬移，必須確認外接卷的實際餘裕與 ai-core 容量 gate，逐檔驗證後再移除原件，保留必要連結與 rollback。沒有足夠外接空間時如實給出 `NO-GO` 和替代方案，不能改用內建暫存造成更低空間。
4. 執行具體清理／搬移前，向 Owner 提交 exact path 清單、預估回收量及回退方案供核准。本卡不是刪除不明資料、清 macOS swap／VM、關閉其他 App、重啟主機、變更 TOP10 launchd 或解除 restart-denied marker 的授權。

## 驗收契約

- 完成前後同口徑、同卷的 Foundation/raw/APFS 量測；列實際而非 `du` 推估的物理回收量、hash 驗證、連結解析、唯一資料保全與 rollback verification。
- 內建 admission 可用量須高於 `max(20 GiB, 10%)` 保留線加上**同版本代表性週期實測／投影的主機峰值占用**，並確認足夠持續餘裕；不得只靠單次 `PASS` 或當下高於保留線宣稱 readiness。10/16 歷史跌幅 3.51 GB 是最低風險參考，不是保證下一輪上限。
- 外接寫入根必須在正式容量 gate 下維持可用，無 mount／identity／quota／retention 旁路；其他專案與 out-of-scope job 未變。
- 交付一份收據給 TOP10，含 before/after、清理清單、被保全資料、回退證據與剩餘 blocker。此卡驗收 **不等於** Daily production accepted；後續 Rule24／Rule25、marker、自然週期與 Discord 送達仍須獨立驗收。

## 起點證據

- TOP10 調查交接：`docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/HANDOFF-20261019-DAILY-CAPACITY.md`
- 10/16 guard：`~/TOP10-runtime-automation-3b6ff80-20261015/logs/storage_safety/receipts/daily/daily-20261016T093004Z-12702.json`
- 10/16 失敗驗收：`docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/daily-natural-acceptance-failed-20261016.json`
- 四份搬移收據：`~/Storage-Relief-20261012/*.relocation*.json`
- ai-core 規則：`~/ai-core/rules/24-storage-capacity-safety.md`、`~/ai-core/rules/25-production-canary-readiness.md`

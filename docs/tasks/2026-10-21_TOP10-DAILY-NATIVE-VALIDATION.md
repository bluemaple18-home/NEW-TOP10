> 2026-10-22 整合後最新狀態：18檔發布保護已整合、鎖RED→GREEN；主線誤用tmp政策導致回歸中斷並留下新的工具隔離，整合版34 passed／1 failed、no-send 0/2。詳細見 `docs/evidence/TOP10-INTEGRATED-CANDIDATE-20261022/RESULT.md`；下列已通過數字屬先前版本。Production維持NO-GO。

> 2026-10-22 最新日驗證：官方10/22行情完整no-send五步PASS，TOP10／日報／payload一致，swap增量0，收尾容量PASS。正式版有發布鎖與送達保護差異，須先整合再驗收，Production維持NO-GO；未搬移至外接。見 `docs/evidence/TOP10-LATEST-NO-SEND-20261022/RESULT.md` 及 `RESTORE-PLAN.md`。

> 2026-10-22 最新狀態：開發解封已核對；內建四組回歸180 passed＋41 subtests、同版兩輪完整歷史快照no-send PASS／PASS。owned暫存已清理，正式Production NO-GO。詳細結果見 `docs/evidence/TOP10-DAILY-RESUME-20261022/RESULT.md`。下文為歷史阻塞與處置，不再代表目前工具隔離狀態。

# TOP10 Daily 原生驗證與容量回收

- objective：辨識可安全回收容量，容量准入後重跑完整四組回歸及兩輪同版獨立 no-send。
- scope：TOP10 exact-owned 冷資料與現有驗證入口；沿用工作樹修補，以檔案 digest 固定版本。
- constraints：Production 維持 NO-GO；不解除正式停跑標記、不部署、不啟動正式 Daily、不外送；不清 swap、不動其他專案、不重建 CodeGraph。保留既有工作樹修改。
- acceptance：原生 Foundation/APFS/swap/程序證據；回收前後容量、內容完整性與回退證據；四組回歸通過；兩輪 guard/完整流程/無外送/source identity/程序結束證據。任一關卡不通過，後續相依步驟停止。
- status：BLOCKED_TEST_HARNESS。Owner 已明示同意限定搬移，搬移完成；2026-10-21 16:43 台北時間 Daily 原生容量准入 PASS。回歸與兩輪 no-send 尚未完成，Production 仍 NO-GO。
- decision：歷史 CodeGraph 查詢偏向 evidence 副本，對本次缺漏以限域 rg 檢查現行入口。不沿用舊 frozen runtime driver 當作目前修補版本的驗證。
- evidence refs：docs/evidence/TOP10-DAILY-NATIVE-20261021/；/private/tmp/top10-daily-full-regression-20261021.log。

## 本輪驗證與交接

- 容量候選：Daily allowlist 總量 1,784,818 bytes，無法補足缺口；16 組 TOP10 驗證副本約 6.10 GB logical，但 APFS 共用區塊令實際回收未知。較可行的是共用 Chrome 模型冷封存 4,269,934,835 bytes／4 檔，已列 SHA256、未見開檔；外接目的卷 admission 約 77.52 GB，限定方案已提交 Owner，未搬移或刪除。
- 目前設定為 directory cache；舊 AICoreCache 映像非本次實際入口。toolchain 入口成功載入。
- 低負載原生回歸使用既有 tmp_artifact_lifecycle，256 MiB／300 秒上限，沒有啟動完整 Daily。測試期間 pytest 留下 current 連結與測試 fixture，使 symlink 數量超過既有 8 個上限；lifecycle 中止並保留 unknown isolation。不可宣稱四組回歸完成或原 74 個失敗已消失。
- 一次既有 recover dry-run 失敗：本輪 root 未產生 recover 所要求的 evidence/session metadata。未改寫或捏造缺失證據，未直接移除隔離標記。測試根詳見 receipt.json；.git/.ai-core-tmp-artifact-isolation.json 是本輪測試隔離，與正式 Daily restart-denied 不同。後續新受管測試須先合法解除此阻塞。
- 兩輪 no-send：0／2，尚未啟動。候選 26 個檔案 digest 與正式 marker/plist 前後一致，Daily not running，git diff --check PASS。
- handoff：先處理待核准冷封存範圍及測試工具恢復缺口，再重跑四組回歸；Daily 容量准入與回歸均通過後才跑兩輪 no-send。Production 仍 NO-GO。

## 2026-10-21 16:43 限定搬移完成

- authorization：Owner 回覆「好啊搬」，只承接已提出的 Chrome 舊模型封存限定搬移。
- result：4,269,934,835 bytes／4 檔已複製至 `/Volumes/VibeCode/Capacity-Reclaim-Quarantine/TOP10-capacity-20261021/chrome-model`；逐檔 SHA256／完整集合一致、外接 UUID 正確、原路徑連結解析正確後才釋放內建副本。回退方案與各階段已保存。
- capacity：內建 Foundation admission 30,973,469,888 → 35,241,272,512 bytes，觀測增量 4,267,802,624 bytes；raw 觀測增量 4,267,798,528 bytes。全系統背景活動仍會影響差值。現行 Daily measure 回 PASS，沒有更動保留線或峰值預算。
- layout：開發 checkout、正式 runtime 及其 data/artifacts/logs 均仍在內建 Data 卷；目前外接化的是設定中的共用 directory cache。這次沒有搬遷 TOP10 runtime 或修改 launchd。
- remaining blocker：靜態核對發現 `tmp_artifact_lifecycle.recovery_metadata` 僅接受 browser/review session；上一輪 generic run 不產生相應 session metadata，不能以補造證據或重複 dry-run 恢復。保留 unknown isolation，待合法的恢復處置。原四組回歸不宣稱完成，no-send 維持 0／2。
- evidence refs：`docs/evidence/TOP10-DAILY-NATIVE-20261021/chrome-model-relocation-receipt.json`、`relocation-and-layout-result.json`、`post-relocation-preflight.json`。原生讀回 Daily not running、正式 marker/plist 雜湊不變。

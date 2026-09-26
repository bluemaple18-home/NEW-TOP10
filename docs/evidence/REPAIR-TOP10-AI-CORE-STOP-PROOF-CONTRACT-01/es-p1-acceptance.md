# ES-P1 離線原型：TOP10 收件驗收

> 2026-09-27 容量整理：本目錄原始輸出與重現腳本已逐檔 SHA-256 核對後合併為 [證據壓縮包](raw-evidence-2026-09-27.tar.gz)。文中原始檔名為包內路徑；需重跑時先在本目錄執行 `tar -xzf raw-evidence-2026-09-27.tar.gz`，再依原說明操作。歷史驗證結果不變。

日期：2026-09-22。Owner「繼續吧」准入已拆分的 ES-P1；ai-core 實作，TOP10 Mainline 收件核對與重跑。範圍是合成資料，不啟動 ES client、宿主事件採集、提權、Daily 或清理程序。

## 交回前鎖定的核對條件

| 條件 | 對應原卡 | 核對方式 |
|---|---|---|
| 已知根程序先 fork，短命中間父程序再 fork，後代另 SID，父先 EXIT 仍留下 live leaf | A1／A4 | 對最小 public API 餵合成事件，leaf EXIT 前必須仍有未停止身分 |
| exec 同 PID 但身分版本改變，後續 fork／exit 歸屬跟著移轉 | A4／A5 | 不把 exec 誤當另一個獨立程序或漏掉原後代；PID reuse 不可沿用舊歸屬 |
| 在自有事件之間插入非自有事件或缺失事件 | A4／A5 | 先驗證串流完整性再依歸屬篩選，不能跳過外部事件後製造假缺口或漏掉真缺口 |
| 未 ready、錯 run／root／identity、版本或序號不足、解析失敗、collector 重啟 | A2／A5／A6 | 拒絕或永久 unknown；後續完整序列不能自行修復當輪批准 |
| 全部已知程序 EXIT、EOF、空佇列或合成 terminal 標記 | A1／A4／A6 | 只可陳述模型所見狀態，永不升格為實機完整停止／清理許可 |
| 模型及測試執行本身 | A7／A8 的離線邊界 | 親讀程式沒有宿主採集、signal、清理、網路或提權副作用；原產品 digest 不變 |

這些檢查是離線必要條件，不是 A1–A8 實機驗收，也不是原定兩名獨立 Reviewer 的替代。無產品接線、無替換既有路徑；不為本輪新增常駐管理介面。

## TOP10 接點核對

本輪 CodeGraph 已取得 `app/storage_safety.py` 的 `_spawn_verified_process_group`：目前先起等待 pipe 的 bootstrap，再捕捉程序 identity，隨即寫入 `start`。未有 ES 訂閱 ready／外層確認。未修改此函式；ES-P1 無論結果如何，都不能據此宣稱現在已安全接入。

本輪起始 SHA-256：

- TOP10 `app/storage_safety.py`：`7a74c41b618a0113dd21195845d75c5461e397ada7f653820de79d73df51a52e`。
- ai-core `scripts/tmp_artifact_lifecycle.py`：`0a2642073f4182db2d34e6e176517c49f0ecc80ee587b78e8d8928f0968523aa`。

## 收件結果

狀態：離線行為核對通過；產品安全判定維持 `BLOCKED_WITH_EVIDENCE`。ai-core 的 `es-p1-sha256.txt` 與本輪測得 digest 一致，原始 RED／GREEN 已讀；不是只依賴對方摘要。此驗收是 TOP10 Mainline 親自重跑，不冒稱兩名獨立 Reviewer。

| 交付物 | SHA-256／結果 |
|---|---|
| `<ai-core-root>/scripts/es_offline_lineage.py` | `29b30384fedd93bf4ab10d5736b8aa63fee6504b72f4fda948050bb1484bd32d` |
| `<ai-core-root>/tests/test_es_offline_lineage.py` | `98f7f7005f94c7c1db5af7fea4c5c988c27ea83e04adc84c7a5af6c3a61e65cc` |
| ai-core `es-p1-red.log` | 初始可匯入介面未保留 still-live leaf，1 項 assertion failure；不是 import error |
| ai-core `es-p1-mainline-green.log`／TOP10 [es-p1-unittest.log](raw-evidence-2026-09-27.tar.gz) | 各自執行同一組 20 項測試通過；不合算為 40 項不同案例 |
| TOP10 [verify_es_p1.py](raw-evidence-2026-09-27.tar.gz)／[es-p1-independent.json](raw-evidence-2026-09-27.tar.gz) | 額外 10 案全通過，輸出綁定上述 reducer digest |

獨立核對使用不同合成身分且不引用 ai-core test helper：六種 anchor／middle／leaf 退出排列，在最後 live identity EXIT 前保持未停止集合；集合清空本身不標記完成。合成 complete 只改模型記帳，finish／EOF 仍回 unknown。另四案將 global sequence、run、root、observer 分別破壞，後續正常退出及再次 ready 均無法重置 unknown。所有結果 cleanup_allowed=false。

讀碼核對：模組只 import dataclasses，維持合成資料集合，沒有程序查詢、signal、刪檔、網路或提權。原本兩個產品檔的結束 digest 與上方基線一致。新檔未被接到產品流程。

## 重跑命令

在 `<top10-root>` 執行，透過既有 `.venv`，離線且不安裝依賴：

```sh
UV_CACHE_DIR=/private/tmp/top10-es-p1-uv-cache uv run --offline --no-sync python -B docs/evidence/REPAIR-TOP10-AI-CORE-STOP-PROOF-CONTRACT-01/verify_es_p1.py <ai-core-root>/scripts/es_offline_lineage.py
UV_CACHE_DIR=/private/tmp/top10-es-p1-uv-cache AI_CORE_ROOT=<ai-core-root> uv run --offline --no-sync python -B -c 'import os, sys, unittest; root = os.environ["AI_CORE_ROOT"]; sys.path.insert(0, root); suite = unittest.defaultTestLoader.discover(root + "/tests", pattern="test_es_offline_lineage.py"); result = unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(not result.wasSuccessful())'
```

跨機時替換 ai-core 根目錄，並核對 digest；原始命令輸出保存在上述 JSON／log。

## 尚未證明與下一步

- 合成 `version=1`／序號起點 1／opaque token 是模型輸入約定，不能直接視為 Apple ES message version、原生序號起點或已驗證 audit token。接入時仍需版本檢查與可信轉換。
- 合成 ready 不證明訂閱成功／mute 涵蓋／根程序建立前已觀測；合成 complete 不證明尾端完整。原生 fork/exec/exit 採集與終端因果需 ES-P3 實測。
- entitlement、簽署、root、正確 responsible process 的 FDA 仍未驗證；此輪沒有採集任何宿主程序事件，沒有實機 sentinel／清理測試。
- ES-P1 到此只完成 A1／A4／A5 等條件的離線子集。下一階段為既定 ES-P3 權限與有限實機原型准入；不再追加泛查資料或無目的離線案例。TOP10 接線與整組 A1–A8／兩名 Reviewer 尚未開始。

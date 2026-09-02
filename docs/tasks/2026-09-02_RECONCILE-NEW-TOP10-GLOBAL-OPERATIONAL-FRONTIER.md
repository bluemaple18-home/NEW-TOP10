---
id: RECONCILE-NEW-TOP10-GLOBAL-OPERATIONAL-FRONTIER
status: COMPLETE / MAINLINE_ACCEPTED
type: mainline-control
date: 2026-09-02
---

# Global Operational Frontier Reconciliation

👉 [假設與目標確認] 目標：消除主線成果與控制文件之間的狀態漂移；邊界：只改 control metadata，不改產品、模型、資料、排程或 production；驗收：所有候選都被分為已整合、條件等待、歷史狀態或未 admission。

## Decision

- A5、A6 已 review GO 且已合併，更新為 `MAINLINE_ACCEPTED`。
- TPEx current-day-only chain 已整合且 review GO，舊 dossier 狀態更新為已整合。
- B0/C0/BC 與 Forecast 依 canonical backlog／merge history 收斂；不存在尚未完成的非 TimesFM implementation frontier。
- TimesFM 3 固定 `DEFERRED / LAST / HOLD`，不能因前線空白自動提前。
- 「報牌沒動」是另一個已存在的 task，本線不重複調查。
- Overlay shadow 已由舊的 `WAITING_FOR_NEW_OOS_DATES` 進入正常 `ACCUMULATING`；Chip=`22/60`、Event=`9/60`，不構成 implementation blocker。

## Acceptance evidence

- A5 fixed-SHA review：remaining `P0=0 / P1=0`；主線合併 `bb617e9`。
- A6 fixed-SHA review：remaining `P0=0 / P1=0`；主線合併 `2b9eccd`。
- A5/A6 current-tree focused regression：`77 passed`。
- TPEx chain：實作 `bc61e5d`、repair `78134f4`、receipt refresh `c081e36`；既有 reconciliation 為 `INTEGRATED_CURRENT_DAY_ONLY / REVIEW_GO`。
- Forecast merge：FM0=`ff3d30b`、FC1=`9abc159`、FC2=`02730a7`。

## Non-goals

- 不下載或執行 TimesFM。
- 不重跑已完成的 TPEx、A5、A6 卡。
- 不取代獨立 incident task，不做 push、deploy、production 或外部 write。

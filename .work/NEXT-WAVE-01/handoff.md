# Handoff: NEXT-WAVE-01

## Goal

由接收端 Mini 完成 TPEx source、Theme aggregation、Graph diffusion、feature promotion、Top10 ranking candidate 與 read-only API/UI radar。

## Constraints

- 每張卡獨立 branch/worktree/candidate。
- Mini 不得停在 preflight。
- source/promotion gate fail closed。
- repo 外 write 未授權。
- secure/yuanta 不得進 Git、log 或聊天。

## Completed actions

- 從 origin/main @ 558a04f 建立卡片 package。
- 固定 1 dispatcher + 6 task cards。
- 建立 blocking edges、共同 workflow、驗證與 evidence paths。
- 未執行任何 backlog implementation。

## Remaining work

接收端解密 ZIP、核對 MANIFEST、讀 dispatcher，從 TSKG-MFO-TPEX-01 開始逐卡執行。

## Waiting conditions

- TPEx source decision 解鎖 Theme 的 venue coverage。
- Theme acceptance 解鎖 Graph 與 Radar。
- Graph + checkpoint 解鎖 formal promotion。
- Promotion GO 才解鎖 ranking mutation。

## Limits

- 元大 prototype 只供 Windows local validation。
- 不宣稱 task thread 已在接收端建立；接收端必須自行建立可見 task 與獨立 worktree。

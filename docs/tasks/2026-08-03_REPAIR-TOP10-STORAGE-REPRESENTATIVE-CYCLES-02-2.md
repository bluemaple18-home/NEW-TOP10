---
id: REPAIR-TOP10-STORAGE-REPRESENTATIVE-CYCLES-02-2
chain_id: TOP10-STORAGE-RUNAWAY
status: ready_to_dispatch
type: repair
priority: P0
role: repair
cycle: 2
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 最後一個 P1 涉及 OS sandbox 違規的可信判定；誤報 OK 會把違規 workload 當成代表性成功週期。
reviewed_candidate: 572c789de5902a6f4da2ffaa68f64598bd124470
review_thread: 019fc62f-1bcb-7492-ad0d-e7b1c073db2d
repair_thread: 019fc639-f0cd-7c61-97ee-1d0684e6c3bf
repair_generation: 2
allowlist:
  - app/storage_safety.py
  - scripts/storage_safety.py
  - tests/test_storage_safety.py
  - docs/operations/top10-storage-safety.md
  - docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/repair-2-verification.md
  - docs/tasks/2026-08-03_REPAIR-TOP10-STORAGE-REPRESENTATIVE-CYCLES-02-2.md
forbidden_scope:
  - 任何 production data、artifacts、models 或 main checkout 未提交檔案
  - 重新執行八 job 代表性 workload、reclaim drill 或 stop-loss evidence drill
  - 瀏覽器、cookie、外部 provider、connector 或控制面
  - launchd load、enable、kickstart、restart 或 reload
  - merge、push、deploy 或發布外部訊息
---

# REPAIR-TOP10-STORAGE-REPRESENTATIVE-CYCLES-02-2｜swallowed Seatbelt denial

## Root question

Seatbelt 已阻止 scope 外寫入時，即使 child 用 `|| true` 或其他方式吞掉 I/O error，guard 能否仍可靠回傳非 OK、留下 reason 與 restart denial，而不靠可繞過的 command 字串掃描？

## 唯一 blocking finding

### TOP10-REV-P1-001｜Seatbelt denial 被 child exit 0 掩蓋

- reviewed candidate：`572c789de5902a6f4da2ffaa68f64598bd124470`
- path：`app/storage_safety.py:733`
- Review evidence：隔離 child 執行 scope 外寫入再 `|| true`；Seatbelt 確實保持 protected content 不變，但 guard 得到 `result=0`、receipt `status=OK`、`reasons=[]`。
- 風險：違反寫入契約的 workload 可被計為成功代表性週期。

## 修復契約

必須選擇並證明其中一條可信路徑：

1. 取得可與本次 child／sandbox instance 精確綁定、無競態的 Seatbelt violation telemetry；任何 denial 都轉成 STOP、persistent restart denial 與明確 reason code。
2. 若沒有可信 telemetry，validation-only 入口必須在 spawn 前限制為結構化、可驗證的 trusted harness／entrypoint contract，拒絕任意 shell、`-c`、eval 或其他可吞掉 I/O error 的任意 command seam。不得以 command 字串黑名單／substring scanning 冒充信任邊界。

無論採哪條：

- source/protected hash 必須保持不變。
- capability 或信任契約無法驗證時 fail closed。
- 原 P1-002 與 P1-003 的 GREEN 不得回歸。
- validation 變窄造成的既有 invocation 相容性變化必須在 docs/evidence 精確列出；安全優先，不得為相容而保留任意 command bypass。

## Acceptance

1. isolated fixture 執行 `outside-write || true` 或等價 swallowed error：protected hash 不變，guard 非零，receipt 非 OK，有精確 reason code 與 restart denial。
2. 合法 trusted fixture 能讀 source、只寫 sandbox 並回 OK。
3. 未登記 entrypoint、shell `-c`、eval／動態 command 或 contract digest 不符時 spawn 前拒絕。
4. Seatbelt capability/probe 缺失仍 fail closed。
5. 全部 storage tests 通過，且 metric-gap、leader-first descendant、unrelated-process isolation regression 維持通過。

## 執行順序

1. 先查 CodeGraph；失敗才限域讀 violation 判定、validation CLI 與既有 regression tests。
2. 先新增 swallowed-denial RED；不得用修改 fixture 讓 child exit nonzero 來假修。
3. 做最小 GREEN；動態測試僅限 temp roots 與短命 isolated subprocess。
4. 跑 affected storage tests、必要 pure／isolated tests、full pytest（環境 gap 精確記錄）與 `git diff --check`。
5. 更新 `repair-2-verification.md`，建立單一 candidate commit，收卡 `READY_FOR_RE_REVIEW` 或精確 `BLOCKED`。

## 禁止移動球門

- 不再處理 P2 residual。
- 不修改 production `launch_verified=false`，不啟用任何排程。
- 不重跑或重寫既有代表性 cycle evidence。
- 不自行 Review，不 merge、push、deploy。

## 收卡格式

- `status: READY_FOR_RE_REVIEW | BLOCKED`
- `base_commit: 572c789de5902a6f4da2ffaa68f64598bd124470`
- `candidate_commit: <40-char SHA>`
- `finding_addressed: TOP10-REV-P1-001`
- RED／GREEN、affected/full tests、`git diff --check`、changed files、residual risks
- live launchd 仍 disabled；無 merge／push／deploy

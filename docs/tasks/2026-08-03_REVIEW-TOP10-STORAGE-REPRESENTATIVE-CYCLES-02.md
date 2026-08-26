---
id: REVIEW-TOP10-STORAGE-REPRESENTATIVE-CYCLES-02
chain_id: TOP10-STORAGE-RUNAWAY
status: ready_to_dispatch
type: review
priority: P0
role: review
cycle: 1
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 儲存停損會控制八條排程入口並可能終止程序；需獨立高強度審查，避免錯誤放行或跨專案誤殺。
review_base: 93fb825138774a206a27792f1cbec75e0dd65abb
review_candidate: supplied_by_dispatch
superseded_candidate: 8592176769fc888be3f7fc8d8c6f53d369a93a0f
evidence_path: docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/
forbidden_scope:
  - 修改任何程式碼、設定、文件或 evidence
  - 執行代表性 workload 或寫入 production data/artifacts/models
  - 瀏覽器、cookie、外部 provider、connector 或控制面
  - launchd load、enable、kickstart、restart 或 reload
  - commit、merge、push、deploy 或發布外部訊息
---

# REVIEW-TOP10-STORAGE-REPRESENTATIVE-CYCLES-02｜strict 獨立審查

## Root question

相對 base `93fb825138774a206a27792f1cbec75e0dd65abb`，dispatch 指定的 candidate 是否正確實作 validation-only 隔離、容量／RSS／swap 停損、回收範圍與 fail-closed 判定，且 evidence 足以支持它宣稱的 `READY_FOR_REVIEW / GLOBAL NO-GO`？

## 審查邊界

- 必須確認 `HEAD` 等於 activation prompt 指定的 candidate SHA，worktree 乾淨且為獨立 worktree；不符即停止。
- 只讀審查 base → candidate diff、受影響 source/tests、policy、task card 與 `docs/evidence/TOP10-STORAGE-REPRESENTATIVE-CYCLES-02/`。
- 可執行不改 repository 的靜態檢查與測試；不得執行代表性 workload、reclaim drill、stop-loss drill 或任何 live job。
- 不得把外部權限缺失、provider-disabled、live launchd 維持 disabled 本身列為程式缺陷。Reviewer 要判斷 candidate 是否誠實 fail closed，而不是越權追求 global PASS。
- 只允許 P0／P1 阻擋；P2／P3 要列為 residual，不得移動驗收門檻。

## 必查項目

1. validation-only 入口是否確實無法被 production wrapper／launchd 誤用，且 input/output/root/symlink 邊界 fail closed。
2. process-tree RSS、swap growth、runtime、bytes、file count、host reserve 與 growth-rate 是否在正確時間取樣、觸發、終止與留下 restart denial。
3. process group 終止是否只影響目標 workload，跨平台／PID reuse／child process race 是否有 P0/P1 風險。
4. reclaim allowlist 是否可能刪除 scope 外資料，特別是 `baseline_outputs` 與 unlock policy。
5. policy schema、CLI、receipt 與 docs 是否一致；production `launch_verified=false` 是否仍不可繞過。
6. tests 是否能證明新增安全契約；full-suite 唯一失敗是否確為既有 isolated-worktree evidence gap，而非 candidate regression。
7. job matrix、verification、machine receipts 是否互相一致，是否有把 fixture、空 workload、單週期或外部未授權 job 誤報 PASS。
8. repository evidence 體積與檔案數是否本身造成新的無界增長或不可接受的追蹤負擔。

## Findings 契約

每個 finding 必須包含：

- `id`
- `severity`（P0／P1／P2／P3）
- `class`（spec 或 standards）
- 精確 `path:line`
- 可重現 evidence
- 最小修復方向
- 可判定的 acceptance

沒有證據不得列 finding。P0／P1 以外不得阻擋。

## 收卡輸出

Reviewer 最終回覆必須包含：

- `verdict: REVIEW_GO` 或 `verdict: REVIEW_NO_GO`
- `reviewed_commit: <40-char SHA>`
- `blocking_findings: <count>`
- `residual_findings: <count>`
- findings 清單或 `none`
- 實際執行的檢查／測試與結果
- 一句說明：此 verdict 是 candidate 正確性判定，不代表授權啟用 live launchd。

`REVIEW_GO` 僅代表 candidate 正確、證據與 `GLOBAL NO-GO` 宣稱相符；它不會把任何 job 的 `launch_verified` 改成 true，也不授權 merge、push、deploy 或排程啟用。

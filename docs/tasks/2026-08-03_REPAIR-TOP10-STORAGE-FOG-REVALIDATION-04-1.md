---
id: REPAIR-TOP10-STORAGE-FOG-REVALIDATION-04-1
chain_id: TOP10-STORAGE-FOG-REVALIDATION-FRESH
status: ready_for_review
blocker: SWAP_GROWTH_BUDGET_EXCEEDED
blocker_detail: "raw guard swap stop 保持有效；post-run cadence contract 亦失敗。cycle 2、retry 與 fresh workload 均禁止。"
type: implementation
priority: P0
role: repair
cycle: 1
generation: 2
reviewed_generation_1_candidate: bd7fa8d67409e7db439c3a3f8640ae18aaf8472b
remaining_finding: FOG-REV04-P1-002
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: sampler cadence 是高 RSS workload 的 fail-closed 安全邊界，且現有 evidence 必須在不重跑 workload 下誠實收斂；需高強度修復與測試。
source_candidate: aa2fc1eeeb23d36a992b8ad40bd34e8df9cd7147
review_status: REVIEW_NO_GO
review_thread: 019fc6fc-7a02-79b1-bc99-856efa7cb2ac
blocking_findings:
  - FOG-REV04-P1-002
resolved_in_generation_1:
  - FOG-REV04-P1-001
allowed_paths:
  - app/storage_safety.py
  - tests/test_storage_safety.py
  - docs/tasks/2026-08-03_TOP10-STORAGE-FOG-REVALIDATION-04.md
  - docs/tasks/2026-08-03_REPAIR-TOP10-STORAGE-FOG-REVALIDATION-04-1.md
  - docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-04/cycle-1.json
  - docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-04/verification.md
  - docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-04/repair-1-verification.md
forbidden_scope:
  - 重跑 fog workload、cycle 1、cycle 2 或任何代表性 workload
  - 清除、修改或復用 fresh／前代 sandbox、marker、contract 或 restart denial
  - 提高、放寬、繞過或重解釋任何 storage／RSS／swap／cadence ceiling
  - 修改 fog business logic、其他七個 job、production data/artifacts/models 或主工作區既有 dirty 檔
  - 瀏覽器、cookie、外部 provider、connector 或控制面
  - launchd load、enable、kickstart、restart 或 reload
  - merge、push、deploy、發布外部訊息或自審
---

# REPAIR-TOP10-STORAGE-FOG-REVALIDATION-04-1｜收斂狀態與 live sampler cadence

## Root question

能否在完全不重跑 fog workload、不清除 restart denial 的前提下，誠實修正 fresh candidate 的
卡片狀態與 cadence evidence，並把 storage guard 改成 monotonic absolute-deadline 取樣；任何無法
維持最長 60 秒 cadence 的情況都 reason-coded fail closed，避免監控 overhead 累加成安全盲區？

## 固定前提

- Parent candidate 精確為 `aa2fc1eeeb23d36a992b8ad40bd34e8df9cd7147`。
- 原始 cycle 1 與 raw receipt 不可改寫：guard stop reason 是
  `SWAP_GROWTH_BUDGET_EXCEEDED`，guard exit `70`，child exit `0`，cycle 2／retry 未執行。
- 原始三段 live gap 為約 `60.485444` 與 `61.718713` 秒；這是額外的 post-run cadence
  contract violation，不能刪除、四捨五入成 60 秒內或冒充 raw guard reason。
- Fresh denial digest、marker／contract／entrypoint／runner digest、前代 sandbox 與 main protected hashes必須保持不變。
- 本 Repair 只修復兩個 blocking finding；不得藉機追求 fog PASS 或兩週期完成。

## Finding trace 與 Acceptance

### AC-1｜FOG-REV04-P1-001：狀態不可再派工

Given candidate 已因 swap 超限停止且 denial 禁止自動清除
When Repair 收斂 implementation 卡
Then frontmatter 必須是 `status: ready_for_review`、`blocker: SWAP_GROWTH_BUDGET_EXCEEDED`，
blocker detail 明示 cadence violation、cycle 2／retry／fresh workload 均禁止；不得把卡片標成 completed、PASS或可再次派工。

### AC-2｜FOG-REV04-P1-002：monotonic cadence fail closed

Given policy `sample_interval_seconds = N`
When child 持續存活、snapshot／wait／scheduler 產生 overhead
Then scheduled live samples 以 monotonic absolute deadline 驅動，不得每輪從工作完成後重新等待完整 N；
若實際連續 scheduled live sample gap 大於 N，必須加入穩定明確的
`LIVE_SAMPLE_CADENCE_EXCEEDED` stop reason、終止同一 verified PGID、保存 restart denial，guard return `70`。

至少補下列 regression：

1. 可控制 clock／wait／sample overhead，證明 absolute deadline 不累積 drift。
2. 故意讓取樣或 scheduler 超過 cadence，證明 reason-coded stop、denial 與 exit `70`。
3. first-write sample、immediate sample、fast child、max runtime、swap/RSS stop、PGID termination 與既有 receipt契約不退化。
4. cadence 計算只使用 monotonic time；wall-clock timestamp只能作 evidence，不可作安全判斷。

### AC-3｜既有 evidence 誠實補記

Given committed `cycle-1.json` 是 bounded derived evidence、raw receipt留在 local sandbox
When 補記本 Review finding
Then保留 raw guard `reasons=[SWAP_GROWTH_BUDGET_EXCEEDED]` 不變，另以明確欄位保存
`LIVE_SAMPLE_CADENCE_EXCEEDED`、兩段精確 gap、最大 gap與 ceiling；verification 明示這是 post-run
evidence finding，代表本次監控契約也失敗，未來必須先通過 Repair Review 與新 fresh activation才能重跑。

## 實作邊界

- source decision 前先查 CodeGraph；未初始化／無結果才限域 `app/storage_safety.py`、
  `tests/test_storage_safety.py` 與相關 receipt helper。
- 不新增 dependency、不改 policy schema ceiling、不把 60 改成較大值、不用浮點容忍把 61.7 秒判為通過。
- cadence 檢查必須掛在 production guard共用路徑，不能只修 fog adapter或 evidence formatter。
- 任何新 stop reason 必須走既有 dedupe、PGID termination、restart denial與 receipt路徑。
- 測試不得 sleep 60 秒；使用 deterministic fake clock／process wait／sample hook或等價受控方法。
- 不改 `docs/evidence/.../preflight.md`，不觸碰 raw local evidence。

## 驗證

至少執行：

```text
PYTHONDONTWRITEBYTECODE=1 <venv-python> -B -m pytest -q -p no:cacheprovider \
  tests/test_storage_safety.py tests/test_fog_storage_validation.py
```

另跑 full suite、machine JSON parse／gap 重算、denial／marker／protected digest唯讀核對與
`git diff --check`。若 full suite 仍只有既有 ledger evidence gap，精確記錄，不得掩蓋新 regression。

## 交付

- 單一 generation-2 candidate commit，parent 精確為
  `bd7fa8d67409e7db439c3a3f8640ae18aaf8472b`。
- `repair-1-verification.md` 必須 trace `FOG-REV04-P1-001`／`002` 到 tests與 changed files。
- changed files 嚴格限於 allowlist；worktree clean。
- 收卡只可 `READY_FOR_REVIEW / FOG_NO_GO_SWAP_GROWTH_BUDGET_EXCEEDED` 或
  `BLOCKED / <REASON>`。

完成後回主線；由主線把同一 Reviewer `019fc6fc-7a02-79b1-bc99-856efa7cb2ac` 喚醒做 targeted re-review。Repair 不得
自審、不得建立 replacement Reviewer、不得重跑 workload、不得 merge／push／deploy或啟用排程。

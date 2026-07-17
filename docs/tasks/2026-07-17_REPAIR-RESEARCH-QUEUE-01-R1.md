# REPAIR-RESEARCH-QUEUE-01-R1

## 任務

只修復 `REVIEW-RESEARCH-QUEUE-01` 對 commit `fea9307224d3dccef28428773d09cf061491c5e0` 提出的三項 findings，不擴大範圍。

## Findings

1. 依 post-run eligibility/actionability 建立 queue，讓第二次仍為 `partial_needs_followup` 的 topic 留在 queue，並由 24 小時 cooldown 阻止立即重跑。
2. history fallback 只接受可證明真實 execute 的 row；拒絕 `execute=false` 或缺少 `execute` 的 row，保留明確 `execute=true` legacy scalar `selected_topic_id` 相容性。
3. verifier 與架構文件移除 `--rerun`／`--include-rejected` 可繞過 manager policy 的舊語意。

## 驗收

- run1 → run2 partial → 仍在 queue → 24h cooldown → run3 lifecycle。
- cooling／exhausted／rejected／empty queue 均 fail closed。
- dry-run 與缺 `execute` history row 不可作 fallback。
- `execute=true` 且使用 legacy scalar `selected_topic_id` 的 history row 可作 fallback。
- 受影響單元測試、`scripts/verify_autonomous_research.py`、`git diff --check` 通過。

## 邊界

- 不改模型、排名、promotion。
- 不刪除或覆寫既有 artifact。
- 不 merge、push、deploy。

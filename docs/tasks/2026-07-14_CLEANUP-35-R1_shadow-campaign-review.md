# CLEANUP-35-R1｜獨立審查 shadow research campaign

## Chain

- chain_id：`CLEANUP-35`
- card：`R1`
- candidate commit：`f9b4a71`
- candidate branch：`codex/cleanup-35-i1`
- parent card：`docs/tasks/2026-07-14_CLEANUP-35_shadow-research-campaign.md`

## 任務目的

獨立審查 `f9b4a71` 是否完整保留四支舊 shadow research 入口的 CLI、command plan、artifact/manifest、failure semantics 與 dry-run 零副作用契約。只做 review 與可重現驗證，不修改候選實作。

## 必讀

- `docs/tasks/2026-07-14_CLEANUP-35_shadow-research-campaign.md`
- `.work/CLEANUP-35/result.md`
- `.work/CLEANUP-35/evidence/parity.json`
- candidate diff：`9748b95..f9b4a71`
- `scripts/run_shadow_research_campaign.py`
- `tests/test_shadow_research_campaign.py`
- 四支被刪除舊入口（由 candidate parent `9748b95` 讀取）
- `~/ai-core/skills/code-review-gate/SKILL.md`

## Review 範圍

- Spec axis：四個 stage/profile、舊 CLI/default、輸出 path/schema/console/exit、TSV 與 Markdown、全域/stage dry-run、逐 stage status
- Standards axis：subprocess 安全、失敗是否被掩蓋、路徑/模型 hash guard、無真實 replay、測試是否真的覆蓋 valid/missing/failure
- 搜尋 stale 舊入口引用與 lifecycle/reference audit 行為
- 核對 daily 四檔完全未改

## 禁止事項

- 不得修改 candidate code、tests、config 或既有 evidence
- 不得執行真實 replay、shadow ranking、training 或長跑 subprocess
- 不得 merge、push、deploy、修改 production artifact/model/ranking
- 驗證只能使用靜態 diff、focused tests、dry-run、mocked subprocess、strict audits 與完整 pytest

## 輸出

- `.work/CLEANUP-35-R1/review.md`
- `.work/CLEANUP-35-R1/status.md`
- 若有 findings：逐項寫 `finding_id / severity / path:line / trigger / risk / required_fix / verification`
- verdict 僅能是 `GO` 或 `NO-GO`
- 建立單一 review-evidence commit，不修改 candidate

## 下一張卡尾巴

`status.md` 必須獨立保留：

- `root question`
- `candidate commit`
- `verdict`
- `open findings`
- `next_card_type`：`FIX`（NO-GO）或 `MAINLINE_ACCEPTANCE`（GO）
- `next_card_scope`
- `required_evidence`
- `recommended_model`
- `waiting_condition`

若 `NO-GO`，只提出 bounded findings，交由新的 repair 對話框處理；Reviewer 不得自行修正。

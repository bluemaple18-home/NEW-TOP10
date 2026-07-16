---
card_id: RESEARCH-AUDITOR-01
title: TOP10 Research Auditor MVP
status: REVIEW_NO_GO
ownership: mainline
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 需要跨 ETL、ranking、artifact 與驗證契約做最小架構判斷；不涉及 production 交易變更。
source_kind: working_tree
main_cwd: <repo-root>
worktree_path: <repo-root>
thread_status: local-card-only
---

# RESEARCH-AUDITOR-01

## 目標

建立一個只讀的 TOP10 Research Auditor MVP，檢查既有 ranking、features、fundamental 與 backtest artifact，輸出可追溯的研究稽核報告。

## Ownership / allowlist

- `app/`：僅在確認既有 public interface 後新增最小 auditor 模組。
- `scripts/`：新增一個可重複執行的 auditor CLI（若需要）。
- `tests/`：新增行為測試。
- `artifacts/`：僅寫入明確指定的 research/audit 輸出位置。
- 本卡片本身：`docs/tasks/2026-07-17_RESEARCH-AUDITOR-01.md`。

## Forbidden scope

- 不修改 production ranking、LightGBM 權重或模型檔。
- 不修改 ETL 資料來源與欄位契約。
- 不呼叫 Claude/OpenAI API，不引入外部 connector、MCP 或 plugin runtime。
- 不將 LLM 判斷作為投資建議或自動交易決策。
- 不清理或覆蓋工作區既有、與本卡無關的 dirty changes。

## MVP acceptance criteria

1. 輸入既有 ranking/features/backtest 路徑即可執行。
2. 報告至少包含：輸入 artifact snapshot、缺值／欄位問題、日期一致性、推薦理由與證據欄位一致性、production mutation=false。
3. 輸出 schema 可由 deterministic verifier 驗證；錯誤要 fail loud。
4. 預設為 research-only，不能寫入 production ranking 或 models。
5. 有最小單元測試，並通過 `git diff --check` 與受影響驗證。

## Workflow contract

```text
existing artifacts
  -> deterministic auditor
  -> structured audit report
  -> human review
```

LLM／Agent 若未來加入，只能解讀已驗證證據並產生草稿；資料日期、欄位、缺值、路徑與 mutation guard 由 deterministic code 負責。

## Verification / evidence

- 測試：`tests/` 中 auditor behavior tests。
- CLI 驗證：auditor dry-run／fixture replay。
- 格式：`git diff --check`。
- 證據預計：`artifacts/research_audits/`，不得覆蓋 production artifact。

## Slices

1. 盤點現有 artifact 與 public interface。
2. 建立只讀 audit contract 與 fixture-based deterministic checks。
3. 建立 CLI／報告輸出。
4. 執行測試、diff 與受影響 gate；交付 candidate，等待獨立 review。

## Progress evidence

- 已新增 `app/research_auditor.py`：deterministic ranking／reasons／stock coverage／artifact snapshot checks。
- 已新增 `scripts/run_research_auditor.py`：research-only CLI，直接執行時可載入 repo package。
- 已新增 `tests/test_research_auditor.py`：3 個行為測試通過。
- 驗證：`.venv/bin/python -m pytest -q tests/test_research_auditor.py` → `3 passed`。
- 驗證：`.venv/bin/python -m py_compile app/research_auditor.py scripts/run_research_auditor.py` → pass。
- 驗證：`git diff --check` → pass。
- Candidate commit：`f0fe163c30d6cd4bb6edcde5a6e8e0a107e23734`。
- Candidate scope：本卡 4 個檔案；既有其他 dirty paths 未納入。
- Review evidence：`.work/RESEARCH-AUDITOR-01/review/review_result.md`。
- 下一狀態：`REPAIR_READY`，repair card：`docs/tasks/2026-07-17_RESEARCH-AUDITOR-01R1.md`。

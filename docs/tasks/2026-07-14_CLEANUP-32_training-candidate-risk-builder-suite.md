# CLEANUP-32｜收斂 training-candidate risk builder

## 任務目的

依 CLEANUP-24 的 MERGE-05，把 training-candidate risk attribution 與 risk-control report builder 收斂為一支具名 profile builder；逐欄保留兩份研究決策資料與輸出契約後，才退休舊入口。

## 請讀

- `.work/CLEANUP-24/evidence/retirement-plan.json` 的 `MERGE-05`
- `scripts/build_training_candidate_risk_attribution.py`
- `scripts/build_training_candidate_risk_control_report.py`
- `scripts/verify_training_candidate_risk_reports.py`
- `config/script_lifecycle.yaml`

## 可改檔案

- 新增 `scripts/build_training_candidate_risk_review.py`
- 刪除兩支舊 builder
- 新增 focused parity tests
- 更新 `config/script_lifecycle.yaml`
- 新增 `.work/CLEANUP-32/status.md`、`result.md`、`evidence/parity.json`

## 必須保留的契約

- profile：`attribution`、`risk_control`
- attribution 的 candidate-root/summary 輸入解析、headline、trade/matrix attribution、risk hypotheses、next experiments、decision 與 research-only boundary
- risk_control 的 variant/peer 掃描、missing、ranking、decision、next 與 research-only boundary
- 每個 profile 的 schema、完整 JSON、同名 Markdown、預設 output、console JSON 與 exit code
- valid 與 missing/invalid fixture 的 normalized JSON、Markdown bytes、console、exit code frozen parity
- CLEANUP-31 新 verifier 對兩個 profile 產物的 consumer gate

## 不可改

- 每日報牌、publish、模型、權重、正式 ranking、launchd、plist、automation
- 既有研究 artifact、其他 builder/verifier 或研究結論

## 驗收證據

- old/new valid 與 missing/invalid parity，涵蓋兩個 profile 的完整輸出與 CLI 契約
- focused tests、reference/lifecycle strict-new、完整 pytest、`git diff --check`
- daily 四檔 SHA-256 與 CLEANUP-31 基線完全相同

## 交付限制

- 只建立單一 atomic commit，不 merge、不 push。
- worktree 無 `.venv` 時借用主線既有 `.venv`；不得下載或建立新環境，不得把本機絕對路徑寫進共享文件。
- parity 無法證明時保留舊入口並回報 blocker，不可硬刪。

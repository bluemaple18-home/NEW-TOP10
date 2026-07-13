# CLEANUP-31｜收斂 training-candidate risk verifier

## 任務目的

依 CLEANUP-25 的 B3 計畫，把 training-candidate risk attribution 與 risk-control verifier 收斂為一支具名 profile verifier；完整保留兩者不同的證據面、check 結果與 CLI 契約後，才退休舊入口。

## 請讀

- `.work/CLEANUP-25/evidence/verifier-retirement-plan.json` 的 `MG-TRAINING-CANDIDATE-RISK` 與 B3
- `scripts/verify_training_candidate_risk_attribution.py`
- `scripts/verify_training_candidate_risk_control_report.py`
- 對應的兩支 builder
- `config/script_lifecycle.yaml`

## 可改檔案

- 新增 `scripts/verify_training_candidate_risk_reports.py`
- 刪除兩支舊 verifier
- 新增一支 focused parity test
- 更新 `config/script_lifecycle.yaml`
- 新增 `.work/CLEANUP-31/status.md`、`result.md`、`evidence/parity.json`

## 必須保留的契約

- profile：`attribution`、`risk_control`
- 每個 profile 的 verification schema version、完整 checks 名稱／順序／value／ok、summary、artifact 路徑
- valid 與 invalid fixture 的完整 normalized payload parity
- CLI 必填參數、預設 output、console JSON 與 exit code
- attribution：三個 input 檔存在、return/drawdown delta、sector/rank/month attribution、至少三個 hypotheses/experiments、promotion false
- risk_control：至少五個 variants、每列 return/drawdown、decision wording/reason、至少兩個 next steps、promotion false

## 不可改

- 每日報牌、publish、模型、權重、正式 ranking、launchd、plist、automation
- builder 產出契約、既有研究 artifact、其他 verifier 或研究結論

## 驗收證據

- old/new valid／invalid parity，涵蓋兩個 profile 的 payload、console 與 exit code
- focused tests、reference/lifecycle strict-new、完整 pytest、`git diff --check`
- daily 四檔 SHA-256 與 CLEANUP-30 基線完全相同

## 交付限制

- 只建立單一 atomic commit，不 merge、不 push。
- worktree 無 `.venv` 時可借用主線既有 `.venv`，不得下載或建立新環境，也不得把本機絕對路徑寫進共享文件。
- parity 無法證明時保留舊入口並回報 blocker，不可硬刪。

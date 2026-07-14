# CLEANUP-33｜收斂 operational-rule builder

## 任務目的

依 CLEANUP-24 的 MERGE-03，把 operational-rule candidate 與 experiment report builder 收斂為一支具名 profile builder；完整保留 policy、risk guard、rank 與 shadow 結論後，才退休舊入口。

## 請讀

- `.work/CLEANUP-24/evidence/retirement-plan.json` 的 `MERGE-03`
- `scripts/build_operational_rule_candidate_report.py`
- `scripts/build_operational_rule_experiment_report.py`
- `config/script_lifecycle.yaml`

## 可改檔案

- 新增 `scripts/build_operational_rule_review.py`
- 刪除兩支舊 builder
- 新增 focused parity tests
- 更新 `config/script_lifecycle.yaml`
- 新增 `.work/CLEANUP-33/status.md`、`result.md`、`evidence/parity.json`

## 必須保留的契約

- profile：`candidate`、`experiment`
- candidate：candidate/production comparison、exit/rank/regime/concentration/shadow summaries、next experiments、policy 與 production boundary
- experiment：risk guard、rank stability、sector guard、shadow monitor、next actions 與 production boundary
- 每個 profile 的 schema、完整 JSON、Markdown bytes、預設 output、console JSON 與 exit code
- valid 與 missing fixture 的 old/new normalized JSON、Markdown、console、exit code parity
- 不得把兩份報告壓成同一套簡化 schema；profile 僅負責 dispatch

## 不可改

- 每日報牌、publish、模型、權重、正式 ranking、launchd、plist、automation
- 既有研究 artifact、其他 builder/verifier 或研究結論

## 驗收證據

- old/new valid/missing parity，涵蓋兩個 profile 的完整輸出與 CLI 契約
- focused tests、reference/lifecycle strict-new、完整 pytest、`git diff --check`
- daily 四檔 SHA-256 與 CLEANUP-32 基線完全相同

## 交付限制

- 只建立單一 atomic commit，不 merge、不 push。
- worktree 無 `.venv` 時借用主線既有 `.venv`；不得下載或建立新環境，不得把本機絕對路徑寫進共享文件。
- parity 無法證明時保留舊入口並回報 blocker，不可硬刪。

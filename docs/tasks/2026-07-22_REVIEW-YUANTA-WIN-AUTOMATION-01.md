---
task_id: REVIEW-YUANTA-WIN-AUTOMATION-01
status: REVIEW_GO
final_review_sha: 5505a7e
card_type: independent-security-correctness-review
reviewed_sha: d765cb5
ownership: independent reviewer
allowlist:
  - docs/evidence/REVIEW-YUANTA-WIN-AUTOMATION-01/**
  - .work/REVIEW-YUANTA-WIN-AUTOMATION-01/**
  - docs/tasks/2026-07-22_REVIEW-YUANTA-WIN-AUTOMATION-01.md
risk: credentials, certificate import, GUI automation, Windows-only behavior
---

# REVIEW-YUANTA-WIN-AUTOMATION-01

請對 candidate `d765cb5` 執行獨立 Security／Correctness Review。只審不修，不得執行真實登入、憑證匯入、外部交易或敏感截圖。

## 必查

- candidate diff 僅含 implementation allowlist，沒有 prototype、binary、PFX、登入資料、runtime log 或 screenshot。
- 以專案既有 `.venv` 重跑 py_compile、static verifier、grep 人工判讀與 `git diff --check`。
- dry-run／`-Execute` 邊界、Windows-only fail-closed、動態 process/window 定位、UI Automation ID。
- `PSCredential`／互動提示／明示 env fallback 的 secret lifecycle；command line、log、JSON output 不洩漏值。
- PFX 只複製、不以明文參數自動匯入；真實 import/login 需使用者當次授權。
- screenshot 必須避免敏感視窗並要求 acknowledgement。
- README 的支援平台、參數、rollback、Windows live 未驗證狀態是否誠實。

## Verdict

在 `docs/evidence/REVIEW-YUANTA-WIN-AUTOMATION-01/review.md` 記錄 reviewed SHA、命令、findings 與 `REVIEW_GO` 或 `REVIEW_NO_GO`，並提交 review commit。若 NO_GO，只列可重現修復需求，不得修改 implementation。

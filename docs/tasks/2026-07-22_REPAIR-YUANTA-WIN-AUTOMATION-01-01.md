---
task_id: REPAIR-YUANTA-WIN-AUTOMATION-01-01
card_type: repair
review_no_go_commit: f9b7503
original_candidate: d765cb5
ownership: repair executor
allowlist:
  - tools/yuanta_windows/**
  - scripts/verify_yuanta_windows_helpers.py
  - docs/evidence/YUANTA-WIN-AUTOMATION-01/**
  - .work/YUANTA-WIN-AUTOMATION-01/**
  - docs/evidence/REPAIR-YUANTA-WIN-AUTOMATION-01-01/**
  - .work/REPAIR-YUANTA-WIN-AUTOMATION-01-01/**
  - docs/tasks/2026-07-22_REPAIR-YUANTA-WIN-AUTOMATION-01-01.md
risk: credential lifecycle and screenshot privacy
---

# REPAIR-YUANTA-WIN-AUTOMATION-01-01

完整讀原卡與 `docs/evidence/REVIEW-YUANTA-WIN-AUTOMATION-01/review.md`，只修下列三個 P1，不擴張功能，也不得執行真實登入、憑證匯入或截圖。

## 固定修復

1. Env fallback：兩個 process env secrets 一律在 `finally` 清除；部分輸入 fail closed；conversion／cleanup 例外路徑也不得留下值。補可在非 Windows 執行的 synthetic/source-level regression。
2. UIA PIN：誠實承認 UI Automation `ValuePattern.SetValue(string)` 無法保證 managed string 零化；最小化 plaintext lifetime，所有 references 在 `finally` 釋放，不得宣稱完整 memory zeroization，補 Windows failure-path test plan。
3. Screenshot：停止 full-primary-screen 模式。改成只擷取由使用者明確指定、經 title/process/handle 唯一驗證且標記非敏感的單一 allowlisted window；任何 dialog／owned window／多重視窗／不可驗證 surface 都 fail closed。補另一 process dialog 與 multi-monitor／surface 邊界的 synthetic verifier coverage。

## 驗證與交付

- 專案既有 `.venv` 執行 py_compile、static/synthetic verifier、secret scan、`git diff --check`。
- Windows live 仍可維持 NOT_RUN，但不可冒充 PASS。
- 產出 repair evidence，candidate commit 只含 allowlist。
- 交付 repair candidate SHA 後，回原 Reviewer task `019f88d0-f4e8-7b61-840e-81bb717af1a4` re-review。

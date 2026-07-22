---
task_id: YUANTA-WIN-AUTOMATION-01
card_type: secure-implementation
ownership: receiving Mini
allowlist:
  - tools/yuanta_windows/**
  - scripts/verify_yuanta_windows_helpers.py
  - docs/tasks/2026-07-22_YUANTA-WIN-AUTOMATION-01_secure_windows_helpers.md
  - docs/evidence/YUANTA-WIN-AUTOMATION-01/**
  - .work/YUANTA-WIN-AUTOMATION-01/**
  - .gitignore
thickness: strict
risk: credentials, certificate import, GUI automation, Windows-only behavior
model: receiving Mini
reasoning: medium
model_reason: User selected Mini; strictness comes from credential and external-write risk, while scope remains bounded.
---

# YUANTA-WIN-AUTOMATION-01 Secure Windows Helpers

任務ID：YUANTA-WIN-AUTOMATION-01
卡片類型｜派工對象：Secure Implementation + Integration｜另一台電腦的 Mini
請讀：本卡、AGENTS.md、.work/MINI-REMAINING-01/evidence/yuanta_local_prototype_redacted.md
任務目的：重建可攜、安全、可驗證的元大 Windows 輔助工具，取代本機含祕密的未提交 prototype
證據路徑：docs/evidence/YUANTA-WIN-AUTOMATION-01/、.work/YUANTA-WIN-AUTOMATION-01/evidence/

## 需要支援的行為

- 開啟元大指定公開頁面。
- 把安裝程式與使用者明確提供的憑證來源放到可設定的工作目錄。
- 啟動／定位 API 測試軟體登入視窗。
- 以本地安全輸入來源完成登入欄位操作。
- 產生可設定輸出路徑的診斷截圖。

## Security invariants

- Git、task card、logs、process command line、test fixture 與 screenshot 不得含真實帳號、PIN、PFX 密碼、私鑰或憑證內容。
- 不得硬編碼 PID、使用者名稱、Downloads、Public Desktop 或其他單機絕對路徑。
- credentials 必須由執行時本地安全來源取得；優先 Windows Credential Manager／互動安全提示。環境變數只能作明示的測試或臨時 fallback，且不得回顯。
- PFX 密碼不得作為 certutil 明文參數保存於 script 或 log。若 Windows API 無法安全完成，將憑證匯入改為使用者互動步驟並清楚提示。
- screenshot 前必須遮罩或避開密碼欄、憑證內容與其他敏感資料。
- 真實憑證匯入與真實登入是外部 write，執行前取得使用者明確授權。
- 原 prototype 已出現可用祕密；不得搬入 Git。建議使用者另行輪替該登入祕密。

## Implementation requirements

- 放在 tools/yuanta_windows/，不要散落 repo root。
- 提供 README，列支援平台、參數、安全邊界、dry-run 與 rollback。
- 提供至少 static verifier，掃描硬編碼 credentials、PID、使用者專屬絕對路徑與敏感輸出。
- 能在非 Windows CI 執行的檢查不得依賴 GUI。
- Windows live verification 若無環境，須留下精確未驗證項與可重跑命令；不得虛報 PASS。

## Forbidden scope

- 不提交既有六個 root-level prototype。
- 不提交 setup.exe、PFX、ZIP、登入資料、vm_screen.png 或 runtime logs。
- 不自動關閉防毒、不修改系統安全政策、不繞過憑證驗證。
- 不在未授權下執行真實登入、憑證匯入或對外下單。

## Verification

至少包含：

```bash
cd <repo-root>
uv run python scripts/verify_yuanta_windows_helpers.py
git grep -n -E '(password|pin|account|pfx)' -- tools/yuanta_windows scripts/verify_yuanta_windows_helpers.py
git diff --check
```

grep 命中必須人工判讀，變數名稱與安全文件可以存在，但不得有真實值。Windows 實機命令由實作後 README 定義。

## Acceptance

- candidate commit 只含 allowlist，且 secret scan 無真實祕密。
- 獨立 Security/Correctness Reviewer 對 candidate SHA 給 REVIEW_GO。
- mainline acceptance 記錄 static/synthetic 與 Windows live verification 的真實狀態。
- 若 Windows live verification 尚待使用者授權，可將功能標為 EXPERIMENTAL，但不得宣稱完整 live acceptance；主線是否整合由接收端依風險證據判定。

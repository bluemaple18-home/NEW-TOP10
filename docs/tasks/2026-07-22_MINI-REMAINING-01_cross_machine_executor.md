---
task_id: MINI-REMAINING-01
card_type: cross-machine-executor
ownership: Mini on the receiving computer
thickness: strict
risk: cross-machine integration, credentials, Git cleanup
model: receiving Mini
reasoning: medium
model_reason: User explicitly selected Mini; the card makes the work bounded and keeps review/acceptance gates unchanged.
base_sha: 406b8119b543bdb100d23463c7379cd8dabf8d10
---

# MINI-REMAINING-01 跨機收尾執行卡

任務ID：MINI-REMAINING-01
卡片類型｜派工對象：跨機 Executor / Integrator｜另一台電腦的 Mini
請讀：AGENTS.md、.work/current/status.md、.work/current/handoff.md、.work/current/context_manifest.md、本卡與兩張子卡
任務目的：接手這台尚未收尾的兩條工作，完成實作、驗證、獨立 Review／必要 Repair、mainline acceptance、整合 main、push 與安全 cleanup
證據路徑：.work/MINI-REMAINING-01/evidence/、docs/evidence/SHADOW-RUN-01/、docs/evidence/YUANTA-WIN-AUTOMATION-01/

## 使用者授權與完成定義

你是執行者與整合者，不是唯讀盤點員。Preflight 只是第一步；除非命中本卡「真正 blocker」，不得在回報 status、branch、dirty files 或測試清單後停止。

依序完成：

1. Preflight：確認 repo、最新 origin/main、獨立 worktree／branch、dirty files 與 do-not-touch。
2. 完成 SHADOW-RUN-01 candidate，執行指定驗證。
3. 建立獨立 Review；NO_GO 時開 Repair，修完回原 Reviewer re-review。
4. REVIEW_GO 後做 mainline acceptance，整合 main、重跑驗證、push。
5. 完成 YUANTA-WIN-AUTOMATION-01 的安全化實作與可執行驗證；需要 Windows 實機或憑證時依卡片界線處理。
6. 同樣完成 Review／Repair／acceptance／main integration／push。
7. 確認 candidate commits 已整合、無獨有未提交成果、證據已保存後，移除已整合的任務 worktree；刪 branch 前再次確認無 unique commit。可見 task 只 archive，不刪除。
8. 更新 .work/current/result.md，回報 integrated commit、origin/main、驗證、未驗證原因、剩餘風險與 cleanup receipt。

## 子卡與順序

- 第一張：docs/tasks/2026-07-22_SHADOW-RUN-01_shadow_feature_experiments.md
- 第二張：docs/tasks/2026-07-22_YUANTA-WIN-AUTOMATION-01_secure_windows_helpers.md

兩張卡邏輯獨立；不要混成同一 candidate commit。第一張完成並推上 main 後再處理第二張。

## Forbidden scope

- 不得修改 production RankingPolicy、risk_adjusted_score、模型權重或直接 promote feature。
- 不得把任何帳號、PIN、PFX 密碼、私鑰、憑證、使用者專屬路徑或敏感截圖提交到 Git。
- 不得覆蓋接收端既有 dirty files；不確定 ownership 時先隔離保存並回報。
- 不得用 force push、reset --hard 或刪除未證明已整合的 branch/worktree。
- 不得把本機絕對路徑寫入共享 handoff 或可複製命令。

## 真正 blocker

只有下列狀況可以停止並回報：

- 缺少 GitHub 存取權或 push 被拒。
- candidate 經最多兩代 Repair 仍為 REVIEW_NO_GO。
- 接收端有同檔 dirty changes，繼續會覆蓋不相關成果。
- 元大實機驗證需要使用者在 Windows 主機提供本地憑證／登入，且無法用 synthetic/static verification 替代。
- 即將執行憑證匯入、真實登入或其他外部 write，但未取得使用者明確授權。

若只卡 live Windows 驗證，仍須先完成不需祕密的安全化實作、static/synthetic tests、Review 與可安全整合部分；不得因此只做盤點。

## 接手命令

```bash
cd <repo-root>
git fetch --all --prune
git switch --track origin/codex/top10new-mini-remaining-handoff-20260722-20260722-151430
git status --short --branch
git worktree list
```

若本機已有同名 local branch，改用新的獨立 worktree 從該 remote branch 建立，不要覆蓋既有工作目錄。

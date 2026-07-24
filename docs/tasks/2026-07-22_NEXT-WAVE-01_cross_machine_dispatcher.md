---
card_id: NEXT-WAVE-01
chain_id: TOP10-NEXT-WAVE-20260722
status: DISPATCH_COMPLETED
type: cross-machine-dispatcher
owner: receiving Mini
model: receiving Mini
reasoning: medium
model_reason: 使用者明確指定另一台 Mini 執行；以 bounded cards、獨立 Review 與 gates 控制風險。
base_sha: 558a04f82a9ff164ae6a95a126f8a354bd33ebab
worktree: receiving_host_must_provision
---

# NEXT-WAVE-01 跨機後續工作總派工卡

任務ID：NEXT-WAVE-01
卡片類型｜派工對象：跨機 Executor / Integrator｜另一台電腦的 Mini
請讀：AGENTS.md、本卡、.work/NEXT-WAVE-01/handoff.md、六張子卡
任務目的：依依賴順序完成 TPEx 法人來源、Theme aggregation、Graph diffusion、正式 feature promotion、Top10 ranking／權重與 API/UI radar
證據路徑：.work/NEXT-WAVE-01/evidence/、docs/evidence/<CARD-ID>/

## 使用者授權

使用者已授權啟動這六項 backlog 的 repo 內研究、設計、實作、測試、獨立 Review／Repair、mainline acceptance、整合與 push。這不等於授權購買付費資料、接受外部服務條款、production deploy、真實交易、憑證匯入或其他 repo 外 write。

你是 executor/integrator，不得在 preflight 或狀態回報後停止。每張卡都要形成獨立 candidate commit；Review 與 Repair 不得在同一責任線。

## 執行順序與 blocking edges

1. TSKG-MFO-TPEX-01：官方來源治理與條件式 adapter。
2. TSKG-MFO-THEME-01：versioned Theme membership 與 deterministic aggregation。
3. TSKG-MFO-GRAPH-01：shadow-only graph diffusion。
4. CP-NEXT-WAVE-A：重跑 TSKG、source、theme、graph gates。
5. FEATURE-PROMOTE-02：只產出固定 SHA 的 GO/NO_GO promotion decision。
6. TOP10-RANK-PROMOTE-01：只有 FEATURE-PROMOTE-02=GO 才能開始。
7. UI-MFR-01：read-only API/UI radar vertical slice；至少需 Theme contract 完成，live graph drilldown 另需 Graph GO。

不得為了「全部做完」把 NO_GO 改寫成 GO。若來源或 promotion gate 合理產出 KEEP_BLOCKED／NO_GO，該卡可用完整證據結案，但所有依賴 mutation 必須維持 blocked。

## 每張卡的共同流程

preflight → isolated worktree/branch → implementation → verification → independent Review → 最多兩代 Repair/re-review → mainline acceptance → integrate latest main → rerun verification → push → cleanup receipt。

## 真正 blocker

- 接收端同檔 dirty changes 會被覆蓋。
- 缺 GitHub 權限。
- 需要購買資料、接受外部條款或取得法遵 owner 決策。
- Review 經兩代 Repair 仍 NO_GO。
- promotion decision 為 NO_GO，因而禁止 ranking mutation。
- repo 外 production/deploy/真實交易 write 未獲當次明確授權。

## Secure attachment

ZIP 中的 secure/yuanta/ 是來源電腦的敏感 prototype，只能用於本地 Windows live validation。不得複製進 repo、commit、log、screenshot、task card 或聊天。先依 secure/README_SECURITY.md 處理。

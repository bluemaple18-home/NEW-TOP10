# TOP10 storage guard integration 2026-08-27

## 目標

將已獨立審查為 `REVIEW_GO` 的完整 storage chain，從共同祖先
`cb9a6aedc348c494d984fa168d9c3fb7e089da80` 後的第一個 storage commit
`ad7eea3dd2756875c8143f6caf2c71e6e41bb9be`，一路整合至末端 candidate
`281086c2dcb209e2793e255b7f17218832c0fb5c`，再落到 current main
`f09b9b2453bb1fa0166f5a03461e7f971da8f7ea` 的整合結果。這不是只挑入
`281086c` 單一 commit；範圍包含 storage guard、policy、八個 wrapper、驗證測試、
任務卡與既有 evidence 的整條鏈，並保留 current main 的後續變更。

## 邊界

- 僅整合 `ad7eea3..281086c` 的 storage guard chain 必要檔案與其末端
  first-write coalescing 變更；不吸收同一候選分支上無關的 research chain。
- `scripts/run_daily_research_quota.sh` 僅合併 candidate 的固定 archive stem，保留 current main 的 research batch/ledger 流程。
- 不 push、不 deploy、不啟用排程、不執行 live/FOG/reclaim/外送。
- 不變更 launchd control plane。
- 僅解決實際衝突，禁止順手重構。

## 驗收

- `app/storage_safety.py` 與受影響測試完成整合。
- storage focused/affected tests 通過。
- plist parse、shell syntax、scheduler ownership 與 daily workflow 安全唯讀驗證通過。
- `git diff --check` 通過。
- 全套 `pytest` 通過；若有既有失敗，需以 base A/B 證明與本整合無關。
- 產出 repo 內 evidence receipt。
- 建立單一 integration commit 並回報 commit SHA、changed files、tests 與 blocker。

## 整合驗證要求

- 以 `git log --reverse cb9a6ae..281086c` 與檔案層級 diff 證明涵蓋完整
  storage chain，而不是只比較末端 commit。
- `scripts/run_daily_research_quota.sh` 必須同時保留 current main 的
  `RESEARCH_BATCH_ID`、batch intent、spine/ledger verification 與 history
  projection 流程；storage 修復只把 archive stem 改為同一交易日固定名稱。
- 只做靜態 plist parse，不得載入或改動任何 launchd control plane。

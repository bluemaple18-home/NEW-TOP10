# TOP10 storage guard integration 2026-08-27

## 目標

將已獨立審查為 `REVIEW_GO` 的 storage chain，截至 candidate `281086c2dcb209e2793e255b7f17218832c0fb5c`，整合到 current main `f09b9b2453bb1fa0166f5a03461e7f971da8f7ea`，保留 current main 後續變更。

## 邊界

- 僅整合 storage guard chain 必要檔案與 candidate first-write coalescing 變更。
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

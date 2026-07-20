# TSKG-INT-01 Mainline Acceptance

## Verdict

`ACCEPTED / INTEGRATED / CLEANUP_PENDING`

- Bootstrap / first parent：`a9758aa91e95985b16ce154a65521d10df6544d1`
- Target / second parent：`7f472be548c79a0b8d9758dcb3a4cfaca83751ff`
- Integration candidate：`2a1e5d2493975fda32bb5f9ecdff5dbc5aa018ff`
- Review evidence commit / integrated main commit：`3f73877eba078041515888eeab8b250c19cb20d2`
- Implementation thread：`019f7d89-1c4c-7480-9b62-3b58668d965f`
- Reviewer thread：`019f7d90-39b6-7a01-975b-153972aba6d1`
- Review verdict：`REVIEW_GO`；P0／P1／P2／P3 findings 均為 0。
- Repair：`NOT_NEEDED`；未建立 Repair thread。

## Mainline acceptance evidence

主線沒有只依賴 thread 完成文案；已直接驗證：

- candidate 恰有兩個 parents，且順序精確等於固定 bootstrap 與 target。
- candidate first-parent diff 為 34 個 TSKG payload 檔、integration evidence 與 integration card 狀態更新；Review commit 只新增 Review evidence 並更新 Review 卡。
- `git diff --check` 通過。
- 主線重跑 focused suite：`39 passed, 154 subtests passed`。
- 主線重跑 `py_compile`：TSKG modules 與 focused tests 通過。
- Integration 與獨立 Reviewer 各自跑 full suite，結果分別為 `367 passed, 1 failed, 182 subtests passed`；唯一 research component ledger failure 均在固定 first parent 重現相同 assertion，因此不是 candidate regression。
- Review evidence 與 Review 卡的 fixed reviewed commit 均等於 candidate SHA。

## Verified boundaries

- `app/api/main.py` 未修改；TSKG router 仍未掛 production API。
- 未修改 ranking、model、ETL、scheduler、deployment 或 dependency manifest／lockfile。
- PUBLIC source 仍不得 `APPROVED`；OQ-SRC-01 與 SLC-02 保持 blocked。
- 未連外、未 deploy、未 push、未核准 PUBLIC source。
- 主 worktree 原有 4 個修改檔與 2 組未追蹤內容未被暫存、覆寫或納入本鏈提交。

## Cleanup state

- 正式可見 Implementation／Review threads 與其 worktrees 暫時保留。
- 未取得 archive／branch deletion 授權，因此不宣稱 `CLEANED` 或 `CLOSED`。
- 本機 `main` 已整合；`origin/main` 尚未 push。

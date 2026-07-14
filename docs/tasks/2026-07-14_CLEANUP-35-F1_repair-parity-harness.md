# CLEANUP-35-F1｜修正 shadow campaign parity 證據

## Chain

- chain_id：`CLEANUP-35`
- card：`F1`
- candidate：`f9b4a71`
- review evidence：`b7d7e4d`
- findings：`C35-R1-F1`、`C35-R1-F2`
- re-review owner：`CLEANUP-35-R1` 原 reviewer

## 任務目的

只修 R1 指出的兩項 findings：補上可由乾淨 repository 重跑的 old/new parity harness，並修正 tracked script count。不得改變已審 candidate 的功能設計或擴充需求。

## 必讀

- `.work/CLEANUP-35-R1/review.md`
- `.work/CLEANUP-35-R1/status.md`
- `.work/CLEANUP-35-R1/evidence/verification.md`
- `docs/tasks/2026-07-14_CLEANUP-35_shadow-research-campaign.md`
- `scripts/run_shadow_research_campaign.py`
- `tests/test_shadow_research_campaign.py`
- parent `9748b95` 的四支舊入口

## 允許修改

- 恢復四支舊入口作為 compatibility/frozen legacy fixture，或新增等價且可審核的 frozen legacy fixture
- 新增 committed parity harness 與必要 focused tests
- 由 harness 重建 `.work/CLEANUP-35/evidence/parity.json`
- 修正 `.work/CLEANUP-35/result.md`、`status.md` 中不正確的 tracked script count／可重跑命令
- 必要時更新 `config/script_lifecycle.yaml`，但不得把 legacy fixture 誤標為 production
- 新增 `.work/CLEANUP-35-F1/status.md`、`result.md`、`evidence/`

## 必須關閉

### C35-R1-F1（P1）

- 單一 committed parity command 可在乾淨 worktree 重建 parity evidence
- old/new 各自執行四個 stage 的 valid、missing、subprocess failure fixture
- 比較 normalized JSON、exact Markdown、normalized TSV、console JSON、exit code與完整 command order
- 測試故意改動 CLI default、command argument 或 schema field 時會失敗；至少加入具體 mutation-sensitivity assertion
- 禁止用手寫 expected hash 冒充 old/new 執行結果

### C35-R1-F2（P3）

- lifecycle/reference strict audit 實際 tracked count 與 result/status 記錄一致
- 記錄可重跑命令，不硬編與 repository 不符的數字

## 禁止事項

- 不得執行真實 replay、shadow ranking、training 或長跑 subprocess
- 不得修改 production ranking、model、weights、publish、automation、daily 四檔或子工具資料語意
- 不得 merge、push、deploy
- 不得修 review 範圍外的問題

## 驗收與交付

- 使用 synthetic fixture、dry-run、mocked subprocess
- focused parity、failure、mutation-sensitivity tests
- reference/lifecycle strict-new、完整 pytest、`git diff --check`
- daily 四檔 SHA-256 不變
- 建立單一 atomic repair commit

## 下一張卡尾巴

`.work/CLEANUP-35-F1/status.md` 必須保留：`root question / repair commit / findings addressed / evidence command / remaining risk / next_card_type=RE_REVIEW / re_review_owner=CLEANUP-35-R1 / waiting_condition`。

完成後不得自行宣稱 GO；只把 repair commit SHA 交回原 R1 reviewer re-review。

# CLEANUP-07｜Scripts 生命週期清冊

- status: completed
- priority: P1
- owner: Codex worktree
- task thickness: standard

## 目標

對 400+ 個 `scripts/` 入口建立 deterministic、唯讀的生命週期 inventory，區分 production entrypoint、maintenance、research、builder、verifier、legacy candidate、unclassified；本卡只建立證據與防呆，不刪除、不搬移檔案。

## 依賴與 frontier

- 依賴：Artifact retention inventory 已完成。
- blocker：無。
- frontier：可立即開工；後續刪除卡必須依本卡 evidence 另開。

## 可改檔案

- `config/script_lifecycle.yaml`（可新增，僅放規則與明確 override）
- `scripts/audit_script_lifecycle.py`（可新增）
- `tests/test_script_lifecycle_audit.py`（可新增）
- `docs/architecture/SCRIPT_LIFECYCLE.md`（可新增）
- 本卡 result/status

## 不可改

- 既有 `scripts/*` 的執行行為
- live daily、ranking、model、通知、plist／cron
- artifacts/data/models
- 本卡不得刪除、搬移或自動改名任何檔案

## 實作契約

1. inventory 只掃 git tracked 的 `scripts/` 檔案；輸出 `script-lifecycle.v1` JSON。
2. 每筆至少包含 path、category、entrypoint flag、reference evidence、reason、candidate action。
3. production entrypoint 必須 exact allowlist；prefix 規則只能分類 research/build/verify 等，不得自行推定 production。
4. `legacy_candidate`／`unclassified` 只能建議 `review`，不得直接建議 delete，除非另有無引用證據。
5. 支援 `--output` 與 `--strict-new`；strict 只阻擋相對已核准 baseline 新增的 unclassified，不要求一次清完歷史債。
6. 不依賴網路、不讀 ignored artifacts、不新增第二套 workflow runner。

## 驗收

- fixture 覆蓋 exact production、prefix classification、override、new unknown、path escape。
- 對 repo 實跑成功並列出 category counts／前 20 個 review candidates。
- 重跑結果 deterministic；repo 無 mutation。
- `git diff --check` 通過。

## 回報

附 inventory 摘要與 evidence 路徑；建立單一 atomic commit，不 merge、不 push。

## Result

- `scripts/audit_script_lifecycle.py --strict-new` 對 tracked scripts 實跑通過；分類與前 20 個 review candidates 由 CLI 摘要輸出。
- fixture 已覆蓋 exact production、prefix、override、new unknown 與 path escape；同一 Git tree 連跑兩次 JSON 結果相同。
- 可重跑 evidence 命令與 schema 說明：`docs/architecture/SCRIPT_LIFECYCLE.md`。

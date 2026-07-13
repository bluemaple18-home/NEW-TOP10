# CLEANUP-11｜Legacy Regex Probe 退役

- status: ready
- priority: P2
- task thickness: minimal

## 目標

移除已被 lifecycle inventory 標為唯一 `legacy_candidate` 的 `scripts/test_regex.py`，並移除其 policy override。這是單檔退役，不順手刪其他歷史研究檔。

## 依賴與 frontier

- 依賴：CLEANUP-07 inventory 已完成。
- blocker：無；目前唯一 repo 引用是 `config/script_lifecycle.yaml` 的 override。
- frontier：可立即開工。

## 可改檔案

- 刪除 `scripts/test_regex.py`
- `config/script_lifecycle.yaml`
- `docs/architecture/SCRIPT_LIFECYCLE.md`（只在必要時）
- 本卡 status/result

## 不可改

- 其他 scripts、tests、artifacts/data/models
- daily、ranking、通知與排程

## 驗收

- `rg` 無 `test_regex` 參照。
- lifecycle audit `--strict-new` PASS，legacy_candidate count 為 0。
- 全套或最接近的 unit tests 通過。
- `git diff --check` 通過。

## 回報

建立單一 atomic commit；回報 SHA 與刪除證據，不 merge、不 push。

# CLEANUP-15｜Script Reference 可達性盤點

- status: completed
- priority: P1
- task thickness: standard

## 目標

在現有 457 支 tracked scripts／347 個 review candidates 上增加可重現的「被程式、設定、文件、plist、shell 呼叫」證據，產出 suspected orphan 清單，讓後續刪除有依據而不是憑檔名猜測。

## 依賴與 frontier

- 依賴：CLEANUP-07 script lifecycle inventory 已完成；CLEANUP-11 已刪除一支確認 legacy probe。
- blocker：無。
- frontier：本卡只盤點與測試，不批次刪檔。

## 可改檔案

- `scripts/audit_script_references.py`（可新增）
- `config/script_lifecycle.yaml`
- 對應 tests／docs（可新增）
- 本卡 status/result

## 不可改

- 不得刪除現有 scripts
- daily/retrain/publish/research worker entrypoints、plist、config 行為
- artifacts、model、data、外部排程

## 實作契約

1. 掃描 repo tracked text files；至少辨識 Python import、shell/python 路徑呼叫、plist、YAML、Markdown 引用。
2. 排除 self-reference、產出報告本身與明確 allowlist；結果排序 deterministic。
3. 每支 suspected orphan 必須帶 `reason` 與 reference count；無法判定 dynamic import 時標記 unknown，不得宣稱可刪。
4. production entrypoints 即使 reference count 為 0 也不得列為可刪，必須單獨標示 protected。
5. 支援 JSON output 與 `--strict-new` baseline，避免新增無引用 script。

## 驗收

- fixture tests 覆蓋 Python、shell、plist、docs、dynamic/unknown、protected entrypoint。
- 對 repo 實跑成功，結果 deterministic；現有 lifecycle audit 仍 PASS。
- `git diff --check` 通過。

## 回報

建立單一 atomic commit；回報 SHA、盤點統計與前 20 個 suspected orphan，不 merge、不 push、不刪檔。

## Result

- 新增 `scripts/audit_script_references.py`，輸出 deterministic `script-reference-audit.v1` JSON，並支援 `--strict-new`。
- 既有 101 個 suspected orphan 已寫入 `reference_audit.approved_unreferenced` 基線；它們仍會出現在盤點清單，allowlist 僅避免既有候選使 strict-new 失敗。
- 證據：`.work/CLEANUP-15/evidence/script-reference-audit.json`、`.work/CLEANUP-15/evidence/script-lifecycle.json`。

## Verification

- `uv run python -m unittest tests.test_script_reference_audit tests.test_script_lifecycle_audit`：9 tests PASS。
- reference audit `--strict-new`：PASS；重跑 JSON 與首次輸出逐位元一致。
- lifecycle audit `--strict-new`：PASS。
- `git diff --check`：PASS。

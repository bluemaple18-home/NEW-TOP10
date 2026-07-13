---
id: REFACTOR-03
status: integrated
type: implementation
priority: P2
model: gpt-5.6-luna
---

# Artifact inventory 與 retention dry-run 工具

## 目標

建立安全、可重跑、預設只讀的 artifact retention 工具，處理大量 replay／research 產物；本卡不得直接刪除任何檔案。

## 依賴與 frontier

- blocking edges：無。
- frontier：可立即開工。
- 真正清除檔案必須另開 mutation／acceptance 卡。

## 可改範圍

- `app/artifact_management/` 新模組。
- `scripts/artifact_retention.py` 薄 CLI。
- `tests/test_artifact_retention.py`。
- `docs/operations/` 的 retention 說明。

## 不可改範圍

- 不得刪除、移動、壓縮現有 `artifacts/`、`logs/`、`data/`。
- 不得修改 daily／ranking／model／publish runtime。
- 不得把本機絕對路徑寫入共享文件。

## 行為契約

1. 預設 `--dry-run`，若未明確提供 mutation flag 則永不刪檔。
2. 輸出 structured inventory：目錄、檔數、bytes、日期、保留理由、candidate action。
3. 保護 `latest`、正式 ranking／daily report、模型／baseline、最近 N 日與 manifest 引用檔。
4. 清理規則由明確 policy/schema 驅動，不以檔名猜測後直接刪除。
5. 同一輸入重跑產出一致結果。

## 驗收條件

- 使用 temp fixture 驗證 keep／archive candidate／delete candidate 分類。
- dry-run 前後 fixture 檔案 hash／數量不變。
- 產出機器可讀 JSON 與精簡人類摘要。
- `git diff --check` 通過。

## 建議驗證

```bash
uv run python -m unittest tests.test_artifact_retention
uv run python scripts/artifact_retention.py --dry-run --root artifacts
git diff --check
```

## 回報要求

- dry-run 摘要與可回收估算
- 保護規則
- 已驗證、未驗證、剩餘風險

## 主線整合結果

- 整合提交：`8d58ec8`
- 主線退修並重驗：7／8／30／31／90／91 天邊界與 root 外 symlink 防護共 5 項測試通過。
- 工具維持 dry-run only；未刪除、搬移或壓縮任何 artifact。

# Artifact retention dry-run

`scripts/artifact_retention.py` 是只讀的 artifact inventory 與 retention 分類工具。它不提供刪除、搬移或壓縮功能；`--dry-run` 只是把這個安全邊界明確寫在呼叫上，未提供時也仍是 dry-run。

## 使用方式

```bash
uv run python scripts/artifact_retention.py \
  --dry-run \
  --root artifacts \
  --as-of 2026-07-13 \
  --output .work/artifact-retention/artifact-inventory_2026-07-13.json
```

CLI 會輸出精簡摘要；`--output` 產出 machine-readable JSON。結果中的檔案路徑均相對於 `--root`，不會把本機絕對路徑寫入 inventory。

## Policy schema

`--policy` 接受 JSON，schema version 為 `artifact-retention-policy.v1`：

```json
{
  "schema_version": "artifact-retention-policy.v1",
  "recent_days": 7,
  "archive_after_days": 30,
  "delete_after_days": 90,
  "protected_globs": ["latest*", "*latest*", "ranking_????-??-??.*", "daily_report_????-??-??.*", "ranking.*", "daily_report.*", "*baseline*", "models/*", "*/models/*"],
  "protected_directories": ["models"],
  "manifest_globs": ["*manifest*.json", "*manifest*.yaml", "*manifest*.yml"]
}
```

未指定 policy 時使用上述預設值。`recent_days` 內的檔案保留；未受保護且超過 `archive_after_days` 的檔案標為 `archive_candidate`；超過 `delete_after_days` 的檔案標為 `delete_candidate`。分類是候選建議，不會執行任何 mutation。

以下內容固定保護：`latest` / latest 命名檔、正式 ranking 與 daily report 命名檔、`models/` 與 baseline 檔，以及 manifest 本身和 JSON manifest 引用的檔案。保護規則會在每個檔案的 `retention_reasons` 中留下證據。

## JSON 主要欄位

- `directories`：目錄、檔數、bytes、日期範圍、理由與 action 計數。
- `files`：root-relative path、directory、size、日期、保留理由與 `candidate_action`。
- `summary.reclaimable_bytes`：僅統計 `delete_candidate`，不代表已刪除。
- `dry_run: true`：固定為 true。

## 驗證

```bash
uv run python -m unittest tests.test_artifact_retention
git diff --check
```

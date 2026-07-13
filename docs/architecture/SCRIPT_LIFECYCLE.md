# Scripts 生命週期清冊

`scripts/audit_script_lifecycle.py` 只讀 Git tracked 的 `scripts/` 路徑，輸出 `script-lifecycle.v1` JSON。它不讀 ignored artifacts、不存取網路，也不執行、搬移或刪除任何 script。

## 使用方式

```bash
uv run python scripts/audit_script_lifecycle.py \
  --output .work/CLEANUP-07/evidence/script-lifecycle.json \
  --strict-new
```

輸出欄位為 `path`、`category`、`entrypoint`、`reference_evidence`、`reason` 與 `candidate_action`。清冊依路徑排序，因此相同 Git tree 與 policy 的結果可重跑。

## 分類規則

規則定義於 `config/script_lifecycle.yaml`：

- `production_entrypoint` 只能命中 exact allowlist，且 `entrypoint=true`。
- `research`、`builder`、`verifier`、`maintenance` 可由 policy prefix 分類，但 prefix 永遠不會推定 production。
- 明確 override 可以標示 `legacy_candidate`；該類別及 `unclassified` 一律只建議 `review`，不會建議 delete。

## Strict-new

`--strict-new` 比對 policy 的 `approved_unclassified` baseline。既有、已核准的 unknown 不會令指令失敗；新 unclassified script 會回傳 exit code 1，直到被加上明確分類規則或納入已核准 baseline。這是防呆，不是刪除機制。

## 驗證

```bash
uv run python -m unittest tests.test_script_lifecycle_audit
uv run python scripts/audit_script_lifecycle.py --strict-new --output .work/CLEANUP-07/evidence/script-lifecycle.json
git diff --check
```

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

## Script Reference 可達性盤點

`scripts/audit_script_references.py` 掃描 Git tracked 的 UTF-8 text files，辨識 Python import、shell／Python 路徑、plist、YAML 與 Markdown 的靜態引用。它只產出 `script-reference-audit.v1` JSON，不執行、搬移或刪除任何 script。

`scripts/build_script_governance.py` 再把 lifecycle、reference audit 與 architecture manifest 合併成 `top10.script-governance.v1`。每支 script 都會得到 owner、production reachability roots/workflows、artifact contract、verification contract 與 candidate action。production 可觸達路徑若缺 owner、artifact 或 verification，strict gate 會 fail closed；非 production script 的空 artifact 集合會明確標記為「promotion 前不適用」，不會被誤當成已驗證或可刪除。

```bash
uv run python scripts/audit_script_references.py \
  --output .work/CLEANUP-15/evidence/script-reference-audit.json \
  --strict-new

uv run python scripts/build_script_governance.py
uv run python scripts/verify_script_governance.py
```

報告依路徑排序，每支 script 都有 `reason`、`reference_count` 與引用證據。production entrypoint 由既有 exact allowlist 標示為 `protected`，即使引用數為零也不會列入 suspected orphan。無法靜態解析的 Python dynamic import 會放在 `unknown_references`；它們不構成可刪除結論。

`config/script_lifecycle.yaml` 的 `reference_audit.approved_unreferenced` 是既有無引用基線。`--strict-new` 只對未列入該 allowlist 的新增 suspected orphan 失敗；allowlist 不改變 lifecycle 分類或 production entrypoint 行為。

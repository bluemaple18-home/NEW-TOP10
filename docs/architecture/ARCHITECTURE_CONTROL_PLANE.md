# Architecture Control Plane

`config/architecture_control_plane.yaml` 是 TOP10new production entrypoint、domain、workflow、artifact 與 verification mapping 的人工審核來源。`config/script_lifecycle.yaml` 仍是 production entrypoint exact allowlist；兩者不一致時 builder 必須失敗。

## 建立與驗證

```bash
uv run python scripts/build_architecture_manifest.py
uv run python scripts/verify_architecture_manifest.py
```

Manifest 固定包含 Git SHA、source input digest 與 lifecycle contract。它不掃描網路、不執行 workflow，也不以 LLM 或固定品質分數判定完成。

## 修改規則

- 新增 production entrypoint 時，同步更新 lifecycle policy、control plane、owner 與 required verification。
- workflow step 引用的 artifact 必須存在於 artifact registry。
- artifact 必須明列 producer 與 consumer；heuristic dependency 不得寫成 canonical edge。
- `automatic_full_fallback_allowed=false` 是固定安全契約。

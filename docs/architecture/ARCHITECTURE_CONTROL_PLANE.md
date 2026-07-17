# Architecture Control Plane

`config/architecture_control_plane.yaml` 是 TOP10new production entrypoint、domain、workflow、artifact 與 verification mapping 的人工審核來源。`config/script_lifecycle.yaml` 仍是 production entrypoint exact allowlist；兩者不一致時 builder 必須失敗。

## 建立與驗證

```bash
uv run python scripts/build_architecture_manifest.py
uv run python scripts/verify_architecture_manifest.py
```

Manifest 固定包含 source base Git SHA、source input digest 與 lifecycle contract。驗證時 source SHA 必須仍是目前 HEAD 的 ancestor，並重新計算輸入 digest；因此 evidence 可隨 candidate commit 前進，但不能用不存在的 SHA 或 stale config 通過。它不掃描網路、不執行 workflow，也不以 LLM 或固定品質分數判定完成。

## 修改規則

- 新增 production entrypoint 時，同步更新 lifecycle policy、control plane、owner 與 required verification。
- workflow step 引用的 artifact 必須存在於 artifact registry。
- artifact 必須明列 producer 與 consumer；heuristic dependency 不得寫成 canonical edge。
- `automatic_full_fallback_allowed=false` 是固定安全契約。

## Incremental verification

```bash
uv run python scripts/plan_incremental_verification.py --base <base-sha> --head HEAD
uv run python scripts/verify_incremental_verification_plan.py
```

Planner 合併 control-plane explicit edges、Python AST imports 與 tracked path references。無法解析的 dynamic import 只會列入 `unknown_edges`／`needs_review`；不會被提升成假 canonical edge。Production impact 如果沒有 required verification mapping，planner 必須 fail closed。

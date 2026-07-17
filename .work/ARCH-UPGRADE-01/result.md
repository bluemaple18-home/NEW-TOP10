---
id: ARCH-UPGRADE-01
status: ready_for_review
type: result
---

# Result

## 已完成

- 建立 `top10.architecture-control-plane.v1` 與 `top10.architecture-manifest.v1`。
- production entrypoint exact allowlist 與 control plane 必須完全一致。
- manifest 綁定 Git SHA、source digests 與禁止 full automatic fallback 的 lifecycle contract。
- artifact producer/consumer、workflow step、owner 與 required verification 皆可 deterministic 驗證。

## 驗證

- `.venv/bin/python -m unittest tests.test_architecture_control_plane tests.test_script_lifecycle_audit`
- `.venv/bin/python scripts/build_architecture_manifest.py`
- `.venv/bin/python scripts/verify_architecture_manifest.py`
- `.venv/bin/python scripts/audit_script_lifecycle.py --strict-new ...`
- `git diff --check`

## 剩餘風險

- canonical mapping 是明確人工契約，不宣稱涵蓋 heuristic dynamic imports；`ARCH-UPGRADE-02` 會以 explicit/heuristic provenance 分層補上 incremental impact。

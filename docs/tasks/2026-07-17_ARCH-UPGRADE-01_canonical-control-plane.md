---
id: ARCH-UPGRADE-01
status: completed
type: implementation
priority: P0
thickness: standard
model: gpt-5.5
reasoning: high
model_reason: 跨檔 schema 與架構清冊，但不直接切換 production。
---

# Canonical architecture control plane

## 目標

建立版本化、可重跑、可驗證的 machine-readable manifest，統一描述 production entrypoints、domains、workflows、artifacts、producer/consumer 與 required gates。

## 依賴與 frontier

- blocking edges：無。
- frontier：可立即開工。

## 可改範圍

- `app/architecture/`
- `config/architecture_control_plane.yaml`
- `scripts/build_architecture_manifest.py`
- `scripts/verify_architecture_manifest.py`
- `tests/test_architecture_control_plane.py`
- 對應架構文件與 lifecycle policy。

## 不可改範圍

- production ranking/model/publish 行為。
- launchd 與 live notification 設定。
- 既有 unrelated dirty paths。

## 驗收

- schema 含版本、Git SHA、inputs digest、entrypoints、domains、workflows、artifacts、tests/gates。
- unknown production entrypoint、duplicate owner、missing producer/consumer、missing referenced path 必須 fail loud。
- 全部 tracked production entrypoint 與已知 daily workflow 均被覆蓋。
- builder 與 verifier 可在 temp output 重跑且 deterministic。

## Verification

```bash
uv run python -m unittest tests.test_architecture_control_plane
uv run python scripts/build_architecture_manifest.py --output <temp-output>
uv run python scripts/verify_architecture_manifest.py --manifest <temp-output>
git diff --check
```

## Evidence

`.work/ARCH-UPGRADE-01/evidence/`

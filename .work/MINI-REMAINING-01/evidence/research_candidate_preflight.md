# SHADOW-RUN-01 candidate preflight

## Base

- origin/main：`406b8119b543bdb100d23463c7379cd8dabf8d10`
- candidate 尚未 commit；本文件隨交接 commit 固定。

## Verification

以下命令使用交接端既有專案 `.venv` 的 Python 執行：

```bash
python -m py_compile scripts/run_research_shadow_runs.py scripts/verify_research_shadow_runs.py
python scripts/verify_research_shadow_runs.py
python scripts/verify_feature_experiment_gate.py
```

結果：

- py_compile：PASS
- research shadow verifier：`RESEARCH_SHADOW_RUNS_OK`
- feature experiment gate verifier：`FEATURE_EXPERIMENT_GATE_OK`
- `git diff --check`：PASS

## Environment note

`uv run --with-requirements requirements.txt ...` 在交接端自動選到 Python 3.14.4，因鎖定的 `lxml==4.9.4` 不支援該 Python C API 而建置失敗。這是依賴／直譯器相容性問題，不是 candidate verifier failure。接收端應使用專案既有相容 `.venv`，或明確指定相容 Python 版本後重跑 task card 的命令。

## Limits

- 尚未做獨立 Review。
- 尚未 mainline acceptance 或整合。
- runtime artifacts 為 gitignored evidence，不納入交接 commit。

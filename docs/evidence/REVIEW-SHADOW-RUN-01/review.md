# REVIEW-SHADOW-RUN-01 Independent Review

- reviewed SHA：`19a2d12`
- review scope：candidate diff、SHADOW-RUN-01 implementation card、既有 feature gate/verifier contract
- implementation：未修改
- verdict：`REVIEW_GO`

## Findings

未發現可重現的 correctness、production boundary、artifact schema、path portability 或 deterministic synthetic test 阻塞問題。

檢查結果：

- candidate diff 只包含 implementation card allowlist：`config/research_shadow_runs.yaml`、shadow runner/verifier、task/evidence/status 文件；未修改 RankingPolicy、`risk_adjusted_score`、production LightGBM input/weights 或 production ranking writer。
- `--feature-experiments-only` 不進入 ranking/replay subprocess 路徑；只讀 feature gate，產生 shadow experiment/run artifacts。
- experiment 與 run artifact 均明確寫入 `research_only`、不抓資料、不訓練、不改 production ranking、禁止 production score change/promotion 的 contract flags。
- `market_context` 由 config 明確 excluded，synthetic verifier 確認沒有產生其 artifact。
- source gate 的 `READY_FOR_SHADOW` 會保留為 `READY_FOR_SHADOW`；其他狀態會轉為 `BLOCKED_BY_GATE`，不會被當成 promotion 成功。
- artifact references 以 repo-relative path 為主；synthetic verifier 使用暫存目錄，確認輸出不依賴固定工作樹絕對路徑。
- synthetic verifier 固定 run date、固定 candidate fixture，確認四個指定候選、READY/BLOCKED 保留、market_context exclusion、artifact existence 與 production contract。

## Required verification evidence

使用交接指定的既有相容 interpreter：`/Users/mattkuo/TOP10new/.venv/bin/python`（Python 3.12.12）。未使用 uv cache 執行 review 驗證。

```text
/Users/mattkuo/TOP10new/.venv/bin/python -m py_compile scripts/run_research_shadow_runs.py scripts/verify_research_shadow_runs.py
PASS (exit 0)

/Users/mattkuo/TOP10new/.venv/bin/python scripts/verify_research_shadow_runs.py
RESEARCH_SHADOW_RUNS_OK output=artifacts/research_shadow_runs_verification_latest.json
PASS (exit 0)

/Users/mattkuo/TOP10new/.venv/bin/python scripts/verify_feature_experiment_gate.py
FEATURE_EXPERIMENT_GATE_OK output=artifacts/feature_experiment_gate_verification_latest.json
PASS (exit 0)

git diff --check 19a2d12^ 19a2d12
PASS (exit 0)
```

## Acceptance mapping

- correctness：PASS；runner 的 feature-only 分支、candidate selection、gate status mapping 與 output payload 已檢查，synthetic verifier PASS。
- production boundary：PASS；feature-only 分支不呼叫 ranking/replay；contract flags 與 gate verifier PASS。
- artifact schema：PASS；manifest、experiment、run artifact schema assertions 與欄位 contract 由 synthetic verifier 覆蓋並 PASS。
- path portability：PASS；相對 config path 透過 project-root resolution，artifact references 以 repo-relative path 輸出；synthetic config 在暫存目錄執行並 PASS。
- deterministic synthetic test：PASS；固定 fixture 與 `--run-date 2026-01-31`，verifier PASS。
- candidate allowlist：PASS；`git diff --name-only 19a2d12^ 19a2d12` 僅列 implementation card allowlist 內檔案。

## Remaining risk / limits

- 此 review 未執行真實 ranking、資料抓取、模型訓練或 production promotion，符合本卡 research-only 邊界。
- mainline 整合 candidate 後的最後一次驗證仍由 integration/mainline 流程負責；本 verdict 僅針對 reviewed SHA `19a2d12`。

REVIEW_GO

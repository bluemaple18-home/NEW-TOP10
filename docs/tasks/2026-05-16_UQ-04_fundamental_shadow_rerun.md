# UQ-04：真實 Universe 基本面 Shadow Score 重跑

任務ID：`UQ-04`
卡片類型｜派工對象：基本面研究 / 評估｜Codex
請讀：`docs/tasks/2026-05-16_UQ-01_tradable_universe_contract.md`、`docs/tasks/2026-05-16_UQ-03_feature_universe_rebuild_plan.md`、`scripts/import_goodinfo_universe.py`、`scripts/build_fundamental_shadow_scores.py`、`app/fundamentals/scoring.py`
任務目的：在真實 universe 或 probe universe 上重跑基本面 shadow score，確認 coverage、IC、分組報酬是否足以支持進 ranking。
證據路徑：更新 `artifacts/fundamental_shadow_scores.csv`、`artifacts/fundamental_shadow_report.json`，另存必要的 probe 報告。

## 背景

目前 shadow score 在樣本 universe 上 coverage 只有 8%，IC 約 0，不足以接 ranking。這張卡只在 universe 修正後重跑評估。

## 範圍

- 對真實 universe 批次匯入 Goodinfo cache。
- 產生 shadow score artifact。
- 評估：
  - stock-level coverage
  - feature-level coverage
  - IC
  - top/bottom quantile spread
  - ranking Top10 sensitivity
- 保留失敗清單，不隱藏資料問題。

## 不做

- 不改 `RankingPolicy`。
- 不改 `risk_adjusted_score`。
- 不把低 coverage 結果硬接入模型。

## 驗收

- 報告明確說明 coverage 是否達到接入門檻。
- 若 coverage < 80%，結論預設為不接 ranking。
- 若 IC / spread 無方向，結論預設為只保留 UI 解釋層。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/import_goodinfo_universe.py --delay 0.5
uv run --with-requirements requirements.txt python scripts/build_fundamental_shadow_scores.py --horizon 10
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
```

## Review 重點

- 是否因 coverage 低仍硬下結論。
- 是否把舊年報當近期資料。
- 是否區分「解釋有用」與「預測有用」。

## 執行紀錄

- 狀態：`completed`
- 完成時間：`2026-05-16`
- 使用資料：`artifacts/universe_rebuild_probe/features.parquet`
- Goodinfo summary：`artifacts/goodinfo_universe_import_summary.json`
- Shadow scores：`artifacts/fundamental_shadow_probe_scores.csv`
- Shadow report：`artifacts/fundamental_shadow_probe_report.json`
- 腳本更新：
  - `scripts/import_goodinfo_universe.py` 支援 `--features-path`
  - `scripts/build_fundamental_shadow_scores.py` 支援 `--data-dir` / `--output-prefix`

## 結果

- Goodinfo 匯入：total `20`、ok `13`、skipped `7`、error `0`
- Probe stock-level score coverage：`1.0000`
- Probe feature-level score coverage：`1.0000`
- latest score coverage：`1.0000`
- score observations：`278`
- IC：`0.005`
- IC median：`0.0073`
- top/bottom spread：`0.001597`
- quantile returns：
  - Q1 `-0.017185`
  - Q2 `-0.02261`
  - Q3 `0.007044`
  - Q4 `-0.039398`
  - Q5 `-0.015588`
- Ranking sensitivity：不可比；probe score stocks 與現有 ranking overlap 只有 `1` 檔，`comparable=false`。

## 結論

- 基本面分數在 probe universe 上 coverage 足夠，但沒有穩定 IC 或單調分組報酬。
- 不應接入 `risk_adjusted_score` / `quality_score` 權重。
- 可以保留在 UI 個股解釋層與 shadow artifact，等全量重建與更長樣本回測後再評估。

## 驗證紀錄

```bash
uv run --with-requirements requirements.txt python scripts/import_goodinfo_universe.py --features-path artifacts/universe_rebuild_probe/features.parquet --delay 0.5
uv run --with-requirements requirements.txt python scripts/build_fundamental_shadow_scores.py --data-dir artifacts/universe_rebuild_probe --output-prefix fundamental_shadow_probe --horizon 10
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
```

結果：

- `FUNDAMENTAL_SHADOW_SCORE stocks=20 coverage=1.0000 ic=0.005 top_bottom_spread=0.001597`
- `verify_model_foundation.py` 通過，`MODEL_FOUNDATION_OK specs=11`。

## Real Universe 補充紀錄

UQ-07 完成正式 `data/clean` 修復後，已用 real universe 重跑 shadow score：

```bash
uv run --with-requirements requirements.txt python scripts/build_fundamental_shadow_scores.py --data-dir data/clean --output-prefix fundamental_shadow_real_universe --horizon 10
```

輸出：

- `artifacts/fundamental_shadow_real_universe_scores.csv`
- `artifacts/fundamental_shadow_real_universe_report.json`

結果：

- feature stocks：`1967`
- stock-level available：`23 / 1967`
- stock-level coverage：`0.0117`
- feature-level score coverage：`0.0117`
- latest score coverage：`0.0118`
- IC：`0.0296`
- IC median：`0.0909`
- top/bottom spread：`0.064421`
- ranking sensitivity：不可比，current ranking overlap `1` 檔。

結論：real universe 下 coverage 遠低於 `80%` gate，不可接 ranking。

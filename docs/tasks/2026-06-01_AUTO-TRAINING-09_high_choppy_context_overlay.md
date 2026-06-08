# AUTO-TRAINING-09 HIGH_CHOPPY Context / Overlay

## 目標

把 `HIGH_CHOPPY` 做成訓練上下文、分層診斷、soft feature、ranking/risk overlay 候選，而不是硬訓練 gate。

## 背景

目前單日版 `HIGH_CHOPPY` 樣本偏少：

- strict version 約 14 天。
- 小幅放寬約 19 天。
- 大幅放寬約 25 天，但尚未證明適合作為 family-specific training 定義。

這不代表 `HIGH_CHOPPY` 不做；代表它不應該先被拿來單獨訓練正式模型。正確方向是改測 rolling-window 區段型 context。

## 原則

- `HIGH_CHOPPY` 會列入訓練研究。
- 樣本不足時只能 `MONITOR_ONLY` 或 warning，不得阻斷 AUTO-TRAINING-08。
- 不把 `HIGH_CHOPPY` 拆成多個正式 family tag。
- calibration variant 只能是 experiment variant，不能直接變成正式分類。
- 不用結果倒推定義；定義要先寫入 artifact 再評估。

## 任務範圍

1. 建立 rolling-window `HIGH_CHOPPY` context：
   - 高位條件：20D/60D 指數或權值報酬仍偏強。
   - 震盪條件：近期波動、上影、回檔或突破續航變差。
   - 集中條件：主流族群成交占比偏高。
   - 廣度條件：市場不是全面擴散。
2. 比較三種用途：
   - soft feature：加入候選特徵，讓模型自己決定權重。
   - stratified evaluation：只切報表，看模型在哪些盤勢失效。
   - ranking/risk overlay：調整排序或風險，不取代模型。
3. 拆解新增樣本：
   - 與 strict 版重疊多少。
   - 新增日期的 base regime 分布。
   - 新增日期的 10D label / return / Top10 replay 表現。
4. 判斷下一步：
   - 保留 monitor。
   - 升級為 soft feature candidate。
   - 升級為 ranking/risk overlay candidate。
   - 不允許直接 promotion。

## 非目標

- 不訓練 `HIGH_CHOPPY` 專屬正式模型。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不直接改 production ranking。
- 不新增正式盤勢類別。
- 不當 promotion evidence，除非後續另有 no-hindsight / sealed / replay 證據。

## 驗收標準

- Artifact 明確列出 context 日期數與 rolling-window 定義。
- Artifact 明確列出用途允許狀態：
  - soft feature allowed / blocked。
  - stratified evaluation allowed / blocked。
  - ranking overlay allowed / blocked。
  - promotion evidence allowed / blocked。
- `HIGH_CHOPPY` 樣本不足不會讓 training launch readiness blocked。
- 若新增樣本品質不穩，只能標 `MONITOR_ONLY`。

## 建議驗證

```bash
uv run --with-requirements requirements.txt python scripts/verify_training_automation_readiness.py --skip-model-research-flow --timeout-seconds 900
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
git diff --check
```

## 預期回報格式

```text
high_choppy_context_status:
strict_dates:
rolling_context_dates:
new_dates_quality:
soft_feature_allowed:
stratified_evaluation_allowed:
ranking_overlay_allowed:
promotion_evidence_allowed:
blocks_main_training:
errors:
```

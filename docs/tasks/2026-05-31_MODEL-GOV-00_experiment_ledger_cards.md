# MODEL-GOV experiment ledger card set

## 任務卡

任務ID：MODEL-GOV-00
卡片類型｜派工對象：Planning Index / Model Governance｜Codex
請讀：`docs/architecture/MODEL_IMPROVEMENT_LOOP.md`、`docs/tasks/2026-05-30_MODEL-EXP-01_offline_experiment_plan.md`、`docs/tasks/2026-05-29_FEATURE-EXP-01_shadow_feature_promotion_gate.md`
任務目的：建立完整的模型實驗治理插件規劃，把 feature / label / horizon / universe / overlay 實驗從「一次性 artifact」升級成可追蹤、可到期驗收、可統計命中率的 experiment ledger；本卡只開規劃，不實作。
證據路徑：`docs/tasks/2026-05-31_MODEL-GOV-*.md`

## 背景

`fadacai-portfolio` 的 thesis ledger 對 TOP10new 最有價值的部分不是券商/MCP/推送，而是「把可驗證假設寫進帳本，到期驗收，累積命中率」。TOP10new 應把這個概念轉成模型訓練治理層：每次新增特徵、調整 label、改 horizon、改 universe 或測 overlay，都必須留下預註冊假設、baseline、驗收窗口、metric policy、結果與後續決策。

這不是最小 MVP。本專案尚未正式上線，因此本組卡直接規劃完整閉環，但每張卡仍必須可單獨交付與驗證。

## 核心邊界

- `model_experiment_ledger` 是長期狀態記憶層，不是新的 promotion gate、acceptance engine 或第二套 model experiment pipeline。
- 既有 artifacts 仍是各自層級的 source of truth：計畫看 `model_exp_plan_*.json`，執行看 `model_exp_run_manifest_*.json`，結果看 `model_exp_result_report_*.json`，升版看 sealed OOS / replay / rollback / model group acceptance。
- Ledger 只回答「這個假設目前在哪個狀態、何時該驗收、最後結果是什麼、同類假設歷史表現如何」。
- 不直接搬 `fadacai-portfolio` 程式碼；MIT 可參考，但 TOP10new 需依本地資料契約重寫。
- 不引入美股、Firstrade、Claude Code MCP、Telegram 或 options workflow。
- 不改 `risk_adjusted_score`。
- 不覆蓋 `models/latest_lgbm.pkl`。
- 不把 ledger verdict 當 production promotion 授權；ledger 只提供治理證據，promotion 仍走既有 gate。
- 所有可重跑命令使用 repo-relative path 與 `uv run --with-requirements requirements.txt python ...`。

## 卡片順序

0. `MODEL-GOV-FULL`：完整實作派工卡，將 `00~08` 收斂為單一 feature delivery loop。
1. `MODEL-GOV-01`：Experiment Ledger Schema Contract
2. `MODEL-GOV-02`：Experiment Ledger CLI + Storage
3. `MODEL-GOV-03`：Ledger Integrity Verifier + Unit Regression
4. `MODEL-GOV-04`：Research Flow Integration
5. `MODEL-GOV-05`：Result Report → Ledger Resolver
6. `MODEL-GOV-06`：Daily / Weekend Governance Surfacing
7. `MODEL-GOV-07`：Backfill + Migration
8. `MODEL-GOV-08`：Promotion Evidence Adapter

## 依賴圖

```text
MODEL-GOV-01
  -> MODEL-GOV-02
      -> MODEL-GOV-03
          -> MODEL-GOV-04
              -> MODEL-GOV-05
                  -> MODEL-GOV-06
          -> MODEL-GOV-07
              -> MODEL-GOV-08
```

## Checkpoints

- Checkpoint A：`MODEL-GOV-01` 到 `03` 完成後，必須能建立 ledger、阻擋壞資料、跑 unit regression。
- Checkpoint B：`MODEL-GOV-04` 到 `05` 完成後，既有 model research flow 必須能自動登錄與驗收 experiment，不改 production training。
- Checkpoint C：`MODEL-GOV-06` 到 `08` 完成後，daily/weekend/report/review 能讀 ledger，並且 promotion gate 能看到治理證據但不能被 ledger 單獨放行。

## 完整驗收定義

- 每個 experiment 都有穩定 id、hypothesis、target metric、baseline artifact、trigger、decision policy、created/resolved timestamps。
- CLI 支援 add/list/due/resolve/reschedule/supersede/stats。
- Ledger verifier 只檢查 ledger integrity，不重做 no-hindsight、sealed OOS、replay 或 promotion gate。
- `run_model_research_flow.py` 可在不正式訓練/不覆蓋模型的前提下產生 ledger evidence。
- result report 是實驗結果 source of truth；ledger resolver 只把 result verdict 寫回長期狀態。
- promotion review 只把 ledger evidence 當必要佐證；ledger evidence 不得取代 sealed OOS / replay / rollback / human review。

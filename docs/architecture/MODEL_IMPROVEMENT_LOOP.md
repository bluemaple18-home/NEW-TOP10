# 模型升級閉環：回測、資料面、特徵升級

## 目標

NEW-TOP10 的模型升級不是把更多欄位直接塞進 LightGBM，而是建立一條可重複、可回測、可回滾的升級管線：

1. 每日產生候選與決策 artifact。
2. 用 production replay 檢查歷史上同一套決策是否有效。
3. 新訊號先做 shadow feature / decision annotation。
4. 只有通過 out-of-sample、sealed OOS、walk-forward、portfolio replay 的訊號才可進正式模型。

## 現況判斷

- 技術面、事件訊號、K 線型態是目前正式模型主要特徵。
- 基本面欄位有資料結構，但 coverage 過低，目前未進正式 feature group。
- 籌碼面有三大法人欄位路徑，但目前資料源不可用，沒有進正式模型。
- 產業輪動已有 shadow research / monitor，但結論仍是 monitor-only，不影響 production score。
- 入榜天數目前尚未進 daily report / API / UI / model。
- `SHADOW-01` 已把可進模型實驗前檢查的候選收斂為：
  - `candidate_persistence`
  - `portfolio_risk_overlay`
  - `regime_feature_group_ablation`
- `MODEL-EXP-01` 只建立離線實驗矩陣，不正式訓練、不覆蓋 `models/latest_lgbm.pkl`、不改 `risk_adjusted_score`。
- `market_context`、基本面、籌碼、產業輪動在資料契約或驗證完成前維持 blocked，不進模型實驗。

## 研究到上線分層

```text
feature_experiment_gate
        ↓
SHADOW-01：候選特徵驗證 artifact
        ↓
MODEL-EXP-01：離線模型/overlay 實驗計畫
        ↓
MODEL-EXP-02：sealed OOS + replay + regime breakdown
        ↓
MODEL-PROMOTE-01：人工 review + rollback-ready 正式替換
```

## 自動訓練與正式升版分層

`training_automation_readiness` 必須分清楚兩件事：

- `training_launch_ready=true`：可以啟動預註冊自動訓練候選，產生新模型候選與驗證 artifact。
- `promotion_ready=true`：才可以進正式模型升版 review。

`MONITOR_ONLY`、月營收資料降級、factor monitor warning、ranking outcome 尚未成熟，可以允許訓練候選啟動，但不能允許 production promotion。這些狀態必須出現在 `warnings` 或 `promotion_blockers`，不得靜默通過。

目前標準：

- `READY_FOR_AUTOMATED_TRAINING_REVIEW`：事前準備已可啟動自動訓練 review。
- `training_launch_mode=pre_registered_candidate_with_promotion_gate`：只能走預註冊候選；不得用同輪診斷結果補 filter。
- `promotion_ready=false`：候選訓練可以開始，但 `models/latest_lgbm.pkl` 不得因 readiness artifact 被覆蓋。

## 研究治理契約

模型研究必須先回答「這一輪要驗什麼」，再產 artifact。任何研究 artifact 若要被 readiness 或 promotion 讀取，必須符合下列契約：

- `research_question`：明確描述本輪只回答的一個問題。
- `layer`：只能是 `model`、`ranking`、`trading`、`operations` 之一；測試不能混層。
- `pre_registered=true`：跑前已固定 baseline、window、metric、門檻與診斷欄位。
- `decision`：只能是 `PROMOTE_CANDIDATE`、`MONITOR_ONLY`、`REJECTED`。
- `decision_policy`：記錄本輪 pass / monitor / reject 的預註冊門檻。
- `diagnostics_not_for_promotion`：明列哪些欄位只能輔助理解，不能當 promotion 證據。
- `research_only=true`：研究階段不改 production ranking、不覆蓋 `models/latest_lgbm.pkl`。
- `production_promotion_allowed=false`：研究 artifact 不能直接授權上線。
- `promotion_gate_variant=current_baseline`：正式 gate 只能看預先定義的 baseline，不得用事後挑出的診斷變體。
- `diagnostic_only_variants`：消融、盤勢 breakdown、替代特徵組只能當診斷，不能在同一輪變成正式規則。
- `diagnostic_failures_cannot_define_same_run_filters=true`：看到某段輸了，只能產生下一輪假設，不能回頭修改同一輪結論。
- `new_filters_require_next_walkforward_run=true`：任何新防守條件、濾網或 overlay 都必須在下一輪 walk-forward 驗證。
- 每個 fold 必須記錄 `train_end` 與 `validation_start`，且 `train_end < validation_start`。

這些不是文件建議，而是機器檢查：

```bash
uv run --with-requirements requirements.txt python scripts/verify_half_year_walkforward_no_hindsight.py \
  --artifact artifacts/model_experiments/half_year_walkforward_validation_YYYY-MM-DD.json

uv run --with-requirements requirements.txt python scripts/verify_half_year_walkforward_no_hindsight.py --self-test
```

`--self-test` 必須證明 verifier 會擋住下列反例：

- 把 diagnostic variant 當 promotion gate。
- 允許同輪診斷結果倒推出正式濾網。
- fold 訓練資料壓到 validation window。
- 研究 artifact 宣稱可直接 production promotion。

readiness gate 只能讀通過 verifier 的 artifact；readiness 不負責發明策略、不負責調參、不負責把 post-hoc 診斷變成 production 規則。

目前可重跑產物：

- `scripts/build_feature_experiment_gate.py`
- `scripts/build_shadow_feature_experiment.py`
- `scripts/build_model_experiment_plan.py`
- `scripts/verify_feature_experiment_gate.py`
- `scripts/verify_shadow_feature_experiment.py`
- `scripts/verify_model_experiment_plan.py`

## 升級順序

### 1. 資源保護

先分離本機安全測試與主機正式長任務：

- `local_safe`：擋正式重訓、擋無日期窗 daily ETL、跳過重型 industry monitor。
- `standard`：沿用既有流程。
- `host_full`：主機正式跑全流程時明確使用。

### 2. Production Replay Backtest

回測應模擬真實每日使用方式：

- D 日收盤後產生候選。
- D+1 開盤買進。
- 使用當時已知資料，不用未來 ranking / price / fundamentals。
- 納入手續費、證交稅、滑價、漲跌停與最大持股限制。
- 評估 1D / 3D / 5D / 10D、勝率、MDD、Sharpe、Sortino、Profit Factor、平均賺賠比。

### 3. 入榜天數

`candidate_streak_days` 先作為決策輔助，不直接進模型。

應輸出：

- `first_seen_date`
- `consecutive_ranked_days`
- `days_since_first_seen`
- `previous_rank`
- `rank_delta`

驗證假設：

- 第 1 天入榜可能是剛突破，尚未確認。
- 第 2-5 天入榜可能代表動能延續。
- 太久入榜可能代表過熱或追高風險。

是否進模型必須由 replay backtest / OOS 實驗決定。

### 4. 基本面資料契約

基本面進模型前必須先解決：

- as-of date：財報發布日與模型可見日。
- coverage：各欄位在 universe 的覆蓋率。
- lag：季報/年報延遲。
- missing policy：缺值不可被當成好訊號。

### 5. 籌碼資料契約

先做三大法人，再評估券商分點：

- 三大法人買賣超：資料源、coverage、更新時間、欄位單位。
- 融資融券：可作為風險與過熱輔助。
- 券商分點：需確認資料來源、授權與點位穩定性，不可用未授權/不可重現資料進模型。

### 6. 產業輪動

產業輪動先走 shadow / overlay：

- 不直接改 `risk_adjusted_score`。
- 用 leave-one-out / ex-self group factor。
- 檢查同族群曝險與集中度。
- 只有 portfolio replay 改善，才可開 production integration。

## 不可做

- 不用全歷史重訓結果宣稱未來會準。
- 不用同一天收盤訊號卻假設同一天最低價買進。
- 不把低 coverage 的基本面/籌碼欄位直接塞正式模型。
- 不把入榜天數直接當加分權重，除非回測證明有效。
- 不在本機預設跑全量 ETL 或正式 retrain。

## 主機長期測試定位

主機應負責跑可重複的長任務：

- 每日 official daily run。
- 每日 postcheck。
- 每日/每週 production replay report。
- 每週或手動 retrain acceptance。
- shadow feature experiment。

本機只負責：

- local-safe unit / contract test。
- 小樣本 regression。
- UI 與 API contract。
- review 前證據整理。

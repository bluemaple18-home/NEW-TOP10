# 模型升級主線卡片索引

## BACKTEST-01

任務ID：BACKTEST-01
卡片類型｜派工對象：Backtest / Production Replay｜Codex
請讀：`docs/architecture/MODEL_IMPROVEMENT_LOOP.md`、`app/agent_b_ranking.py`、`app/labels.py`、`app/trading/ranking_policy.py`
任務目的：建立 production replay 回測，模擬 D 日收盤選股、D+1 開盤進場，含成本、滑價、停損停利、最大持股與同族群曝險
證據路徑：`artifacts/backtest/replay_YYYY-MM-DD.json`、`artifacts/backtest/replay_YYYY-MM-DD.md`

## PERSIST-01

任務ID：PERSIST-01
卡片類型｜派工對象：Decision Artifact / Candidate Persistence｜Codex
請讀：`scripts/build_weekly_candidate_snapshot.py`、`scripts/generate_daily_report.py`、`app/services/weekly_decision_service.py`
任務目的：新增入榜天數、首次入榜日、連續入榜天數、排名變化，先進 daily report / API / UI，不進模型分數
證據路徑：`artifacts/candidate_persistence_YYYY-MM-DD.json`、`artifacts/daily_report_YYYY-MM-DD.json`

## BACKTEST-02

任務ID：BACKTEST-02
卡片類型｜派工對象：Backtest / Persistence Research｜Codex
請讀：`docs/tasks/2026-05-28_MODEL_IMPROVEMENT_CARDS.md`、`artifacts/candidate_persistence_*.json`、`artifacts/ranking_*.csv`
任務目的：驗證入榜天數對 1D / 3D / 5D / 10D 報酬、勝率、MDD、MAE/MFE 的影響，判斷是否值得成為 shadow feature
證據路徑：`artifacts/backtest/persistence_study_YYYY-MM-DD.json`、`artifacts/backtest/persistence_study_YYYY-MM-DD.md`

## FUND-01

任務ID：FUND-01
卡片類型｜派工對象：Data Contract / Fundamentals｜Codex
請讀：`app/fundamental_data.py`、`data/fundamentals/`、`app/agent_b_modeling.py`、`scripts/verify_data_contracts.py`
任務目的：補齊基本面 coverage、as-of date、財報延遲、缺值策略；在 coverage 未達門檻前不得進正式模型
證據路徑：`artifacts/fundamental_contract_YYYY-MM-DD.json`、`artifacts/fundamental_shadow_feature_YYYY-MM-DD.json`

## CHIP-01

任務ID：CHIP-01
卡片類型｜派工對象：Data Contract / Chip Flow｜Codex
請讀：`app/finmind_integrator.py`、`app/indicators/mixins/volume.py`、`docs/References.md`
任務目的：建立籌碼資料契約，先驗三大法人買賣超 coverage / as-of / 缺資料，再評估券商分點資料源與授權
證據路徑：`artifacts/chip_data_contract_YYYY-MM-DD.json`、`artifacts/chip_shadow_feature_YYYY-MM-DD.json`

## INDUSTRY-ML-01

任務ID：INDUSTRY-ML-01
卡片類型｜派工對象：Research / Industry Rotation｜Codex
請讀：`scripts/research_industry_momentum_walkforward.py`、`scripts/monitor_industry_momentum.py`、`data/reference/stock_industry_map.csv`
任務目的：用 production replay 驗證產業輪動是否可作為 overlay 或 shadow feature；不得直接改 production score
證據路徑：`artifacts/industry_rotation_replay_YYYY-MM-DD.json`、`artifacts/industry_rotation_replay_YYYY-MM-DD.md`

## FEATURE-EXP-01

任務ID：FEATURE-EXP-01
卡片類型｜派工對象：Model Experiment Gate｜Codex
請讀：`docs/architecture/MODEL_IMPROVEMENT_LOOP.md`、`docs/tasks/2026-05-28_MODEL_IMPROVEMENT_CARDS.md`、`app/agent_b_modeling.py`
任務目的：建立 shadow feature promotion gate，只有 streak / fundamentals / chip / industry 在 OOS、sealed、walk-forward、production replay 都改善時才可進正式模型
證據路徑：`artifacts/feature_experiment_gate_YYYY-MM-DD.json`

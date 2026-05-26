# RETRAIN-03 auto retrain promotion gate

## 卡片

任務ID：RETRAIN-03  
卡片類型｜派工對象：Model Ops / Auto Retrain Promotion Gate｜Codex  
請讀：`docs/tasks/2026-05-26_RETRAIN-02_formal_manual_retrain_acceptance.md`、`scripts/run_automation.py`、`scripts/daily_retrain.sh`、`scripts/verify_retrain_rollback.py`、`config/automation.yaml`  
任務目的：讓 auto/scheduled retrain 在 PSI CRITICAL 或 factor WARN 超門檻時拒絕 promote 新模型並 rollback；manual retrain 保留警示但不阻斷  
證據路徑：`artifacts/retrain_rollback_injection_YYYY-MM-DD.json`、`artifacts/automation_status.json`、`artifacts/retrain_run_summary_YYYY-MM-DD.json`

## 邊界

- 不啟用 `monitor.auto_retrain`。
- 不改 ranking score 權重。
- 不改模型 feature list。
- 不改 PSI / factor monitor 的報告語意；只在 retrain promotion gate 讀取報告做阻斷。

## 驗收

- `scripts.run_automation retrain` 支援 `--trigger manual|scheduled|auto`。
- `manual` retrain 遇到 PSI CRITICAL / factor WARN 仍只記錄警示，不阻斷手動流程。
- `scheduled` / `auto` retrain 若 fresh monitor report 顯示 PSI CRITICAL 或 factor WARN 超門檻，`retrain.promotion_gate=FAILED`。
- promotion gate 失敗時必須觸發 `model.rollback=OK`，正式 `models/latest_lgbm.pkl` 回到備份。
- dry-run 不讀取舊 monitor report，不把舊報告當成 gate 證據。

## 本地驗證

- `scripts/run_automation.py` 新增 trigger-aware promotion gate；預設只阻斷 `auto` / `scheduled`。
- `config/automation.yaml` 新增 promotion gate 設定：PSI `CRITICAL`、factor `WARN`、factor_warn_count > 0 均阻斷 auto/scheduled promotion。
- `scripts/daily_retrain.sh` 支援 `--trigger manual|scheduled|auto`，預設為 `manual`。
- `scripts/verify_retrain_rollback.py` 新增 `promotion_gate` 故障注入 case：monitor subprocess 記為 OK，但 fresh report 為 PSI `CRITICAL` + factor `WARN`。
- `PYTHONPYCACHEPREFIX=/private/tmp/top10_pycache python3 -m py_compile scripts/run_automation.py scripts/verify_retrain_rollback.py` 通過。
- `bash -n scripts/daily_retrain.sh scripts/run_daily.sh` 通過。
- `python3 -m scripts.run_automation retrain --help` 顯示 `--trigger {manual,scheduled,auto}`。
- `uv run --with-requirements requirements.txt python scripts/verify_retrain_rollback.py` 通過，輸出 `artifacts/retrain_rollback_injection_2026-05-26.json`。
- rollback / gate injection 五個 case 全部通過：`validate`、`ranking`、`monitor`、`promotion_gate`、`manual_promotion_skip`。
- `promotion_gate` error 為 `auto retrain promotion blocked: psi_status=CRITICAL, factor_status=WARN, factor_warn_count=3>0`，且 `model.rollback=OK`、`restored_original_model=true`。
- `manual_promotion_skip` 在同樣 PSI `CRITICAL` + factor `WARN` 報告下，`retrain.promotion_gate=SKIPPED`、未 rollback、`kept_trained_model=true`。

## Review 結論

- RETRAIN-03：PASS。
- 確認 `manual|scheduled|auto` trigger 已接到 runner 與 wrapper。
- 確認 manual 遇 PSI `CRITICAL` / factor `WARN` 會跳過 promotion gate、不 rollback。
- 確認 auto 遇 PSI `CRITICAL` + factor `WARN` 會 `retrain.promotion_gate=FAILED` 並 rollback。
- `monitor.auto_retrain` 仍維持 false；scheduled path 與 auto 共用 gate 設定，未另開自動重訓。

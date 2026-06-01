# MODEL-GOV-03 experiment ledger integrity verifier

## 任務卡

任務ID：MODEL-GOV-03
卡片類型｜派工對象：Integrity Verifier / Model Governance｜Codex
請讀：`docs/architecture/MODEL_EXPERIMENT_LEDGER.md`、`scripts/model_experiment_ledger.py`、`scripts/verify_model_experiment_plan.py`、`scripts/verify_model_experiment_run_manifest.py`
任務目的：新增 ledger integrity verifier 與 regression tests，只檢查 ledger 自身結構、狀態轉移、引用路徑與碰撞保護；不重做既有 model experiment / no-hindsight / promotion gates。
證據路徑：`artifacts/model_experiments/model_experiment_ledger_verification_latest.json`

## 交付內容

- 新增 `scripts/verify_model_experiment_ledger.py`。
- 新增或擴充測試檔，覆蓋壞資料反例。
- Verifier 必須檢查：
  - schema version 正確。
  - id 唯一。
  - pending 實驗有 trigger。
  - resolved 實驗有 history verdict。
  - `decision_policy` 存在且包含 pass/fail/partial 規則。
  - `baseline` 不可空。
  - `source_artifacts` 必須是 repo-relative path。
  - `production_promotion_allowed` 不可由 ledger 單獨設成 true。
  - `ledger_role` 必須是 `state_memory` 或等價欄位；不得宣稱自己是 promotion gate。
  - 同 id 不同 hypothesis 不可靜默覆蓋。

## 明確不檢查的事

以下已由既有架構負責，本 verifier 不重做：

- no-hindsight / post-hoc filter 規則：由既有 model experiment verifier / `verify_half_year_walkforward_no_hindsight.py` 負責。
- sealed OOS 是否通過：由 sealed OOS gate 負責。
- replay / portfolio replay 是否通過：由對應 replay verifier 負責。
- production promotion 是否可放行：由既有 promotion / model group acceptance 流程負責。

## 壞資料反例

Verifier self-test 必須證明會擋下：

- 沒有 baseline 的 experiment。
- `hypothesis` 空白或只有質性描述。
- `decision_policy` 缺主要 metric。
- `source_artifacts` 使用本機絕對路徑。
- `status=passed` 但 history 沒有 actual metric。
- ledger verdict 直接宣稱 `promotion_ready=true`。
- 同 id 不同 hypothesis 被靜默覆蓋。

## 不可做

- 不修改 `verify_model_group_acceptance.py`。
- 不新增 promotion gate。
- 不重做 no-hindsight verifier。
- 不改 retrain gate。
- 不重跑模型。

## 驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/model_experiment_ledger.py scripts/verify_model_experiment_ledger.py
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --self-test
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
git diff --check -- scripts/model_experiment_ledger.py scripts/verify_model_experiment_ledger.py docs/tasks/2026-05-31_MODEL-GOV-03_experiment_ledger_verifier.md
```

## TDD Loop

- RED：先寫 verifier self-test 壞樣本。
- GREEN：讓 verifier 擋住所有壞樣本並接受最小好樣本。
- Refactor：把錯誤訊息整理成機器可讀 JSON。

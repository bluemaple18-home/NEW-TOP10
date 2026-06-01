# MODEL-GOV-08 promotion evidence adapter

## 任務卡

任務ID：MODEL-GOV-08
卡片類型｜派工對象：Promotion Evidence Adapter｜Codex
請讀：`docs/architecture/MODEL_IMPROVEMENT_LOOP.md`、`docs/architecture/MODEL_EXPERIMENT_LEDGER.md`、`scripts/verify_model_group_acceptance.py`、`scripts/verify_model_experiment_ledger.py`
任務目的：把 experiment ledger 作為既有模型升版 review 的必要 evidence adapter；只確認候選模型能追溯到已驗收假設，不新增第二套 promotion gate。
證據路徑：`artifacts/model_experiments/model_promotion_review_YYYY-MM-DD.json`、`artifacts/model_group_acceptance_YYYY-MM-DD.json`

## 交付內容

- 新增或擴充既有 promotion review artifact 的 ledger evidence section；若尚無 promotion review script，先以薄 adapter artifact 表達，不接管升版判定。
- Evidence adapter 必須檢查：
  - 候選模型對應的 experiment ledger entry 存在。
  - ledger status 是 `passed` 或具明確人工 override reason。
  - 沒有 unresolved collision 或 expired required experiment。
  - ledger source artifacts 可追溯到 result report / run manifest。
- `verify_model_group_acceptance.py` 如需讀 adapter 結果，只能把缺 ledger evidence 視為 promotion review blocker；不得因 ledger passed 就略過 sealed OOS、replay、rollback 或既有 acceptance。

## Source of truth 分工

```text
ledger evidence：只證明候選模型有可追溯、已驗收的研究假設
sealed OOS：仍由 sealed OOS gate 判定
replay / portfolio replay：仍由 replay artifacts 判定
rollback：仍由 rollback verifier 判定
model group acceptance：仍由 verify_model_group_acceptance.py 判定
human review：仍由既有 review 流程判定
```

缺 ledger evidence 時只能輸出 `MISSING_LEDGER_EVIDENCE` / `HUMAN_REVIEW_REQUIRED`；ledger evidence 通過時只能輸出 `LEDGER_EVIDENCE_OK`，不得輸出 `PROMOTION_READY`。

## 不可做

- 不在本卡啟用任何新模型。
- 不降低 sealed OOS 或 acceptance 門檻。
- 不新增自動 promote 行為。
- 不新增第二套 promotion gate。
- 不把 `partial` 當 passed。

## 驗證

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/verify_model_group_acceptance.py scripts/verify_model_experiment_ledger.py
uv run --with-requirements requirements.txt python scripts/verify_model_experiment_ledger.py --ledger artifacts/model_experiments/model_experiment_ledger.json
uv run --with-requirements requirements.txt python scripts/verify_model_group_acceptance.py
git diff --check -- scripts/verify_model_group_acceptance.py docs/tasks/2026-05-31_MODEL-GOV-08_promotion_review_contract.md
```

## TDD Loop

- RED：建立缺 ledger、ledger partial、ledger passed、collision、expired required experiment 的 synthetic evidence cases。
- GREEN：讓 adapter 正確輸出 `MISSING_LEDGER_EVIDENCE` / `LEDGER_EVIDENCE_BLOCKED` / `LEDGER_EVIDENCE_OK`。
- Refactor：把 promotion review 結果維持為 artifact，不直接寫 production config。

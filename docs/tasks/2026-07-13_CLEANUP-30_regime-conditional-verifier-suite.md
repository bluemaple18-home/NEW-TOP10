# CLEANUP-30｜收斂 regime conditional verifier

## 任務目的

依 CLEANUP-25 的 B2 計畫，把兩支 regime conditional 研究 verifier 收斂為一支具名 profile 的 verifier，完整保留各自檢查、輸出、console 與 exit code 契約，再退休舊入口。

## 請讀

- `.work/CLEANUP-25/evidence/verifier-retirement-plan.json` 的 `MG-REGIME-CONDITIONAL-RESEARCH` 與 B2
- `scripts/verify_regime_conditional_hybrid_report.py`
- `scripts/verify_regime_conditional_shadow_rankings.py`
- `scripts/build_regime_conditional_suite.py`
- `tests/test_regime_conditional_suite.py`
- `config/script_lifecycle.yaml`

## 可改檔案

- 新增 `scripts/verify_regime_conditional_research_contract.py`
- 刪除兩支舊 verifier
- 更新 `tests/test_regime_conditional_suite.py`，或新增一支 focused parity test
- 更新 `config/script_lifecycle.yaml`
- 新增 `.work/CLEANUP-30/status.md`、`result.md`、`evidence/parity.json`

## 必須保留的契約

- profile：`hybrid_report`、`shadow_rankings`
- 每個 profile 的 verification schema version、所有 check 名稱／順序／value／ok、summary、artifact 路徑
- valid 與 invalid fixture 的完整 normalized payload parity
- CLI 的必填參數、預設 output、console JSON 與 exit code
- hybrid：capital matrix、required sides、missing、decision safe、production/model mutation false
- shadow：date/family counts、rows accounting、sample output existence、training/production mutation false
- CLEANUP-29 builder tests 必須改用新 verifier 並持續通過

## 不可改

- 每日報牌、publish、模型、權重、正式 ranking、launchd、plist、automation
- builder 的產出契約與既有研究 artifact
- 其他 verifier 或研究結論

## 驗收證據

- frozen valid／invalid parity，涵蓋兩個 profile 的 payload、console 與 exit code
- `uv run pytest -q -p no:cacheprovider <focused-tests>`
- `uv run python scripts/audit_script_references.py --strict-new`
- `uv run python scripts/audit_script_lifecycle.py --strict-new`
- `uv run pytest -q -p no:cacheprovider`
- `git diff --check`
- daily 四檔 SHA-256 與 CLEANUP-29 基線完全相同

## 交付限制

- 只建立單一 atomic commit，不 merge、不 push。
- 若 parity 無法證明，保留舊入口並回報 blocker，不可硬刪。

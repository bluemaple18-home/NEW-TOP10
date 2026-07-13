# REFACTOR-05 Result

## Status

ACCEPTED：三組 exit-rule 契約已收斂為 builder／verifier suite，舊六入口的退休條件已由逐欄 parity 證據滿足；staged audits、完整 pytest 與控制檔 hash gate 全部通過。

## Evidence

- `evidence/parity.json`：三個 profile 的 builder valid／invalid、verifier valid／invalid 與 Markdown normalized hash 均與舊版一致。
- `tests/test_exit_rule_validation_suite.py`：16 tests passed。
- `evidence/verification.txt`：主專案完整 pytest 180 passed、28 subtests passed；syntax、diff 與四個每日控制檔 hash gate 通過。

## Scope

- 新增 `scripts/build_exit_rule_validation_suite.py`。
- 新增 `scripts/verify_exit_rule_validation_suite.py`。
- 刪除三支舊 builder 與三支舊 verifier。
- lifecycle 六筆舊例外換成兩筆 suite 例外。

## Remaining risk

未執行正式研究 artifact 產生流程；suite 保留三個 profile 的原始欄位、checks 與失敗語意，後續若調整研究規則仍需各自補 parity 測試。

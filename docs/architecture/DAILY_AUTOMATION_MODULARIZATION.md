# Daily automation modularization

`scripts/run_automation.py` 保持正式 CLI 與 composition root 身分；可獨立測試的契約已收斂到 `app/automation/`：

- `daily_contract.py`：production status 與 Daily V2 共用的核心 step 名稱、順序與 production-equivalent attestation。
- `daily_orchestrator.py`：每日主要流程及最終 report／payload 的既有執行順序。
- `execution.py`：命令正規化、dry-run 與 subprocess outcome；是否中止仍由 runner 套用原本的 `allow_failure` 政策。
- `status_contract.py`：status path、snapshot 與 summary schema。
- `pipeline_policy.py`：resource profile 與 pipeline window 政策。

## 不變契約

- launchd、shell wrapper 與 `scripts/run_automation.py` 的入口不變。
- ETL、validate、ranking、附屬 evidence、postcheck、report、payload 的順序不變。
- report 與 payload 仍只在主要 daily status 為 `OK` 且先落盤後執行。
- subprocess 非零 exit code 仍先記錄 `FAILED`；除非呼叫端明確 `allow_failure`，否則立即中止。
- 本次不切換 Daily V2、不修改模型、排名、發布與排程設定。

## Production-equivalent 邊界

Parity CLI 的 `--workflow-profile production-equivalent` 不是授權。workflow manifest 必須包含 `production_equivalence`，並綁定 `top10.daily-core-contract.v1` 且明確 attested；缺少時 parity 為 `NO-GO`。目前 Daily V2 fixture 沒有此證明，因此 production switch 持續封鎖。

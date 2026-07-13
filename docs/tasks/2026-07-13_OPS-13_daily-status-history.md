# OPS-13｜Daily Status 歷史證據保留

- status: ready
- priority: P0
- task thickness: strict

## 目標

避免週末或後續 `SKIPPED` 執行覆蓋 `artifacts/automation_status.json` 後，指定交易日的 publish verifier 無法驗證先前成功結果。新增按 run date 保存的 daily status snapshot，canonical latest status 與正式發送流程維持不變。

## 依賴與 frontier

- 依賴：REFACTOR-12 automation status contract 已完成。
- 現況證據：2026-07-12 的 `SKIPPED` 已覆蓋 latest status，導致 `--date 2026-07-09` 無法核對當日 status。
- frontier：只做 additive history contract；不得回填或改寫既有 artifact。

## 可改檔案

- `app/automation/status_contract.py`
- `scripts/run_automation.py`
- `scripts/verify_daily_publish_workflow.py`
- 對應 tests（可新增）
- 本卡 status/result

## 不可改

- `scripts/run_daily.sh`、`scripts/run_daily_publish.sh`
- plist、config、排程與 live send 設定
- ranking/model/data、既有 status schema 與 canonical latest path
- 不得執行正式 daily、send、launchctl reload 或歷史 backfill

## 實作契約

1. daily 每次 status 寫入時，除 canonical latest 外，另保存 deterministic dated snapshot；OK、FAILED、SKIPPED 都需可追溯。
2. snapshot 必須是同一份 payload，不新增或刪除既有 JSON 欄位；寫入需避免半檔。
3. `verify_daily_publish_workflow.py --date` 優先讀指定日期 snapshot；未提供日期時維持 latest 行為。
4. 舊資料沒有 snapshot 時要明確回報 `historical status unavailable`，不得拿 latest 冒充。
5. wrapper 的 stale-send guard 與 send exit code 不得改變。

## 驗收

- table tests 覆蓋同日 latest、歷史 dated、週末覆蓋、缺歷史 snapshot、FAILED/SKIPPED。
- automation status、publish workflow、wrapper guard 既有測試全通過。
- live 控制檔 hash 不變；`git diff --check` 通過。

## 回報

建立單一 atomic commit；回報 SHA、fixture 證據與剩餘風險，不 merge、不 push、不 reload。

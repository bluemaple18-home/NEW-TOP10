# DOC-16｜Automation 指令契約一致化

- status: completed
- priority: P2
- task thickness: minimal

## 目標

清理 `docs/AUTOMATION.md` 仍出現的舊 `uv run --with-requirements requirements.txt` 操作指令，使現行操作統一使用 repo `.venv`／lockfile workflow；歷史事故與舊任務證據不改寫。

## 依賴與 frontier

- 依賴：環境契約與 `uv.lock` 已完成。
- blocker：無。
- frontier：只改 active operational instructions。

## 可改檔案

- `docs/AUTOMATION.md`
- `tests/test_environment_contract.py`（必要時）
- 本卡 status/result

## 不可改

- scripts、app、config、plist、dependencies、lockfile
- `docs/operations/incidents/` 與既有 task result 的歷史命令
- 不執行 daily、send、reload

## 實作契約

1. 現行 command blocks 改用 `.venv/bin/python` 或專案已定義的 `uv run --locked`；選擇需與 `run_daily.sh` 契約一致。
2. 不把本機絕對路徑寫入文件。
3. 文件需清楚區分「正式排程入口」與「人工 verifier」。
4. 加強 environment contract test，避免 active automation docs 再出現 `--with-requirements`。

## 驗收

- environment contract tests 通過。
- `rg` 確認 active automation instructions 無舊命令；`git diff --check` 通過。

## 回報

建立單一 atomic commit；回報 SHA 與變更行號，不 merge、不 push。

## Verification

- `docs/AUTOMATION.md` 已移除 active automation 區塊中的 `--with-requirements`。
- `tests/test_environment_contract.py` 已新增 `docs/AUTOMATION.md` 的 allowlist 驗證。
- `git diff --check` 通過。

## Result

- active automation 文件命令已統一為 repo `.venv/bin/python` 入口。
- 歷史事故與舊任務證據未改寫，且未碰 scripts/config/plist/lockfile。
- 驗證命令可重跑，且環境契約測試通過。

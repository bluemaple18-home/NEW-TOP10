# REFACTOR-14｜Clawd Publish Payload 邊界拆分

- status: done
- priority: P1
- task thickness: strict

## 目標

把 1600 行的 `scripts/build_clawd_publish_payload.py` 拆成薄 CLI／artifact I/O adapter 與可測試的 `app` payload domain；輸出 schema、訊息文字、排序與 daily publish 呼叫方式完全等價。

## 依賴與 frontier

- 依賴：TEST-09 publish wrapper fixture 已完成。
- blocker：無。
- frontier：先拆 boundary，不改文案策略、不新增訊號、不調 ranking。

## 可改檔案

- `app/publishing/`（可新增 package/module）
- `scripts/build_clawd_publish_payload.py`
- payload 相關 tests／fixtures（可新增）
- 本卡 status/result

## 不可改

- `scripts/run_daily.sh`、`scripts/run_daily_publish.sh`、sender、plist、config
- payload schema version、JSON 欄位、key semantics、Markdown 內容與排序
- ranking/model/data、產業與概念來源資料
- 不得執行 live send 或正式 daily

## 實作契約

1. script 只保留 argparse、路徑解析、檔案載入/寫入與 exit code；domain transform 放入 `app`。
2. domain 不解析 CLI，不直接寫 artifacts；外部 lookup/config 以明確輸入或 loader boundary 提供。
3. 保留既有 script public imports 的必要相容入口，先盤點 consumers 再搬移。
4. 以固定 daily report fixture 比對完整 payload（允許只正規化 `generated_at` 與輸出絕對路徑）及完整 Markdown。
5. production wrapper hash 與呼叫參數不變。

## 驗收

- payload targeted tests、publish wrapper guard、daily publish workflow static checks 全通過。
- CLI fixture 產物與舊 golden 深度相等；無 live send。
- `py_compile`、`git diff --check` 通過。

## 回報

建立單一 atomic commit；回報 SHA、golden 差異證據與剩餘風險，不 merge、不 push。

## Result

- `scripts/build_clawd_publish_payload.py` 由 1600 行縮成 110 行，只保留 CLI、report/artifact I/O、exit code 與既有 import compatibility adapter。
- payload schema、排序、文案與 transform 搬到 `app/publishing/clawd_payload.py`；domain 以參數明確接收四組 lookup/config，不解析 CLI、不讀 CSV、不寫 artifact。
- reference/config CSV 載入集中在 `app/publishing/clawd_payload_io.py`，作為唯讀 loader boundary。
- 已保留現有 consumer 使用的 `build_payload`、`ai_feature_names`、`classified_publish_sections`、`notification_summary`、`raw_signal_texts` script imports。
- 未修改 wrapper、sender、automation runner、config、plist、ranking/model/data；未執行 live send 或正式 daily。

## Verification

- golden fixture：`tests/fixtures/clawd_publish_payload/`；只正規化 `generated_at` 與 payload 內的本機絕對路徑。
- 重構前後完整 payload 深度相等；canonical SHA-256：`37048ba26fcb7c8e6ffd0e8c711cce549732afe8939e76883c3f32b649a83aa2`。
- 重構前後完整 Markdown byte-for-byte 相等；SHA-256：`55410700707fb0bf7e8a1a498905c709e9d92b2acfa4db13e64354c2a615f875`（7680 bytes）。
- `.venv/bin/python -m pytest tests/test_clawd_publish_payload_boundary.py tests/test_daily_publish_wrapper_guards.py -q`：`5 passed`。
- `.venv/bin/python scripts/verify_daily_tape_and_rr_guard.py`：`DAILY_TAPE_RR_GUARD_OK`。
- publish wrapper guard：兩個 fake-project cases 全通過，send failure 保留 exit 7、catch-up success exit 0；未觸發 production sender。
- daily publish workflow static check：`status=OK`、`errors=[]`、`warnings=[]`。
- `py_compile` 與 `git diff --check`：通過。
- production wrapper SHA-256 維持不變：`run_daily.sh=3a0a0905a9f24f79938eb8a5d24c4c0d20bf841833ce0a5c07b078be4718f4a3`；`run_daily_publish.sh=ff001af0c95d100d7e077bf1a6735f488e36234dadd4a8d73223486d747e84c3`。
- repo-wide pytest：`152 passed, 1 failed, 16 subtests passed`；唯一失敗是 fresh worktree 缺少未追蹤的 research evidence/data，`research_component_ledger` 的 `evidence_exists` check 失敗，與本卡路徑無關，依 allowlist 未處理。

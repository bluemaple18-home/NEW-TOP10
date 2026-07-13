# REFACTOR-14｜Clawd Publish Payload 邊界拆分

- status: ready
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

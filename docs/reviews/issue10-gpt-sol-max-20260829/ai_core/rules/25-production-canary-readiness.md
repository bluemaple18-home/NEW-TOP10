# Production Canary Readiness Gate（全域）

## 目的與適用範圍
- 適用於任何會在 production 建立、派送或推進 canary 的專案與工作流；低流量、測試資料或人工觸發也不例外。
- canary 派工前必須先以正式入口完成 capability probe，並保存 capability receipt。`dry-run`、sandbox 或可回復的 synthetic probe 可以作證據，但不得以建立真正 canary 來證明 readiness。
- 本規則只判斷完整鏈路是否已被證明，不取代產品 pipeline、發布權限、容量安全或人工核准。

## 強制完整鏈路
Capability receipt 必須逐步涵蓋 `create → run → select → publish → transaction → tag → push`。每一步都必須保存：

1. **正式入口**：實際會被 production 使用的 command、script、API 或 tool identifier；mock、臨時 shell 片段與只存在文件中的入口不合格。
2. **I/O 契約**：具體 inputs 與 outputs，足以確認上一步輸出如何成為下一步輸入。
3. **Identity / correlation**：執行者或資源 identity，以及同一條鏈共享的 correlation ID；名稱相似、時間接近或人工猜測不算關聯。
4. **正向證據**：正式入口成功完成代表性 probe 的 artifact，結果必須是 `PASS`。
5. **Fail-closed 負向證據**：缺輸入、錯 identity、錯 correlation、無 selector、publish／transaction／tag／push 拒絕等代表性失敗，必須由相同正式邊界擋下並保存 `BLOCKED` artifact。

`transaction`、`tag`、`push` 是三個獨立 capability，不得合併成單一「發布成功」訊號。selector 的存在不等於 select 已可執行；tag 或 branch 存在也不等於 transaction 與 push 已完成。

## 派工前硬閘門
- 使用 `templates/production_canary_capability_receipt.json` 建立 receipt，再執行：

  ```bash
  <repo-root>/.venv/bin/python <ai-core-root>/scripts/production_canary_readiness_gate.py \
    --receipt <repo-root>/<receipt-path>
  ```

- gate 只驗證 receipt 與 evidence artifact，不代跑 production 動作。輸出只有 `READY` 或 `BLOCKED`；缺欄、空值、證據檔不存在、結果不符、correlation 不連續或任何一步缺失，一律 `BLOCKED`。
- `READY` 前 `canary_created` 必須為 `false`。receipt 通過後仍須另走既有 production approval、儲存容量與發布 gate，不能把 readiness receipt 當成部署授權。
- `BLOCKED` 時先在同一 `execution_line_id` 建立入口修補卡，修正式入口或證據缺口後重跑。不得建立 canary，不得把入口修補、selector 修補與 canary 拆成平行執行線，也不得以另一張 canary 卡繞過原阻斷原因。

## 最小檢查表
- [ ] 七個 capability 都指向 production 正式入口。
- [ ] 每步 inputs／outputs 可串接，identity 明確，correlation ID 全鏈一致。
- [ ] 每步各有獨立、存在的 `PASS` 正向 artifact 與 `BLOCKED` fail-closed artifact。
- [ ] receipt 顯示尚未建立 canary，且 gate 回傳 `READY`。
- [ ] 既有 production approval、容量安全與發布 gate 另行通過。

## 禁止事項
- 禁止用單次 happy path、狀態文案、selector 命中、HTTP 200、tag 存在或 push 命令 exit 0 單獨證明完整鏈路。
- 禁止共用同一 artifact 冒充正向與負向證據。
- 禁止缺能力時先派 canary 再補 receipt，或以修補卡、selector 卡、canary 卡三線並跑規避 fail-closed。

---
id: FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01-RE-REVIEW-02-RECEIPT
status: GO
type: re_review_receipt
original_base_sha: ae187d286d70f1c5ffed86798e9a4a53abfb5103
rejected_candidate_sha: 33309e921a6b460967c9c96f30da5fca5630b075
repair_candidate_sha: 62c31c37e1f575991e5f6eea4b96953dc465115b
---

# Re-review 02 Receipt

## Verdict

`GO`

完整審查範圍固定為
`ae187d286d70f1c5ffed86798e9a4a53abfb5103..62c31c37e1f575991e5f6eea4b96953dc465115b`；
repair delta 固定為
`33309e921a6b460967c9c96f30da5fca5630b075..62c31c37e1f575991e5f6eea4b96953dc465115b`。
未把 re-review card commit `e53753a6d436bc60def478dac5bccf5de0047d0b` 納入 code review range。

## Original Findings Closure

- `P1-01 identity confusion`：`CLOSED`。
  - 有 `topic_id` 時，default-v2 canonicalization 先要求 raw `combo_id` 與 raw topic＋dimensions 導出的 v2 identity 完全一致；mismatched row 保留 raw identity。
  - 無 `topic_id` 時，只接受同時具備完整 base suffix 與 non-empty topic key 的 expanded identity。
  - lifecycle child 的 default-v2／non-default-v2 先驗 raw child identity，再映 parent；mismatched child 不會把 combo 映到 parent。
  - 原離線 probe 由 `false_positive=True` 轉為 `raw_identity_preserved=True / false_positive=False`。

- `P1-02 cross-invocation replay`：`CLOSED`。
  - 同日期先前為 `NO_PROGRESS / no_progress` 或已為 `BLOCKED / unchanged_no_progress_identity`，且 representative identity set 未變時，candidate 會在 replay command 前寫入 `BLOCKED` 並 exit 1。
  - 第二、第三次相同 identity invocation 都不再呼叫 replay；identity set 改變後恢復一次 replay 嘗試。
  - `StartInterval=900` 仍會啟動 wrapper，且 parent 仍接收 exit 1；但 Repair 02 明確不改 wrapper／LaunchAgent，只要求阻擋相同 queue 的昂貴 replay。此候選已符合該契約。

## Findings

- [P2] 損壞或缺 identity 的 prior progress 尚未形成一致的結構化降級契約 — `scripts/run_representative_replay_drain_worker.py:66`
  - prior progress JSON 被截斷或不是合法 JSON 時，`read_json()` 直接拋出 `JSONDecodeError`；這會在 replay 前停止，容量面屬 fail-closed，但不會產生新的結構化 `BLOCKED` artifact/event。
  - prior progress 的 `latest_queue` malformed 或 identity 為空時，`unchanged_no_progress_identity()` 在 `scripts/run_representative_replay_drain_worker.py:292` 回傳 false；因無法證明 identity 相同而 fail-open。different-date progress 同樣 fail-open，符合 per-date recovery。
  - 有效 candidate-generated `NO_PROGRESS/BLOCKED` artifact 均帶 non-empty identity，因此不影響本次 P1 closure；建議後續將 JSON parse failure與 same-date terminal-but-unusable identity 明確分類為 `BLOCKED / invalid_previous_progress`，並補不執行 replay 的測試。

未發現 P0／P1 阻塞問題。

## Spec Axis

- `FR-01`：通過；valid default-v2 evidence 只關閉對應 base/default，mismatched topic/combo 不誤歸戶，且 expansion count 不重複增加。
- `FR-02`：通過；non-default v2 維持 expanded identity 與 expansion count。
- `FR-03`：通過；正常 default-v2 completed evidence 可經 canonical history 關閉 base scenario，供 inventory／queue 重建排除 pending。
- `FR-04`：通過；單輪仍要求 non-forced append 或 identity change，zero-progress 第一批後停止。
- `FR-05`：通過；單輪產生 `NO_PROGRESS / no_progress`，後續同日期相同 identity invocation 在 replay 前 `BLOCKED`；force append 仍不偽造 evidence progress。
- `SC-01`：通過；base、non-default v2、lifecycle child default/non-default、mismatched child 與 bounded queue 相關 suites 綠。
- `SC-02`：通過；未改 ranking、model、weights、promotion、topic supply、wrapper 或 LaunchAgent 設定。
- `SC-03`：通過 re-review 邊界；僅執行離線 tests/probes，未做 live、runtime artifact/log、LaunchAgent、circuit、deploy、push 或 merge 操作。

## Standards Axis

- Correctness：兩項原 P1 均以 negative regression 與獨立 probe 關閉；有效 progress artifact 的 suppression/recovery 資料流正確。
- Regression：lifecycle child × default-v2、child × non-default-v2、mismatched child 與無 topic history shape 已有直接覆蓋。
- Testing：核心負向路徑與跨 invocation state transition 已由 temp/mocks 覆蓋；P2 degraded progress parsing/empty identity 尚缺 main-level regression。
- Unattended runtime fail-closed：相同有效 identity 不再執行昂貴 replay。每 15 分鐘 wrapper 仍會觸發並留下 blocked status/event，屬明訂 scope，不構成本卡阻塞。
- Maintainability：guard 重用 per-date progress artifact，狀態與 stop reason 可稽核；P2 的 damaged-artifact 分類可再收斂。
- Security/privacy/performance：未見 secret、PII、權限或 production boundary 擴張；核心重播 compute 已有 durable suppression。

## Tests

- 兩個原 P1 negative tests：`2 passed`。
- Targeted map/drain/lifecycle：`17 passed, 2 subtests passed`。
- Affected weekend/Fog：`38 passed, 6 subtests passed`。
- P1-01 原始 ad-hoc probe：`raw_identity_preserved=True`、`false_positive=False`。
- Prior-progress helper probes：same-date `NO_PROGRESS=True`、repeated `BLOCKED=True`、different-date `False`、empty identity `False`、malformed shape `False`；malformed JSON 讀取為 `JSONDecodeError`。
- Changed Python in-memory compile：PASS。
- Debug audit（`DBG-`、`pdb`、`breakpoint(`）：PASS，無 matches。
- `git diff --check`（完整範圍與 repair delta）：PASS。
- Repair commit `62c31c3` exact changed-file allowlist：PASS；review card／receipt 未由 repair commit 修改。
- Review worktree 未自建 `.venv`；pytest 使用既有 uv 管理的 `.venv` interpreter、cwd 固定在 re-review worktree，並停用 bytecode/cache 寫入。
- 未獨立重跑 full suite；repair evidence 記錄 `633 passed, 254 subtests passed, 1` 個 isolated-worktree evidence availability failure，該既有缺口不抵銷本次 review findings。
- CodeGraph 在 re-review worktree 未初始化；查詢失敗後依規則改用限域 `rg` 與 fixed diff/source inspection。

## Remaining Risks

- prior progress JSON 損壞時缺結構化 blocked evidence；same-date terminal artifact 若遺失 identity，guard 無法證明相同而 fail-open（P2）。
- `latest_by_combo()` 的 base/default canonical collision 仍依既有 `finished_at` 字串排序契約；本 repair 未改該函式，也未新增 mixed-timezone 測試。
- 15 分鐘 wrapper 仍會觸發 initial refresh/linkage 並寫 blocked status/event；昂貴 replay 已阻擋，但上線前仍須以容量安全閘門確認 artifact/log 增長監控與自動停損。
- 本 re-review 未做 live acceptance；依 SC-03 與容量安全政策維持禁止。

## Final Decision

`GO` — 原兩項 P1 已關閉，未發現新的 P0／P1。P2 degraded-progress 邊界保留追蹤，不阻塞本 candidate。

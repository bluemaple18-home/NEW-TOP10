---
id: FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01-REVIEW-RECEIPT
status: NO_GO
type: review_receipt
base_sha: ae187d286d70f1c5ffed86798e9a4a53abfb5103
candidate_sha: 33309e921a6b460967c9c96f30da5fca5630b075
---

# Review Receipt

## Verdict

`NO_GO`

固定審查範圍為
`ae187d286d70f1c5ffed86798e9a4a53abfb5103..33309e921a6b460967c9c96f30da5fca5630b075`；
未審查 review-card commit `c5e17f5d5bbfd87bc0f271ea268320890ac2fd7f`。

## Findings

- [P1] mismatched `topic_id` 的 default-v2 evidence 會被誤歸到另一個 base scenario — `app/research/map_contract.py:224`
  - 觸發條件：一筆 completed v2 row 同時帶有 `topic_id`，但 raw `combo_id` 的 topic prefix 與該 `topic_id` 不一致；只要 `combo_id` 以 default-v2 suffix 結尾，`completed_default_v2_base_combo_id()` 就回傳 truthy。
  - 實際行為：`canonicalize_lifecycle_history()` 在 `app/research/map_contract.py:287` 把這個 truthy 結果當作布林授權，忽略 raw prefix，改用 row 的 `topic_id` 重算 base combo。離線 probe 以 raw `other|...|regime_gate_ALL|risk_guard_NONE|entry_filter_TOPIC_DEFAULT` 加上 `topic_id=research:target`，得到 canonical `target|...`，可直接把 unrelated evidence 標到 target base scenario。
  - 風險：違反 FR-01「對應 base/default scenario」與 evidence fail-closed；錯誤或混線 history 可讓未完成座標退出 queue，屬重要研究狀態資料錯誤。
  - 建議修法：有 `topic_id` 時，先以原始 topic（lifecycle child 尚未映到 parent 前）與 dimensions 重建 expected raw v2 combo，只有 exact match 才允許 default-v2 canonicalization；lifecycle child 通過 raw identity 驗證後再映 parent。無 `topic_id` 的既有 representative row 則保留嚴格、可驗證的 combo shape/suffix 路徑。補 mismatched topic/combo 必須保持原 identity 的 regression test。

- [P1] `NO_PROGRESS` 只阻止同一 process 的後續 batch，無法阻止下一個 15 分鐘排程週期重播 — `scripts/run_representative_replay_drain_worker.py:430`
  - 觸發條件：queue identity 與 appended evidence 持續不變。candidate 在第一批設為 `NO_PROGRESS` 並於 `scripts/run_representative_replay_drain_worker.py:498` exit 1；既有 `scripts/run_fog_research_worker.sh:380` 將 exit 1 傳成整體 worker failure，但 replay failure 不會寫入既有 retry circuit。`scripts/com.new-top10.fog-research-worker.plist:14` 仍以 `StartInterval=900` 再次啟動。
  - 實際行為：離線以同一 144-ID queue 連續呼叫兩次 `main()`，結果為 exits `[1, 1]`，且 `representative_replay_batch_1` 執行兩次。單輪由 6 批降為 1 批，但 unattended runtime 會每 15 分鐘重播同一批，直到外部狀態改變。
  - 風險：FR-04 的單輪 stop-loss 有效，但 FR-05「不進行後續重播」與 unattended fail-closed 未完整成立；原本的重播／artifact／log 容量風險只是跨排程週期延後，並未終結。
  - 建議修法：另開獨立 Repair 卡，在允許的 runtime 邊界內保存 no-progress fingerprint（至少 run date、queue identity、evidence watermark），下一次 invocation 在 evidence/identity 未變前必須在 replay 前 skip；或把 replay no-progress 納入可驗證恢復的 circuit。只有 identity/evidence 改變或人工驗證恢復後才解除。不得在本 review 操作 LaunchAgent 或 circuit state。

## Spec Axis

- `FR-01`：未通過。正常 fixture 能把無 `topic_id` 的 default-v2 row 映到 base，且不計 expansion；但缺少 raw combo/topic 一致性驗證，存在可重現的錯誤歸戶。
- `FR-02`：目前實作路徑未見 non-default v2 identity/count regression；candidate 的單一 non-default fixture 通過。
- `FR-03`：正常 default-v2 fixture 通過 base scenario closure；但 P1 mismatched identity 可錯誤關閉別的 scenario，因此不能接受為完整通過。
- `FR-04`：同一 drain invocation 通過；zero append 且 identity 不變時第一批後停止，forced append count 不被視為新 evidence。
- `FR-05`：未通過 unattended 邊界。artifact 為 `NO_PROGRESS / no_progress` 且單輪不再跑第二批，但下一個 `StartInterval=900` invocation 仍可重播相同 identity。
- `SC-01`：base、non-default v2 與既有 lifecycle base test 綠；缺 lifecycle child × default/non-default v2 組合與 canonical collision/latest-by-combo 測試，尚不足以完整證明不退化。
- `SC-02`：通過；candidate diff 未改 ranking、model、weights、promotion、topic supply 或排程設定。
- `SC-03`：通過 review 邊界；只執行離線 tests/probes，未執行 live Fog、LaunchAgent、circuit、deploy、push 或 merge。

## Standards Axis

- Correctness：`NO_GO`；兩項 P1 分別造成 evidence 錯誤歸戶與跨 invocation 重播。
- Regression：既有 lifecycle base 與 non-default v2 基本路徑未見退化；combined lifecycle-v2 與 latest collision 缺直接覆蓋。
- Testing：targeted 與 affected suites 綠，但測試只驗單次 `main()`，且 default-v2 fixture 沒有 `topic_id`/`combo_id` mismatch negative case，未覆蓋兩項阻塞風險。
- Unattended runtime fail-closed：單輪 fail-closed、跨 15 分鐘 invocation 不 fail-closed。
- Maintainability：progress evidence 明確保留 before/after identity 與 append 資訊，可稽核；但 terminal 狀態目前沒有跨 invocation ownership/恢復契約。
- Security/privacy/performance：未見 secret、PII、權限或 production 變更；跨週期重播仍有不必要 compute、artifact 與 log 增長風險。

## Tests

- Targeted：`13 passed`。
  - `tests/test_research_map_contract_boundary.py`
  - `tests/test_representative_replay_drain_worker.py`
  - `tests/test_representative_replay_lifecycle.py`
- Affected weekend/Fog：`38 passed, 6 subtests passed`。
- Offline negative probe：mismatched raw combo topic `other` + row `topic_id=research:target` 被 canonicalize 成 target base；`false_positive=True`。
- Offline repeated-invocation probe：同一 144-ID zero-progress fixture 連跑兩次 `main()`，exits `[1, 1]`，batch 1 被執行兩次。
- `git diff --check ae187d2..33309e9`：PASS。
- Candidate exact changed-file allowlist audit：PASS。
- Review worktree 未自建 `.venv`；以上 pytest 使用既有 uv 管理的 `.venv` interpreter、cwd 固定在 review worktree，並停用 bytecode/cache 寫入。
- 未重跑 full suite；candidate evidence 記錄 `629 passed, 252 subtests passed, 1` 個既有 isolated-worktree evidence availability failure，本 review 不以該紀錄抵銷上述 findings。
- CodeGraph 在 review worktree 未初始化；依 repo 規則於查詢失敗後改用限域 `rg` 與 fixed diff/source inspection。

## Remaining Risks

- 尚無 negative test 證明 default-v2 canonicalization 只接受與 topic/dimensions 一致的 raw identity。
- 尚無 lifecycle child × default-v2、lifecycle child × non-default-v2 的直接 regression test。
- 尚無 base/default canonical collision 下 `latest_by_combo()` 的先後順序測試。
- 尚無整合測試涵蓋 `NO_PROGRESS` → parent worker exit → 下一個 scheduled invocation 的 suppression/recovery 契約。
- 本卡禁止 live acceptance、LaunchAgent/circuit 操作；任何 runtime 修復仍須先通過容量安全閘門。

## Final Decision

`NO_GO` — 兩項 P1 阻塞；需要獨立 Repair 卡後重新 review。P2/P3 無法抵銷 Spec axis 與 unattended runtime fail-closed 的失敗。

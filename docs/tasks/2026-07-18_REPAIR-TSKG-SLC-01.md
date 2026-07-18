---
card_id: REPAIR-TSKG-SLC-01
chain_id: TSKG-SLC-01
generation: 1
status: REPAIR_READY
type: repair
owner: Codex 主線
assignee: 獨立 Repair thread
thickness: standard
risk: medium
model: gpt-5.5
reasoning: high
model_reason: 邊界清楚的 identity temporal/schema/test 修復，需跨數檔與負向測試
base_candidate_sha: 7e8006be813be627317a1087744615dafb547a81
review_commit: 040f3806ecdcea9e7580f2586b9850312d48862a
review_thread_id: 019f70ff-7ce1-72e3-9038-500533156cac
evidence_path: docs/evidence/REPAIR-TSKG-SLC-01/
---

# REPAIR-TSKG-SLC-01

任務：只修 REVIEW-TSKG-SLC-01 的 F-01～F-04，產生 successor candidate。
範圍：`app/tskg/**`、fixture、SLC-01 tests/evidence、本卡與 Repair evidence。
禁區：不改 production API/requirements，不連外，不實作 SLC-02。
驗證：負向 temporal/schema/compound-key tests、原 13 tests、compile、allowlist、diff check。
證據：`docs/evidence/REPAIR-TSKG-SLC-01/repair.md`。

## Required repairs

- F-01 P1：實作 accepted v1.1 endpoint discriminator；current lookup 只接受有效 interval；支援 explicit effective instant；同 `(market,code)` 只拒絕 overlap，允許不重疊 code reuse。補 expired/future/malformed/overlap/non-overlap/boundary tests。
- F-02 P2：fixture closed-schema fail loud。驗證 required/unknown fields、entity/security enum、uppercase market、非空 code syntax、issuer/evidence reference、duplicate entity/alias record、alias closed shape。
- F-03 P2：recursive prohibited-key scanner 對 snake/camel/kebab compound keys 做 semantic token 檢查；補 `prediction_score`、`target_price`、`buy_signal`、`stop_loss` nested negative cases。若只改 test helper，必須確保 candidate output 仍通過。
- F-04 P3：shared evidence 只寫 `<main-workspace>/.venv/bin/python`；本機絕對路徑不得留在 committed docs。

## Temporal constraints

- 不自行發明 ingestion/business date。Resolver 接受 injected/effective instant；API current lookup 使用 injectable clock 或明確 deterministic default，測試固定時間。
- UNKNOWN business endpoint 不得當作 expired；UNBOUNDED 表示無界；KNOWN timestamp 使用 UTC ISO-8601。
- 非重疊 code reuse若未提供 effective instant且多筆可能有效，回 ambiguity；不得靠輸入順序選擇。

## Acceptance

- 原 13 tests 不退化，新增負向 tests 全通過。
- reviewer 的 expired-Security probe 不再 RESOLVED。
- malformed fixture matrix全部 fail loud。
- shared docs hardcoded `/Users/` scan 無輸出。
- 只回報 DELIVERED_CANDIDATE；完整 SHA/parent/changed files/tests/evidence/blockers。

## Result

待 Repair thread 填寫。

---
card_id: REVIEW-TSKG-MFO-01
status: REVIEWED_NO_GO
reviewed_on: 2026-07-20
reviewed_candidate: 11c68e9c32812a394788c95bc69a8763a92a8929
reviewed_base: 13349cc9ee038a2577d763f4f0c0390c182d734f
verdict: NO_GO
---

# REVIEW-TSKG-MFO-01 independent review

## Lineage 與 preflight

- Review card HEAD：`0c2a8773216ca3645546a225f383c84db9ad1206`。
- HEAD parent／reviewed candidate：`11c68e9c32812a394788c95bc69a8763a92a8929`。
- Candidate base：`13349cc9ee038a2577d763f4f0c0390c182d734f`；`git merge-base --is-ancestor` 通過。
- 執行位置為獨立 detached review worktree，且不等於 main worktree。
- Review 前 worktree 與 index clean；實際 git-dir 無 `index.lock`。
- Candidate 相對 base 只有卡片 allowlist 內 6 個檔案；`git diff --check` 通過。

## Findings

### [P2] RFC 3339 欄位接受非 JSON `datetime` 物件 — `app/tskg/flow_observation.py:257`

觸發條件：呼叫公開 `SecurityFlowObservationFixture.from_mapping()`，把 `observed_at` 或 `retrieved_at` 換成 aware UTC `datetime`。兩個 probe 都被接受，因為共用的 `parse_utc_instant()` 同時接受 `datetime | str`。

風險：MFO-01 明定這兩欄是 RFC 3339 UTC 字串；目前 mapping 入口可建立無法由 JSON 表達的 observation，使 closed schema 與 `from_file()`／`from_mapping()` 行為不一致，也讓型別 gate 不完整。

建議修法：MFO validator 在呼叫 `parse_utc_instant()` 前先要求兩欄皆為 `str`，並加入 `datetime`、list、dict、null、bool 的 table-driven negative tests。

### [P2] 語法損壞 JSON 漏出非契約例外 — `app/tskg/flow_observation.py:88`

觸發條件：`from_file()` 讀到例如 `{` 的 invalid JSON。mocked file probe 實際得到 `JSONDecodeError`，而不是 `FlowObservationContractError`。

風險：呼叫端無法只依 MFO-01 公開契約例外處理 malformed fixture；Review card 要求 malformed JSON 不漏出非契約例外，現有 7 個 focused tests 也未覆蓋 syntax error。

建議修法：只捕捉 `json.JSONDecodeError` 並轉譯成 `FlowObservationContractError`（保留 exception chaining），再補一個 invalid-JSON file test；不要吞掉 `OSError` 等檔案系統錯誤。

## 驗證證據

### Malformed JSON 與 schema 邊界

- 109 組 table-driven probes：top-level、provenance、evidence、observation、container/item 與所有 scalar 欄位的 list／dict／null／bool confusion。
- 結果：`109/109` 均由 `FlowObservationContractError` 拒絕；無 unhashable `TypeError`、無意外接受。
- JSON top-level list／null／bool：均由 `FlowObservationContractError` 拒絕。
- Invalid JSON syntax：重現 `JSONDecodeError`（P2）。
- Aware UTC `datetime` 注入 `observed_at`／`retrieved_at`：兩案均被接受（P2）。
- duplicate observation ID、semantic key、evidence ID、dangling source/evidence、retrieved-before-observed、freshness/is_stale coherence 由 focused tests 覆蓋並通過。

### Contract、scope 與 regression

- Raw-only 禁區：未出現 5d/20d、price、acceleration、force、anomaly、Theme aggregation、RelationshipClaim 或交易／預測欄位。
- Fixture provenance 明示 `SYNTHETIC_FIXTURE` 與「不代表真實市場數值」；無 source approval 或外部 ingestion 暗示。
- `app.tskg` 可匯入並公開 `FlowObservationContractError`、`SecurityFlowObservationFixture`；既有 `__all__` exports 保留。
- Exact allowlist：`PASS`；無 API、UI、Top10 runtime、dependency、secret、本機絕對路徑或外部存取變更。
- `git diff --check 13349cc9..11c68e9`：`PASS`。
- Combined regression：

```text
<main-worktree>/.venv/bin/python -m unittest \
  tests.test_tskg_mfo01 tests.test_tskg_slc01 tests.test_tskg_src01
Ran 46 tests in 1.113s
OK
```

獨立 review worktree 沒有自己的 `.venv/bin/python`，因此使用專案既有 main-worktree `.venv` 的 Python 3.11.14 執行器；cwd 與 imported `app/tskg/flow_observation.py` 均解析到本 review worktree。未安裝依賴、未連外。

## Axis verdict

- Spec axis：`NO_GO`。raw-only、provenance、semantic duplicate、UTC ordering、freshness coherence、deterministic order、exact lookup、defensive copy 與 summary 皆符合；但 RFC 3339 timestamp 欄位仍可接受非字串物件，closed-schema type contract 未完整成立。
- Standards axis：`NO_GO`。allowlist、exports、46-test regression 與 109 組 JSON type-confusion probes 通過；但 invalid JSON syntax 仍漏出非契約例外，且對應 negative test 缺失。

## Remaining risk 與 repair allowlist

- Python 3.13：`NOT_RUN`；本次只在 Python 3.11.14 驗證，不能視為 3.13 acceptance。
- `GO` 即使後續成立，也只代表 MFO-01 raw observation 可交由主線整合；不批准 Theme、衍生公式、外部來源、API、UI 或 Top10。
- 最小 repair allowlist：
  - `app/tskg/flow_observation.py`
  - `tests/test_tskg_mfo01.py`

## Machine verdict

`NO_GO`

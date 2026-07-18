---
card_id: TSKG-SLC-01
chain_id: TSKG
title: Offline identity-to-company query
status: INTEGRATED
type: implementation
owner: Codex 主線
assignee: SLC-01 implementation thread
thickness: standard
risk: medium
model: gpt-5.5
reasoning: high
model_reason: 跨 fixture、identity contract、resolver、service、FastAPI router 與行為測試，但邊界已由 v1.1 spec 鎖定且無外部副作用
source_kind: commit
source_sha: 36e83750b39ae586cce8cad348fab79331c367cc
source_branch: codex/tskg-slc-01
mainline_dispatcher: TSKG root thread
previous_card: TSKG-01
previous_implementation_thread: 019f70b1-ca96-7f32-a530-e0740db5645f
previous_review_thread: 019f70cc-1bcc-71e2-906c-140679ae93d3
previous_repair_thread: 019f70d3-676a-7673-aae1-203b2ac5aebe
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/TSKG-SLC-01/
---

# TSKG-SLC-01：Offline identity-to-company query

任務：用純 synthetic fixture 建立 identity resolve 到本地 company query 的第一條可執行垂直路徑。
範圍：fixture → deterministic load/normalize/resolve → company service → standalone FastAPI router → public-behavior tests。
禁區：不接外部來源、crawler、LLM、DB、Neo4j、Postgres、Redis；不掛入既有 production API；不含真實供應鏈或交易邏輯。
驗證：TDD、identity/ambiguity/404/empty-sections/API schema/deterministic rerun、既有 API import smoke、`git diff --check`。
證據：`docs/evidence/TSKG-SLC-01/verification.md`；candidate commit 與完整 changed-file allowlist。

## Root question

在不依賴 crawler、database、scheduler 或外部服務的條件下，能否用固定 fixture 可靠地把 alias／股票代碼解析為 canonical Organization／Security，並透過本地 `/v1/company/{stock_id}` 契約回傳可驗證結果？

## Accepted upstream contracts

- `docs/specs/TSKG_v1.1.md`。
- TSKG-01 mainline acceptance commit `36e83750b39ae586cce8cad348fab79331c367cc`。
- SLC-01 current frontier：AC-01、AC-02、AC-07；SRS-ID-01～05、SRS-SCH-01、SRS-API-01。
- F-06／F-07 是後續 provenance/SLO notes，不阻擋本卡 synthetic path。

## Allowlist

- `app/tskg/**`
- `data/fixtures/tskg/identity_v1.json`
- `tests/__init__.py`
- `tests/test_tskg_slc01.py`
- `docs/evidence/TSKG-SLC-01/verification.md`
- 本卡 status／Result：`docs/tasks/2026-07-18_TSKG-SLC-01_offline_identity_company_query.md`

## Forbidden scope

- 不修改 `app/api/main.py` 或既有 router/service/contract。
- 不修改 `requirements.txt`、環境設定、排程、Docker、CI 或 production 啟動流程。
- 不讀寫 `data/reference/**`、模型 artifacts、ranking、Top10 score 或交易資料。
- 不呼叫網路、browser、LLM、Neo4j、Postgres、Redis 或任何外部服務。
- 不把 NVIDIA、Meta、Tesla 或 `3017` fixture 視為真實供應鏈、客戶、供應商或投資結論。
- 不提前實作 SLC-02 relationship claim、SLC-03 graph expansion 或其他 blocked slice。

## Fixture contract

`identity_v1.json` 必須是 deterministic synthetic/offline dataset：

- 至少 12 個 canonical entities，覆蓋 Organization 與 Security。
- alias groups：`NVIDIA/NVDA/Nvidia`、`Tesla/TESLA`、`Meta/Facebook`。
- `3017` Security 連到一個 issuer Organization；名稱明確標示為 fixture/synthetic，不宣稱真實公司資料。
- 至少一組相同 code 跨不同 market，證明沒有 market 時回 ambiguity、指定 market 後唯一解析。
- 至少一組同 normalized alias 對應不同 jurisdiction，必須回 ambiguity，不得 fuzzy auto-merge。
- 包含 fixture/schema/normalizer version；讀取順序不得影響 canonical output。
- 不含任何 relationship claim、Theme membership、ETF holding 或 supply-chain edge。

## Required implementation behavior

### Identity

- canonical `entity_id` 是 opaque、stable，不能由 display name 即時計算。
- Security identity 以 `(market, code, valid interval)` 解析，code 以字串保存並保留前導零。
- alias normalization 至少執行 Unicode NFKC、trim/collapse whitespace 與 Latin casefold；保存 raw alias 與 normalized alias。
- exact deterministic match 唯一時回 canonical entity；多筆回結構化 `AMBIGUOUS`；零筆回 `NOT_FOUND`。
- 不做 fuzzy merge，不把 stock code 當 Organization ID。

### Company query

- 建立可注入 fixture repository 的 service；module import 不讀檔、不建立全域 mutable singleton。
- `GET /v1/company/{stock_id}` 接受 optional `market`。
- 唯一 Security 解析後沿 `issuer_id` 取得 Organization；不得從名稱猜 issuer。
- response 遵守 v1.1 envelope：`request_id`、`data`、`freshness`、`provenance_summary`、`warnings`。
- `data` 至少包含 `company`、`products`、`themes`、`customers`、`suppliers`、`competitors`、`upstream`、`downstream`、`etfs`。
- 每個集合使用 `{items: [], next_cursor: null}`；因 fixture 沒有 claims，全部必須為空，不得臆造。
- company 回傳 canonical Organization、Security 與 synthetic fixture provenance，不回傳交易欄位。
- unknown stock code → 404 `ENTITY_NOT_FOUND`；ambiguous code/alias → 409 `AMBIGUOUS_ENTITY`；invalid argument → 400 `INVALID_ARGUMENT`，使用一致 error envelope。
- router factory 只供測試或後續 composition 使用，本卡不得 include 到 `app/api/main.py`。

## TDD acceptance cases

1. RED：fixture 尚無實作時，public behavior tests 先失敗。
2. Alias normalization：NVIDIA 三個 alias、Tesla 兩個 alias、Meta/Facebook 各自解析到同一 canonical Organization。
3. Alias collision：同 normalized alias 跨 jurisdiction 回 `AMBIGUOUS`，不得自動合併。
4. Security：`3017` 解析到 fixture Security，再連到 issuer Organization；code 維持字串。
5. Market ambiguity：同 code 跨 market 未指定 market 回 409；指定 market 回唯一結果。
6. Happy path：`GET /v1/company/3017` 回 200 且 envelope/schema 完整，所有 relation sections 為空。
7. Missing/invalid：unknown 回 404、非法 code 回 400，error envelope 穩定。
8. Determinism：相同 fixture 以不同輸入排列載入，canonical serialized response（排除 injected request_id）checksum 相同。
9. Isolation：import `app.api.main` 仍成功，且 OpenAPI 不會因本卡自動新增 TSKG route。
10. Prohibited fields：response 不包含 score、weight、prediction、buy/sell、target/stop 等交易或模型欄位。

## Verification commands

使用 repo 的 `uv + .venv` 契約：

```bash
uv run --with-requirements requirements.txt python -m unittest tests.test_tskg_slc01 -v
uv run --with-requirements requirements.txt python -m py_compile app/tskg/*.py tests/test_tskg_slc01.py
git diff --check
```

不得用 `npm`／`yarn`，不得安裝新 dependency。

## Evidence requirements

`verification.md` 至少記錄：

- RED evidence：第一個有意義失敗與原因。
- GREEN command、test count、結果。
- fixture entity/security/alias/collision counts。
- happy-path response schema 與空集合檢查。
- deterministic checksum 方法與值。
- existing API isolation smoke。
- changed-file allowlist、`git diff --check`、post-commit clean status。
- 未跑項目與剩餘風險；不得宣稱真實資料、production API、DB 或 SLO 已完成。

## Stop conditions

- 需要修改 forbidden path、增加 dependency、連外或決定新架構時，停止回主線。
- fixture 無法滿足 accepted schema時，不得降低驗收；回報 contract mismatch。
- 同一 blocker 累計失敗三次即停，不做第四次嘗試。

## Delivery state

- 執行線完成只能回報 `DELIVERED_CANDIDATE`。
- 必須提供完整 candidate SHA、parent SHA、changed files、驗證結果、evidence path 與 blockers。
- 主線後續建立獨立 Review；執行線不得自稱 ACCEPTED／INTEGRATED／COMPLETED。

## Result

`INTEGRATED`：已建立純 synthetic/offline fixture、具 temporal contract 的
deterministic identity resolver、可注入 company service、standalone FastAPI
router 與 22 個 public behavior tests。初審 F-01～F-04 經 Repair 後，由同一
reviewer 複審判定全部 `RESOLVED`，Spec／Standards 皆 `REVIEW_GO`。
`app/api/main.py`、requirements 與既有 production runtime 均未修改；router
仍未掛入 production API。完整驗證與主線接受證據見
`docs/evidence/TSKG-SLC-01/verification.md`、
`docs/evidence/REPAIR-TSKG-SLC-01/repair.md`、
`docs/evidence/REVIEW-TSKG-SLC-01/review.md` 與
`docs/evidence/TSKG-SLC-01/acceptance.md`。

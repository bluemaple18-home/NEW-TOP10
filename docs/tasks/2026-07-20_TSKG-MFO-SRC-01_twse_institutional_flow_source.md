---
card_id: TSKG-MFO-SRC-01
chain_id: TSKG-MFO
title: TWSE daily institutional flow source-governance dossier
status: IN_PROGRESS
type: research
owner: Codex 主線
assignee: current task
created_on: 2026-07-20
thickness: standard
risk: high
model: gpt-5.5
reasoning: high
model_reason: 來源條款、dataset identity、程式存取、保存及再散布需多份官方證據交叉驗證，且結論會控制後續外部 ingestion
source_kind: commit
source_sha: a938dc1cc7a2545d2587a78647a14bcbd8bc9a6a
operation_level: read_only
evidence_path: docs/evidence/TSKG-MFO-SRC-01/verification.md
deliverable_path: docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md
---

# TSKG-MFO-SRC-01：TWSE 三大法人每日買賣資料來源治理

## Goal

只研究一個候選來源：臺灣證券交易所官方發布的上市股票「三大法人每日買賣／買賣超」資料集或其官方 OpenAPI distribution。

目的為建立逐 dataset／distribution 的 source-governance dossier，判定是否具備送交 source/compliance owner 核准的證據；本卡不自行批准、不呼叫資料 endpoint、不下載資料、不啟動 ingestion。

## External-tool gate

```text
tool/service: public web search/open
operation_level: read_only
connection_status: public pages only; no login/OAuth
schema_checked: search/open only; data endpoint schema is research target, not execution permission
confirmation_required: false
execution_status: pending
evidence: source tracker in dossier
remaining_risk: dataset identity/license/path/rate/retention unknown before research
```

## Official-source boundary

允許唯讀搜尋／開啟：

- `twse.com.tw`
- `openapi.twse.com.tw`
- `data.gov.tw` 中明確標示提供機關為 TWSE／證交所的資料集、授權與 metadata 說明
- 上述官方頁直接連結的政府法規／授權頁

禁止：

- 呼叫 `/exchangeReport/**`、`/opendata/**` 或其他資料 response endpoint。
- 下載 CSV／JSON／XML／PDF／附件或 raw artifact。
- 公司／日期參數查詢、表單提交、登入、註冊、付費、驗證碼。
- rate/load test、crawler、Playwright、自動重試或大量頁面列舉。
- 非官方文章、GitHub、套件、搜尋 snippet 作為結論證據。

## Required research fields

1. Dataset canonical identity、publisher、provider、rights／contact owner。
2. Dataset/metadata page、OpenAPI/OAS documentation locator、distribution media。
3. Terms／legal basis／license、attribution、commercial／derivative／redistribution scope。
4. 明示 programmatic permission 與「文件存在」的區分。
5. Allowed method/path family、version、auth/no-auth。
6. Rate limit、frequency、concurrency、retry/backoff、required UA/contact。
7. Update frequency、business date、late correction／revision semantics。
8. Raw/snippet/metadata retention、redaction、deletion/tombstone/legal hold。
9. Policy version、review/expiry、immutable decision artifact owner。
10. 與 TWSE 一般網站條款、政府 OGL 及 MOPS/Data E-Shop 的 scope separation。

所有欄位只能標記：`FOUND | NOT_FOUND | CONFLICTING | NOT_APPLICABLE`，不可補猜。

## Decision contract

本卡只對一個明確 dataset/distribution 產生：

- `RECOMMEND_APPROVAL_REVIEW`：所有必要治理欄位具官方證據，僅待 owner 簽核。
- `KEEP_BLOCKED`：任一必要欄缺失、範圍不明、條款衝突或 operational contract 不完整。
- `NOT_APPLICABLE`：找不到符合目標的官方 dataset/distribution。

即使是 `RECOMMEND_APPROVAL_REVIEW`，也不得修改 SourcePolicy registry、fixture、MFO runtime 或宣稱 approved。

## Verification

- Source tracker 逐 URL 記錄 `retrieved/retrieved_limited/failed/not_used`、access date、用途。
- 只有成功 retrieved 的官方正文可承載 substantive claim。
- 成功／失敗計數可重現；失敗必須列 recovery 或 gap。
- required-field matrix、scope comparison、decision matrix 與 blockers 一致。
- exact allowlist、host-path scan、`git diff --check`。

## Allowlist

- `docs/tasks/2026-07-20_TSKG-MFO-SRC-01_twse_institutional_flow_source.md`
- `docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md`
- `docs/evidence/TSKG-MFO-SRC-01/verification.md`

## Forbidden implementation scope

- 不修改 `app/**`、`tests/**`、`data/**`、`config/**`、`requirements.txt`、frontend、API、Top10、SourcePolicy registry／fixture。
- 不建立 RawArtifact、Evidence、RelationshipClaim 或真實 `SecurityFlowObservation`。
- 不解除 OQ-SRC-01、SLC-02、MFO-02/03 或 UI-MFR blockers。

## Stop conditions

- 官方來源要求登入、驗證碼、非公開權限或實際 endpoint call 時停止。
- robots、rate、license 或 retention 找不到時記錄 gap，不以試打／負載測試推論。
- 同一 blocker 失敗三次即停止，不做第四次嘗試。

## Result

`IN_PROGRESS`

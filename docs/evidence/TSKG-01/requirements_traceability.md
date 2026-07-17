---
id: TSKG-01-requirements-traceability
status: DELIVERED_CANDIDATE
type: evidence
card: TSKG-01
created: 2026-07-17
---

# TSKG-01 需求追溯矩陣

## 1. Authority 與優先序

追溯來源依優先序為：

1. `docs/tasks/2026-07-17_TSKG-01_executable_spec.md` 的安全、provenance、驗收、allowlist 與 forbidden-scope 契約。
2. 父對話在本卡提供的 TSKG v1.0 authoritative design baseline。
3. `docs/specs/TSKG_v1.1.md` 的保守、可回復精煉決策。

v1.0 未另存 repo 是已知輸入形式，不是 blocker；本卡沒有擴大 allowlist 保存原文。若 baseline 與任務卡衝突，以任務卡為準。

## 2. Baseline requirement index

| ID | Authoritative baseline | v1.1 location / disposition |
|---|---|---|
| BL-01 | Goal：持續更新的 Taiwan Stock Knowledge Graph；回答供應鏈、上下游、共同受惠、AI Server、Top10 與補漲關聯候選 | Spec 2.2、BR-01..04、SRS-INT-01；候選明確排除交易預測 |
| BL-02 | Scope：全部上市、上櫃、ETF，約 2,000+ entities | Spec 2.4、SRS-COV-01、SC-06；以核准 manifest 定正式 count |
| BL-03 | 概念架構 Crawler→Raw→Parser→Extraction→Normalizer→KG→REST→consumers | Spec 8.1；加入 source gate、validation/review、authority/outbox/projection 邊界 |
| BL-04 | 候選技術 Python/Scrapy/Playwright/BS/pdfplumber/Marker/LLMs/Neo4j/Postgres/Redis/FastAPI/Temporal-or-Airflow/Docker | Spec 12 ADR-01..08；全部標為候選 architecture constraint，不是使用者需求 |
| BL-05 | 原始 entity：Company、Theme、ETF、Product、Customer、Supplier | Spec 5.1；Customer/Supplier 是 Organization role，Company/ETF 是 kind/subtype |
| BL-06 | 原始 relationships 全集合 | Spec 6.2；逐一 canonicalize，inverse/symmetry/derivation 明確 |
| BL-07 | 兩條供應鏈示意圖未附 evidence | Spec 1、AC-03、SRS-EVD-01；明確禁止作為事實種子 |
| BL-08 | Company response shape 及 `/company/3017` | Spec 9.2、SRS-API-01、AC-07；名稱只取自核准 fixture |
| BL-09 | 來源 P1–P5 優先序與 intended information | Spec 11；優先序不構成 terms/robots/ingestion approval |
| BL-10 | ETL 原始順序與 LLM extraction entity types | Spec 8；輸出統一 candidate schema，LLM 不直接 promotion |
| BL-11 | Alias groups NVIDIA、Tesla、Meta | Spec 5.2、AC-01、TDS-IDENTITY；只驗 identity，不宣稱關係 |
| BL-12 | Theme taxonomy seed | Spec 7；versioned seed，membership 仍需 evidence |
| BL-13 | 原始 API routes、Top10 expansion、daily update | Spec 9、10、SRS-INT-01；read-only、bounded、evidence-backed |
| BL-14 | Future v2、Non-goals、Success | Spec 2.5、13；v2 排除，success 轉為可量測 gates |

## 3. BRS → User Story

| BRS | User Stories | Business acceptance evidence |
|---|---|---|
| BR-01 | US-01、US-03、US-10 | AC-01、AC-02、AC-12 |
| BR-02 | US-02、US-03、US-05、US-09 | AC-03、AC-04、AC-06、AC-11 |
| BR-03 | US-04、US-07 | AC-05、AC-09 |
| BR-04 | US-06、US-09、US-10 | AC-07、AC-08、AC-11、AC-12 |
| BR-05 | US-05、US-08 | AC-06、AC-10 |
| BR-06 | US-04 | AC-05；SLC-01 current frontier |

## 4. SRS → Acceptance → Verification

| SRS | Upstream | Acceptance | Verification artifact / method |
|---|---|---|---|
| SRS-ID-01 | BR-01 → US-01 | AC-01、AC-02 | TDS-IDENTITY stable-ID/rename cases；schema gate |
| SRS-ID-02 | BR-01 → US-01 | AC-01 | alias/name/code resolution golden cases |
| SRS-ID-03 | BR-01 → US-01 | AC-01 | normalization recompute + version assertion |
| SRS-ID-04 | BR-01 → US-01/03 | AC-02 | collision fixture returns `AMBIGUOUS` |
| SRS-ID-05 | BR-01/02 → US-03 | AC-02 | merge/split lineage + as-of golden cases |
| SRS-SCH-01 | BR-01/02 → US-01/02 | AC-01、AC-04 | canonical schema completeness inspection |
| SRS-REL-01 | BR-02 → US-02 | AC-03 | duplicate canonical/inverse count test |
| SRS-REL-02 | BR-02 → US-02 | AC-03 | relationship matrix schema test |
| SRS-REL-03 | BR-02 → US-02 | AC-03 | symmetric endpoint-order golden test |
| SRS-REL-04 | BR-02/04 → US-02/09 | AC-03、AC-11 | prohibited-transitive + rule trace test |
| SRS-EVD-01 | BR-02/05 → US-02/05 | AC-03、AC-04、AC-06 | promotion rejects missing source/evidence/locator |
| SRS-EVD-02 | BR-02 → US-02 | AC-04 | bitemporal required/open-interval cases |
| SRS-EVD-03 | BR-02/05 → US-02/05 | AC-04、AC-06 | extraction/truth separation and version-field scan |
| SRS-EVD-04 | BR-02 → US-02/03 | AC-04 | compatible aggregation + conflict-set golden test |
| SRS-ETL-01 | BR-03/06 → US-04 | AC-05 | stage schema gates + fail-loud error fixture |
| SRS-ETL-02 | BR-03/06 → US-04 | AC-05 | two-run logical checksum/duplicate count |
| SRS-ETL-03 | BR-03 → US-04 | AC-05 | authority/outbox/projection reconciliation test |
| SRS-ETL-04 | BR-03 → US-04 | AC-05 | checkpoint failure injection + rebuild |
| SRS-EXT-01 | BR-02/05 → US-05 | AC-06 | permission boundary test; LLM output remains candidate |
| SRS-EXT-02 | BR-02/05 → US-05 | AC-06 | deterministic invalid cases + review queue assertions |
| SRS-API-01 | BR-04 → US-06 | AC-07 | `/company/3017` contract fixture |
| SRS-API-02 | BR-04 → US-06 | AC-07、AC-08 | OpenAPI/route contract inspection |
| SRS-API-03 | BR-04 → US-06 | AC-08 | cursor snapshot/depth/limit boundary tests |
| SRS-API-04 | BR-04 → US-06 | AC-08 | status/error envelope/freshness contract tests |
| SRS-API-05 | BR-04 → US-06/10 | AC-12 | fixed benchmark dataset and method report |
| SRS-DIF-01 | BR-03 → US-07 | AC-09 | TDS-DIFF seven-event golden manifest |
| SRS-DIF-02 | BR-03 → US-07 | AC-09 | report schema/count/hash inspection |
| SRS-GOV-01 | BR-05 → US-08 | AC-10 | source-gate missing-decision table tests |
| SRS-GOV-02 | BR-05 → US-08 | AC-10 | deletion/tombstone propagation audit fixture |
| SRS-INT-01 | BR-02/04 → US-09 | AC-11 | claim/evidence path + prohibited trading-field scan |
| SRS-COV-01 | BR-01/04 → US-10 | AC-12 | universe manifest reconciliation |

## 5. Coverage checks

| Check | Expected | Candidate result |
|---|---:|---:|
| BRS with at least one User Story | 6 / 6 | 6 / 6 |
| User Stories with at least one acceptance scenario | 10 / 10 | 10 / 10 |
| SRS with upstream BRS/User Story | 31 / 31 | 31 / 31 |
| SRS with acceptance scenario | 31 / 31 | 31 / 31 |
| Baseline items with v1.1 disposition | 14 / 14 | 14 / 14 |
| Unsupported real supply-chain facts introduced | 0 | 0 |

本矩陣的 `Candidate result` 是文件靜態追溯結果，不是 runtime、source compliance 或 production SLO 驗收。

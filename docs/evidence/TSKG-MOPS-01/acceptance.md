---
card_id: TSKG-MOPS-01
status: INTEGRATED
accepted_on: 2026-07-20
acceptance_kind: research_documentation_only
---

# TSKG-MOPS-01 acceptance

## Accepted scope

- Research card、MOPS source-governance dossier、verification、獨立 Review card 與 Review evidence 已整合至主線。
- Candidate source trace 經獨立 Review 重現：`11 retrieved`（`9 substantive`、`2 limited landing`）／`3 failed`。
- Spec axis 與 Standards axis 均為 `GO`，未發現 P0–P3 finding。

## Decision boundary

- `interactive_web`：`KEEP_BLOCKED`
- `official_api_or_open_data`：`KEEP_BLOCKED`
- `manual_file_download`：`KEEP_BLOCKED`
- MOPS source approval：未核准。
- OQ-SRC-01：未解除。
- SLC-02：維持 blocked。
- Source Gate：維持 fail closed。
- 本次沒有修改 executable policy、registry、fixture、crawler、ingestion、RawArtifact、Evidence 或 claim。

## Evidence lineage

- Research candidate：`d5e9f4660e082b6879490768a56a4385d064c3c5`
- Independent Review：`1540a241ac099e7ebcc129786aa06b2c5522e2ad`
- Dossier：`docs/research/TSKG-MOPS-01_source_dossier.md`
- Verification：`docs/evidence/TSKG-MOPS-01/verification.md`
- Review：`docs/evidence/TSKG-MOPS-01/review.md`

`INTEGRATED` 只代表保守研究文件完成主線整合，不代表任何來源、資料集、API、附件或存取方式獲准使用。

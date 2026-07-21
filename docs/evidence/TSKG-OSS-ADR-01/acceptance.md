---
card_id: TSKG-OSS-ADR-01
status: INTEGRATED
accepted_on: 2026-07-21
acceptance_kind: documentation_and_architecture_decision_only
---

# TSKG-OSS-ADR-01 mainline acceptance

## Accepted scope

- `TSKG-MFO-SRC-01`、`TSKG-OSS-01`、`TSKG-OSS-02` 的研究文件與驗證證據。
- OSS research、host-path cleanup 與 ADR 的獨立 Review artifacts。
- ADR 唯一 primary：`ADAPTER_FIRST_INTERNAL_PATTERNS`。
- 外部專案只作 reference；code license、data rights、endpoint authorization 與 production approval 維持分離。

## Evidence lineage

- Mainline base：`a938dc1cc7a2545d2587a78647a14bcbd8bc9a6a`。
- Research／cleanup／ADR chain tip：`659ff161ffe0be7b8f9840f8f012716b833eab0b`。
- ADR candidate：`dfade37ba0c030d764f1f3b7181cead17a6b3756`。
- ADR independent Review：`659ff161ffe0be7b8f9840f8f012716b833eab0b`，verdict `GO`。
- Acceptance verification：26 個既有 candidate 檔案全在 `docs/`，`git diff --check` 通過，shared-file host-path scan 無匹配，四份 independent Review evidence 均為 `REVIEW_GO`。

## Decision boundary

- MOPS／TWSE／FinMind ingestion：未核准。
- Live connector、rate／retention／redistribution、SourcePolicy 與 production runtime：未核准。
- `ThemeFlowObservation`、graph diffusion、UI radar、Top10 ranking／model mutation：維持 blocked。
- `TSKG-MFO-RM-01` 僅是後續離線實作 frontier；本 acceptance 不替代其獨立 Review 與 mainline acceptance。

`INTEGRATED` 只代表研究、清理證據與架構決策完成主線整合，不代表任何外部資料來源、endpoint 或 production 使用獲准。

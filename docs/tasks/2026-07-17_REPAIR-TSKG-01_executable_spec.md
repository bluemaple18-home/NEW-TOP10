---
card_id: REPAIR-TSKG-01
chain_id: TSKG-01
generation: 1
title: Repair Taiwan Stock Knowledge Graph v1.1 contract
status: DELIVERED_CANDIDATE
owner: Codex 主線
assignee: 獨立 Repair 執行線
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 修復核心 ontology、conflict lineage、temporal encoding 與驗證證據一致性
base_candidate_sha: fad395589c90254ffbf4f0e7292a36920d019298
review_commit: 7ddb092b449af801a4c86fb051a7c98561b1a29b
review_thread_id: 019f70cc-1bcc-71e2-906c-140679ae93d3
evidence_path: docs/evidence/REPAIR-TSKG-01/
---

# REPAIR-TSKG-01：TSKG v1.1 規格修復

任務：只修復 REVIEW-TSKG-01 的 F-01～F-07，產生 candidate successor。
範圍：TSKG v1.1 spec、原 trace／verification、Repair evidence 與本卡 status/Result。
禁區：不得實作 runtime、不得查外部網站、不得修改 reviewer evidence、不得新增未經 review 的功能需求。
驗證：每項 finding 都要有 before/after contract、negative/golden case、trace 與 verification disposition。
證據：`docs/evidence/REPAIR-TSKG-01/repair.md`；交付完整 successor commit，送回原 reviewer re-review。

## Allowlist

- `docs/specs/TSKG_v1.1.md`
- `docs/evidence/TSKG-01/requirements_traceability.md`
- `docs/evidence/TSKG-01/verification.md`
- `docs/evidence/REPAIR-TSKG-01/repair.md`
- `docs/tasks/2026-07-17_REPAIR-TSKG-01_executable_spec.md` 的 status／Result

## Required Repairs

### F-01 P1：供應／客戶 canonical fact

- `SUPPLIES_TO(supplier, customer)` 成為單一 canonical claim。
- `SUPPLIED_BY`、`HAS_CUSTOMER`、`CUSTOMER_OF` 僅作明確定義的 query-derived labels／legacy normalization，不再是可獨立 promotion 的 canonical predicate。
- 補同一句義正反向輸入只產生一個 fact 的 golden case及 API 去重規則。

### F-02 P1：conflict／resolution lineage

- 分離 stable canonical fact identity、assertion/version identity 與 claim ID。
- 定義 conflict set、member assertions、resolution decision、decision evidence、decided_by/at、policy version、selected/rejected/superseded lineage。
- 補完整 state transition 與 known_at round-trip case。

### F-03 P1：temporal wire contract

- 每個 interval endpoint 使用可序列化 discriminator，區分 `KNOWN`、`UNKNOWN`、`UNBOUNDED`，定義 timestamp/inclusion 的合法組合。
- 定義 business-time 與 system-time current row 的唯一表示、非法／空 interval。
- 補 parser→authority→projection→API round-trip matrix。

### F-04 P1：verification integrity

- 不得以章節存在或 ID count 宣稱核心契約 PASS。
- verification 必須引用 F-01～F-03 可判定 invariants、negative/golden cases；尚未執行 runtime 的項目標為 `CONTRACT_PASS/RUNTIME_NOT_RUN` 或等價清楚狀態。

### F-05 P2：confidence API

- calibration ADR 前移除 public `min_confidence`；truth 可用性以 claim state、promotion policy、evidence/review status 表達。
- 若文件保留 extraction confidence，只能是 provenance，不得作跨 extractor truth filter。

### F-06 P2：baseline provenance

- 在既有 evidence allowlist 中保存 immutable source thread ID、canonicalization rule 與 authoritative baseline content SHA-256。
- 每個 BL disposition 連到原始 section label；明確區分 internal ID coverage 與獨立 baseline coverage。
- 不得新增一份會與父對話漂移的未校驗全文副本。

### F-07 P2：performance acceptance

- 固定 benchmark manifest/generator version/seed、graph distribution、expected response sizes、cache state 與 measurement tool contract。
- OQ-PERF-01 明確加入 SLC-07 blocking edges；reference environment 未核准前標 `BLOCKED_FOR_SLO_ACCEPTANCE`，不可 PASS。

## Acceptance

- F-01～F-04 無未解 P1。
- F-05～F-07 有明確修復與可重現驗證；若仍 open，必須正確標 blocker，不可 false-positive PASS。
- 31/31 SRS trace 可維持或合理增修，但不得把計數當作獨立正確性證據。
- `git diff --check` 與 changed-file allowlist 通過，工作區乾淨。
- Repair 執行線只回報 `DELIVERED_CANDIDATE`，不得自稱 findings resolved；是否關閉由原 reviewer re-review 決定。

## Stop Conditions

- 需要超出 allowlist、改 runtime 或改 review evidence時停止回報。
- 同一 blocker 三次失敗即停，不做第四次嘗試。

## Result

- Delivery status：`DELIVERED_CANDIDATE`；不代表 findings resolved／accepted／integrated／completed，須送原 reviewer re-review。
- Successor commit：本次 Repair successor；完整 SHA 由交付回報提供，避免 commit 自參照。
- Changed files：
  - `docs/specs/TSKG_v1.1.md`
  - `docs/evidence/TSKG-01/requirements_traceability.md`
  - `docs/evidence/TSKG-01/verification.md`
  - `docs/evidence/REPAIR-TSKG-01/repair.md`
  - `docs/tasks/2026-07-17_REPAIR-TSKG-01_executable_spec.md`（僅 status／Result）
- Finding dispositions：F-01/F-02/F-03/F-05 `CONTRACT_PASS/RUNTIME_NOT_RUN`；F-04 `CONTRACT_PASS` 且仍待 reviewer；F-06 `PARTIAL/BLOCKED`（`baseline_sha256=PENDING_REPRODUCIBLE_CAPTURE`，依三次停損不做第四次 hash）；F-07 contract `CONTRACT_PASS/RUNTIME_NOT_RUN`、SLO `BLOCKED_FOR_SLO_ACCEPTANCE`。
- Verification：僅 repo/git 靜態 contract checks；未執行 runtime、API、database、benchmark 或外部存取。changed-file allowlist、internal SRS set 31/31、AC/BL sets、`git diff --check` 與 post-commit clean workspace 由本線完成並在交付回報提供。
- Evidence：`docs/evidence/REPAIR-TSKG-01/repair.md`、`docs/evidence/TSKG-01/verification.md`、`docs/evidence/TSKG-01/requirements_traceability.md`。

# REVIEW-TSKG-RSCH-02

Reviewer：Codex 主線（`code-review-gate`）；這是本機 mainline review，不宣稱外部獨立 reviewer。

## Finding 與修正

- `[P2]` `scripts/build_tskg_research_adoption_inventory.py` 的 inventory 採用明示 adoption mode，卻曾以 lifecycle 重新推導 reuse intent；在明示 `REUSE` 的非 production lifecycle 上可能誤標 `ARCHIVE_ONLY`。已改為優先採用 compact metadata 的 `usage_intent`，並補 promotion/model path 回歸測試。

## Re-review

- Spec axis：PASS。整合的是 identity/source/time/conflict/evidence 概念，不是 TSKG runtime；舊研究不全面重跑。
- Standards axis：PASS。closed schema、decision 重算、portable refs、UTC timestamp、deterministic inventory 與 additive metadata 均有測試。
- Correctness／regression：修正上述 finding 後未發現阻塞問題。
- Security／privacy：無 network、secret、credential、外部 process 或全域設定變更。
- Maintainability：契約集中於 `app/research/tskg_evidence_contract.py`；既有 builders 只產 compact 摘要，沒有形成第二套 workflow engine。

Verdict：`REVIEW_GO`（本機整合）。外部 Claude Code／Gemini review 仍可依同一測試與 evidence 重現，但不作為這次 additive integration 的必要條件。

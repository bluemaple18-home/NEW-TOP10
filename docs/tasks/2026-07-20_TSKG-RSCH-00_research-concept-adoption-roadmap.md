---
card_id: TSKG-RSCH-00
chain_id: TSKG-RSCH
title: Research Team TSKG concept adoption roadmap
status: PLANNED
type: roadmap
owner: Codex 主線
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 需要把既有 research queue、component ledger、experiment ledger、evidence 與 promotion 邊界切成不全面重跑的漸進式導入卡
source_kind: commit
source_sha: e0aca9e71c4664badce4f1657c9440ce638a4bb1
main_cwd: <repo-root>
---

# TSKG-RSCH-00：Research Team 概念導入路線

## Root question

如何讓 Research Team 開始採用 TSKG 的 identity、source、time、conflict 與 evidence 思維，同時避免全面重跑舊研究、避免另建大型 runtime，並維持既有 research-only／promotion fail-closed 邊界？

## Adoption policy

- 已完成且不再引用的研究：`GRANDFATHERED`，不重跑、不回填完整資料。
- 已完成但將再次引用、比較、升級或進模型的研究：`CHECK_ON_REUSE`，在使用點做輕量檢查。
- 尚未完成、仍在 queue、shadow、review 或 promotion frontier 的研究：`REQUIRED_NOW`，從下一個 checkpoint 採用新 envelope。
- identity、source、time 或 conflict 缺口足以改變結論時：標記 `RESEARCH_REQUIRED`，另開重驗卡；本路線本身不自動重跑。

## Ordered slices and blockers

1. `TSKG-RSCH-01`：建立再使用風險清冊。這是唯一 frontier。
2. `TSKG-RSCH-02`：建立 additive evidence envelope／verifier；被 `TSKG-RSCH-01 ACCEPTED` 阻擋。
3. `REVIEW-TSKG-RSCH-02`：獨立審查契約；被 `TSKG-RSCH-02 DELIVERED_CANDIDATE` 阻擋。
4. `TSKG-RSCH-03`：最多三項研究試行；被 Review GO 阻擋。
5. Checkpoint：只有 pilot 證明低成本、無誤傷，才開後續 queue／ledger checkpoint integration 卡。

## Global boundaries

- 不重跑全部 research、不修改模型權重、不直接改 promotion verdict。
- 不把 TSKG runtime 掛到 Research Team；只採用概念、schema 與 deterministic checks。
- 不連外、不核准 PUBLIC source、不修改 production ranking、scheduler 或 deployment。
- 既有 artifacts 保持 immutable；新增 metadata／evidence 不得改寫歷史結論。
- 任何需要重新研究的項目必須另卡並保留原研究作為歷史 evidence。

## Success criteria

- 能回答「哪些舊研究不用管、哪些在重用時檢查、哪些現在就要補契約」。
- 高風險缺口 fail loud，但純歷史研究不因缺少新欄位被誤判失效。
- 新研究可逐步使用一致 envelope，且現有 workflow 行為不變。
- pilot 後才決定是否接到 PM queue、component ledger 或 promotion review。

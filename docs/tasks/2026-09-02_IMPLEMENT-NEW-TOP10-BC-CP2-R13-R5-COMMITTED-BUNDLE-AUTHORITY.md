---
id: IMPLEMENT-NEW-TOP10-BC-CP2-R13-R5-COMMITTED-BUNDLE-AUTHORITY
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: strict-core-bounded-implementation
risk: critical
model: gpt-5.5
reasoning: high
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
---

# BC-CP2 R13-R5 committed bundle authority implementation

## 工作名稱 → 正在做什麼 → 現在狀態

`R13-R5 Committed Bundle Authority` → 實作 R13-only唯讀 committed-bundle verifier並納入四個 exact bundle bytes → `READY_FOR_IMPLEMENTATION`

## Fixed parent／contract

- Parent：`3367a68`。
- Architecture authority：`docs/evidence/BC-CP2-R13-R4-FORWARD-RECEIPT-AUTHORITY-CONTRACT/01-contract-decision.md`；其「下一張 implementation card 的固定契約」全文具優先權。
- R13-R2 local source只可從 `/private/tmp/top10new-r13-trusted-date-authority-20260902/artifacts/backtest/r13-r2-20260901-af9c32b/output/` 複製四個 exact allowlisted files；不得重跑、修改或生成替代 bytes。

## Exact changed-files allowlist

只可新增 R13-R4 列出的六檔：

1. `app/research/r13_forward_receipt_authority.py`
2. `tests/test_r13_forward_receipt_authority.py`
3. `artifacts/backtest/r13-r2-20260901-af9c32b/output/ranking_2026-09-01.csv`
4. `artifacts/backtest/r13-r2-20260901-af9c32b/output/.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b/COMPLETE.manifest.json`
5. `artifacts/backtest/r13-r2-20260901-af9c32b/output/.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b/receipts/ranking_2026-09-01.receipt.json`
6. `artifacts/backtest/r13-r2-20260901-af9c32b/output/.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b/model_snapshots/model-ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d.pkl`

`artifacts/*` 只能逐檔 explicit force-add；不得修改 `.gitignore` 或 broad-add directory。

## Implementation contract

- Public API／CLI、canonical manifest path、exact identities/hashes/sizes、output schema、兩個 statuses、gate順序與 stable errors 全依 R13-R4。
- Reader不得有 writer、discovery、glob、generic registry或 caller path/identity/allowlist override。
- `ranking_provenance_admission.py`、`ranking_provenance_receipt.py` 與既有 evidence/tests不得修改。
- Registration只證明 R13-R2 committed evidence；receipt保持 `pending_registration`，`downstream_authority=NONE`。

## 驗收

- R13-R4 列出的正負測試矩陣全部落實；historical audit維持 50 records／300 missing／全 REJECT／authority false。
- Canonical R13 real-bundle test必須在 bundle已進 implementation commit後、固定 SHA 上通過；若測試在 pre-commit 因 `SOURCE_NOT_COMMITTED` fail，先提交 exact六檔，再於同 SHA 重跑並以 follow-up verification回報，不得放寬 committed gate。
- 聚焦 tests、既有 receipt/admission regressions、CLI正負、`git diff --check`通過。
- 實作者只提交 exact六檔；不 merge、不 push、不 deploy、不准入 R14或任何下游。

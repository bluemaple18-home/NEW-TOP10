---
card_id: REVIEW-TSKG-MFO-TPEX-01
chain_id: TOP10-NEXT-WAVE-20260722
status: REVIEW_GO
review_sha: 6398e63340123871bc184e80fcfac73eb1806f38
type: independent-source-governance-review
reviewed_sha: 5a436b1062a8ef6a7ba4908cd6a79f8446dce2c9
owner: independent reviewer
allowlist:
  - docs/evidence/REVIEW-TSKG-MFO-TPEX-01/**
  - .work/REVIEW-TSKG-MFO-TPEX-01/**
  - docs/tasks/2026-07-22_REVIEW-TSKG-MFO-TPEX-01.md
---

# REVIEW-TSKG-MFO-TPEX-01

獨立 Review candidate `5a436b1062a8ef6a7ba4908cd6a79f8446dce2c9`。只審不修，不得呼叫資料 endpoint、註冊、購買、接受條款或建立 adapter。

## 必查

- 只用 TPEx／政府官方 primary sources，重新開啟並核對 dossier 中關鍵 locator。
- dataset identity 與 machine-readable source 是否真實存在。
- automation permission、rate、retention、revision/deletion、redistribution、owner 的 `NOT_FOUND` 是否誠實，不能把 endpoint 存在推論為授權。
- TPEx 網站條款與付費 S35 契約是否足以支持 `KEEP_BLOCKED`。
- candidate allowlist、無 Yuanta secure payload／credential、無 adapter/source policy mutation。
- 使用專案既有 `.venv` 重跑 17 tests、py_compile 與 `git diff --check`。

## 輸出

在 `docs/evidence/REVIEW-TSKG-MFO-TPEX-01/review.md` 記錄 reviewed SHA、primary-source receipts、findings 與 `REVIEW_GO`／`REVIEW_NO_GO`。`REVIEW_GO` 可接受 `KEEP_BLOCKED` 為本卡最終 source decision；不得把它改寫成 source GO。

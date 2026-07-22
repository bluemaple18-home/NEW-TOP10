# TSKG-MFO-TPEX-01 Mainline Acceptance

- canonical base：`558a04f82a9ff164ae6a95a126f8a354bd33ebab`
- package commit：`ecac54440d0eae95ee7aefb830f06da3107e2aac`
- candidate：`5a436b1062a8ef6a7ba4908cd6a79f8446dce2c9`
- reviewed candidate：`5a436b1062a8ef6a7ba4908cd6a79f8446dce2c9`
- review verdict／commit：`REVIEW_GO`／`6398e63340123871bc184e80fcfac73eb1806f38`
- source decision：`KEEP_BLOCKED`

Mainline acceptance 接受 source-governance dossier 與 fail-closed decision，不授權 adapter、endpoint 呼叫、TPEx ingestion 或 TPEx downstream redistribution。Reviewer P2 已以明確區分 candidate、candidate parent/package 與 canonical ancestor 的欄位修正，不影響來源 verdict。

## Rerun

- 17 個 TSKG source／MFO tests：PASS
- py_compile：PASS
- `git diff --check`：PASS
- adapter/source policy mutation：無
- Yuanta secure payload／credential：無

Theme 可繼續以 TWSE-only venue coverage 實作，但必須明示 TPEx blocked，不得宣稱全市場。

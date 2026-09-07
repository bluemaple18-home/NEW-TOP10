# Blind Review A — REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01

只讀審查；不得修改任何檔案，不得讀取 Reviewer B 的 prompt／verdict。先完整讀 `AGENTS.md`、task card、review plan/finding schema與以下 fixed manifest，重算 hash；不符即 `UNVERIFIED`。

- `docs/operations/top10-storage-policy.json` `b9f6d822b2ce0bdf4694d3fd4640c3250cc3b019d2fec602b28df70148e4d8dd`
- `docs/operations/top10-storage-safety.md` `80f07d90a669708c3c02e260137950a41949e3f45dbb9cec0bf8870c345e6f91`
- `tests/test_storage_safety.py` `1ebee4cf2ac2b5dcc5c9b6bea607c5039769f2b8cf269f45d87ba3714bc24fac`

以 correctness／storage safety／security 視角審查：exact subtree 是否真能重現並關閉 live marker 的分類；是否把 sibling bytes/files 納入 hard ceilings；是否誤把整個 artifacts、未知寫入、symlink、cleanup 或 `launch_verified` 放寬；是否需要新 authority。可跑唯讀或 temporary fixture tests，不得操作 production marker、launchd、kickstart 或 deploy。

輸出 `VERDICT: GO|NO_GO|UNVERIFIED`。Findings 必須含 P0/P1/P2/P3、`path:line`、觸發條件、風險、證據、修復驗收；只有 P0/P1 可 NO_GO。最後列已跑驗證、spec axis、standards axis與剩餘風險。

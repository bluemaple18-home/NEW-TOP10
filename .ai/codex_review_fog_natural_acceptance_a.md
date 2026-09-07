# Reviewer A — REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01

唯讀審查 working tree candidate；不得修改任何檔案、不得跑 production、kickstart、launchctl、清 marker、deploy、push 或 commit，也不得讀另一位 Reviewer 結論。

先讀 `AGENTS.md`、task card、`.work/REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01/review/review_plan.md`、candidate source/tests。Base SHA：`40fea630f3b4fe0d508fdc3bca5f5aacdb08b4c4`。

Candidate manifest：

- `app/fog_natural_acceptance.py` `7fc68971d68649fc906288d042b02fa5c209630ead2aba71215fe1e25314a1a2`
- `app/storage_safety.py` `fe155df6c30b9b705c6f84038fb3d9d049a0a200fd74ddfedc92c7b3978185f6`
- `scripts/run_with_storage_guard.sh` `92703cb1cc2c52a3b9dd20932b01b251f35e07a48f7590e56d0bdc1bc5a30f9c`
- `scripts/run_fog_research_worker.sh` `502332eee03ef09fa9c4556da736702aabea295b01158281af729fc200cac738`
- `scripts/write_fog_terminal_evidence.py` `07aaaa1489a69bf92adc0ae44c87bba9711516ffe850bd1fcc7c78fd119f6c98`
- `tests/test_fog_natural_acceptance.py` `f717ebe909820ee759388c9e2eb5eecdfbf5730562dce53b39373e8214cdd9eb`
- `tests/test_storage_safety.py` `ce3140944a86a46d1a060711856614bd75209d71649fcb38fa2419baf7750839`
- `tests/test_fog_storage_validation.py` `73035ba80c31e19572dad4ff6b1bfe5e5e01666d870292f1cd8a2a48bcf9dd88`

請先重算 hashes；不符即 `UNVERIFIED`。按 spec axis 與 standards axis 審查 exact invocation binding、artifact run-date authority、archive cadence provenance、counter chain、symlink/path/TOCTOU、denial/lock gates、non-Fog regression、worker exit/trap failure states與測試缺口。可跑唯讀/temporary fixture tests，但不得寫 repo artifact。

輸出：`VERDICT: GO|NO_GO|UNVERIFIED`；findings 只列可重現問題，包含 `P0/P1/P2/P3`、`path:line`、觸發條件、風險、證據、修復驗收。只有 P0/P1 可 NO_GO；最後列已跑驗證與剩餘風險。不得自行修。

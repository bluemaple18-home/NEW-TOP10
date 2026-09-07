# Targeted re-review — REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01

只複驗原 round-1 findings `F-001`～`F-004` 與 Repair regression；不得以一般新建議移動球門，不得修改任何檔案或執行 production/kickstart/launchctl/marker/deploy/push/commit。

請讀原 task card、`.work/REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01/review/round1.md`、`repair1.md` 與下列 fixed manifest。Base SHA：`40fea630f3b4fe0d508fdc3bca5f5aacdb08b4c4`。

- `app/fog_natural_acceptance.py` `31c78a3be44243a2ab03415cfe516f60ce230fb41bc0521adcfe0948d0d26b30`
- `app/storage_safety.py` `fe155df6c30b9b705c6f84038fb3d9d049a0a200fd74ddfedc92c7b3978185f6`
- `scripts/run_with_storage_guard.sh` `dddf04ba6e640cad55214268eec70000c6b7e9c94364f24b988204dcb1328225`
- `scripts/run_fog_research_worker.sh` `502332eee03ef09fa9c4556da736702aabea295b01158281af729fc200cac738`
- `scripts/write_fog_terminal_evidence.py` `07aaaa1489a69bf92adc0ae44c87bba9711516ffe850bd1fcc7c78fd119f6c98`
- `tests/test_fog_natural_acceptance.py` `d48de129834453c590ce527de4cbe6fe436ef60958eb47b74cfd2386857e41ea`
- `tests/test_storage_safety.py` `987646cee7faaaa32c6494c6a5a7081dfcf7e635db85607654dfae193687e7c0`
- `tests/test_fog_storage_validation.py` `fbbfb5b80047d6379bad12b9a785230ea09bbadd04b27ca1789cbd18d3fbb1bc`

Mainline 對 exact-cadence kickstart finding 的裁決已寫在 round1：Owner 指定 archive cadence 為 verifier且禁止驗收期間 kickstart；現有輸入資訊上兩者不可區分，本卡不新增第二 authority，也不把 PPID直接當 verified。請只判斷實作是否忠實採用該明示契約與 fail-closed evidence gaps。

先重算 manifest；不符即 UNVERIFIED。輸出 `VERDICT: GO|NO_GO|UNVERIFIED`，逐項標 `F-001`～`F-004` resolved/unresolved、附可重現證據。只有原 finding 未關閉或 Repair regression 的 P0/P1 才可 NO_GO；最後列測試與 residual risk。

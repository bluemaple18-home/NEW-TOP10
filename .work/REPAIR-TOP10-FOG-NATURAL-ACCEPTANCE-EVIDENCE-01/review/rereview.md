---
id: REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01-REREVIEW
status: go
type: review-evidence
---

# Repair 1 blind re-review

兩位原 Reviewer 在相同新版 fixed manifest、互不讀取對方 verdict 的條件下均回 `GO`。

- `F-001`：已綁既有 Fog time authority；錯誤 market date fail closed。
- `F-002`：acceptance-sensitive read/publish 已改為 anchored dirfd、`O_NOFOLLOW/O_DIRECTORY` 與 same-fd 驗證。
- `F-003`：舊 pending/0 receipt 只可作 cadence anchor；第一個新合格週期為 1、第二個才為 2。
- `F-004`：共同 wrapper 保留 non-Fog overrides，只有 Fog 自產 metadata。
- 未發現新的 P0/P1 repair regression。

固定 manifest SHA-256：

- `app/fog_natural_acceptance.py`: `31c78a3be44243a2ab03415cfe516f60ce230fb41bc0521adcfe0948d0d26b30`
- `app/storage_safety.py`: `fe155df6c30b9b705c6f84038fb3d9d049a0a200fd74ddfedc92c7b3978185f6`
- `scripts/run_with_storage_guard.sh`: `dddf04ba6e640cad55214268eec70000c6b7e9c94364f24b988204dcb1328225`
- `scripts/run_fog_research_worker.sh`: `502332eee03ef09fa9c4556da736702aabea295b01158281af729fc200cac738`
- `scripts/write_fog_terminal_evidence.py`: `07aaaa1489a69bf92adc0ae44c87bba9711516ffe850bd1fcc7c78fd119f6c98`
- `tests/test_fog_natural_acceptance.py`: `d48de129834453c590ce527de4cbe6fe436ef60958eb47b74cfd2386857e41ea`
- `tests/test_storage_safety.py`: `987646cee7faaaa32c6494c6a5a7081dfcf7e635db85607654dfae193687e7c0`
- `tests/test_fog_storage_validation.py`: `fbbfb5b80047d6379bad12b9a785230ea09bbadd04b27ca1789cbd18d3fbb1bc`

保留風險：在本卡被允許的證據集合內，恰好落在 cadence window 的 manual kickstart 與 natural fire 無法作密碼學區分。本卡不新增第二套 scheduler authority；以 60 秒 drift、明示 provenance method 與「驗收期間禁止 kickstart」的操作約束處理，沒有硬寫 verified。

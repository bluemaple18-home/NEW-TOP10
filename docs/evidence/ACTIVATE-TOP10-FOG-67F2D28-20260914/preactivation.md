# Fog-only 67f2d28 preactivation

- exact runtime checkout：`RUNTIME_CHECKOUT_GO`，commit `67f2d28c9825973eac1beb62d40b7d20c6304d47`。
- affected suite：`207 passed, 39 subtests passed`；resource-budget shell、`py_compile`、`git diff --check` 均通過。
- 兩輪代表性 workload：兩輪 guard exit `0`、status `OK`、child exit `0`、process group quiescent，summary verdict `PASS_CANDIDATE`；無 unknown writes。
- cycle 1：elapsed `2899.14s`、project `+64,278,743 bytes`／`+621 files`、peak RSS `679,116,800 bytes`。
- cycle 2：elapsed `2000.34s`、project `+117,421 bytes`／`+29 files`、peak RSS `804,962,304 bytes`。
- fresh runtime capacity：`PASS`；project `1,446,722,989 bytes`／`13,313 files`、host free `50,265,235,456 bytes`、memory pressure `2`。
- prestate：Fog loaded、not running、StartInterval `3600`，old root `fd93d1b`，runs `25`、last exit `75`。
- old denial marker SHA-256：`84b73c62ac203891c613c37f62139aba37aa09008552e7c49df35efa5625de68`；candidate marker absent；old/new Fog storage locks 均可非阻塞取得。
- activation entrypoint SHA-256：`65860b2f5d02557b91a26b76a6385705864e7eb0b1f3a0f75fc13c953547fdea`，與 `8fe9366` 雙 Reviewer `GO/GO` 版本相同。
- mutable state：只以 `--ignore-existing` 合併 previous runtime 的 `data/artifacts/models`；未複製 logs、locks 或 denial marker。
- decision：`PASS`，可執行既有 Fog-only atomic activation transaction；自然週期 acceptance 仍須另驗。

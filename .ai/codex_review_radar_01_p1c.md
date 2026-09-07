# RADAR-01 P1-C strict independent review

任務：唯讀審查目前 working tree 相對 `5512795` 的 RADAR-01 P1-C diff。先讀 `AGENTS.md`、`docs/tasks/2026-09-07_CARD-RADAR-01-P1-C-SIGNAL-OCCURRENCE-RADAR-PROJECTION.md`、`.work/RADAR-01-P1-C/review/review_plan.json`、`.work/RADAR-01-P1-C/review/diff_entries.jsonl`、`.work/RADAR-01-P1-C/review/finding_schema.json`，再讀實際 source/test diff。

責任：獨立覆蓋 spec axis 與 standards axis，優先找 P0/P1 correctness、input-integrity、deterministic identity、immutability、scope/ranking-authority regression 與 test gaps。特別檢查 malformed/tampered dataclass input 是否一律 stable fail-closed、hit 是否受 exact snapshot/spec/report 邊界約束，以及 nested objects 是否真的不可變。不得先讀任何其他 reviewer verdict。

限制：唯讀；不得修改檔案、commit、push、deploy、碰 Fog/runtime；不得把 P1-D statistics/base-rate 或 P1-E confluence 當成本卡缺漏。可以重跑指定 targeted tests。

輸出：先列 findings，依 P0→P3；每項需 path:line、可重現情境、風險、建議修法、驗證缺口與 confidence。P0/P1 才能 NO-GO；只有 P2/P3 時不得 NO-GO。若無 findings，明確說未發現阻塞問題並列 residual risk。最後給 `GO | NO_GO` verdict；不寫 review artifact。

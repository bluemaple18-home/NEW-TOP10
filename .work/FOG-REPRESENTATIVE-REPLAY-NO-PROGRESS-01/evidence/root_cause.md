---
id: FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01-root-cause
status: CONFIRMED
type: evidence
---

# Root-cause evidence

- Diagnostic exit：`1`
- Artifact status／stop：`OK / max_batches_reached`
- Queue initial／latest：`144 / 144`
- Batches／completed／appended／failed：`6 / 144 / 0 / 0`
- First 24 raw history：present；`LOW_INFORMATION=20`、`REJECTED=4`
- First 24 coordinates：all default v2 (`ALL / NONE / TOPIC_DEFAULT`)
- `is_completed_v2_expansion_record()`：`false`
- Drain command：每批`--start-index 0`

結論：history不存在假說已排除。default-v2 evidence未映射回base/default狀態，使queue
持續pending；drain又沒有batch progress invariant，將單點分類錯誤放大成6批重播。

---
id: REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01-REVIEW-ROUND-1
status: no-go
type: review-evidence
---

# Round 1 blind review

兩位 Reviewer 在相同 fixed manifest、互不讀取對方 verdict 的條件下均回 `NO_GO`。

## Confirmed blocking findings

- `F-001 P1`：artifact/event/path/hash 即使彼此自洽，錯誤或不存在的 market date 仍可通過；必須綁既有 Fog time authority。
- `F-002 P1`：evidence、event 與 archive receipt 的 `lstat → path read/write` 有 TOCTOU；必須改為 anchored dirfd＋`O_NOFOLLOW`＋same-fd `fstat/read/publish`。
- `F-003 P1`：舊 live pending receipt 因缺 terminal evidence 不能作 cadence anchor，導致部署後需三輪而非兩輪；cadence anchor 與 accepted counter qualification 必須分離，舊 receipt 只可證 cadence、不可算 accepted。

## Non-blocking regression finding

- `F-004 P2`：共同 wrapper 無條件取消 non-Fog metadata override；修復需保留 non-Fog 既有語意，Fog 自身仍由 wrapper 產生 metadata。

## Mainline disposition：exact-cadence kickstart

Reviewer A 指出 manual kickstart 若恰好落在 cadence window，與 natural fire 對現有輸入不可區分。這是已知資訊限制；Owner 本輪明確要求只用 `scheduled_at`、`invocation_id`、archived receipt cadence，且禁止 kickstart與新增第二 ledger。Repair 不新增虛假 authority；將 drift 縮緊、明示 `ARCHIVED_RECEIPT_CADENCE_V1` provenance method，並保留「驗收期間不得 kickstart」為操作前提。若要求對惡意 exact-cadence kickstart 具密碼學區分，必須另行擴 scope／authority，不在本卡內假裝完成。

## Mainline RED

`env PYTHONPATH=. .venv/bin/python /private/tmp/fog_acceptance_probe.py` 在 round-1 candidate 輸出：

- `stale_date_verified True 2026-09-06`
- `old_anchor False 0 PREVIOUS_RECEIPT_NOT_QUALIFIED`

Repair 後兩者必須分別為錯日期 rejected，以及舊 pending anchor 讓第一個新合格週期 counter=1。

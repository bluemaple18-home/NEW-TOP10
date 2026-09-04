# Reviewer A fourth review — candidate 3023ed0

- Fixed SHA: `3023ed022b72738c49afca5a3311044a19eb0b72`
- Mode: clean-context、archive-only、未讀其他 reviewer evidence。
- Verdict: `GO`

## Adversarial evidence

- Persistent post-seal mask restore failure：receipt 保留成功拓撲，terminal status 為 `SIGNAL_TEARDOWN_UNCONFIRMED_NO_GO`，CLI exit 75。
- Rollback teardown failure：舊拓撲已恢復，receipt 為 `ROLLED_BACK_NO_GO`，terminal status 仍被 signal teardown NO-GO 覆寫。
- `SIG_SETMASK` no-op：readback mismatch 可被偵測。
- Success control：原 handlers 與 arm-time mask exact restore，CLI exit 0。
- Renamed `ReceiptDurabilityError`：不進 rollback，receipt 與新拓撲一致。
- Cleanup 後 pending signal：只在 staging 與 locks 釋放後交付。

Required six cases `6 passed`；完整 activation suite `57 passed`；無 P0/P1 finding。

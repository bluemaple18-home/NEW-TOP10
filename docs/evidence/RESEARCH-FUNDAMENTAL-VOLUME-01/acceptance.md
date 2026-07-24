# RESEARCH-FUNDAMENTAL-VOLUME-01 Mainline Acceptance

Status: `ACCEPTED`

Integrated／pushed SHA: `01b5e87`

## Lineage

- original integrated research：`4deb72660dce9fc15f44d45e30307eb24f0caae1`
- status／Review card commit：`c28a96f38fb78e754de03213be25391a30edacfb`
- initial independent Review：`REVIEW_NO_GO` at `9a90e5317c8c61745bd7273cdc865019399b9525`
- Repair-1 card：`78c6f3a418f88ceb9d1f2aeb1fddec811c870e2c`
- Repair-1 candidate：`a28036a7797f9d1067698ae387d1a76231e917a8`
- original Reviewer re-review：`REVIEW_GO` at `9f29f3018887ea56e838603f865a5b758e04758e`

## Finding disposition

- F-01／P1：CLOSED — Volume runner 在任何續寫前後驗證完整 ledger invariants；corrupt ledger fail closed，combined receipt 轉 `PARTIAL`，production daily 維持 allow-failure。
- F-02／P2：CLOSED — Fundamental verifier 改為獨立 point-in-time oracle，不 import／呼叫 builder。
- F-03／P2：CLOSED — Volume verifier補齊 config/source hashes、warning-only、no-ranking/no-push 與 59／60／61 boundary。

## Acceptance boundary

- Fundamental 結論仍是 `BLOCKED_DATA_COVERAGE`；不因 verifier 修復而 promotion。
- Volume Climax 仍是 warning-only prospective monitor；`promotion_ready=false`。
- 不改 production ranking、model、feature weights、推播或外部資料來源。
- ignored research inputs／receipts 不進 Git；跨機驗證依固定 hashes provisioning。

## Mainline rerun

- Python compile：PASS
- Fundamental independent verifier：PASS
- Volume corrupt／boundary verifier：PASS
- combined runner／verifier：PASS
- daily orchestration affected tests：`8 passed`
- `git diff --check`：PASS

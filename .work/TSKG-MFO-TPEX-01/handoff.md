# TSKG-MFO-TPEX-01 Handoff

## Decision

`KEEP_BLOCKED`. TPEx has a machine-readable catalog identity, but source gate cannot become GO without explicit TPEx automation permission and a complete operational contract.

## Delivered

- Official-only source dossier with fixed access date and source identities.
- Required-field matrix covering license/terms, automation, rate, retention, revision/deletion, redistribution and owner.
- Verification evidence and candidate status.
- No bounded adapter because the card requires fail-closed behavior when permission is unclear.

## Next safe action

Source/compliance owner should obtain written approval for `tpex_3insti_daily_trading` or separately approve the paid S35 product. The approval must name the exact operation/media, allowed method/path, authentication, rate/concurrency, update/correction semantics, retention/deletion, redistribution/derivative scope, owner, policy version, review date and expiry. Only then may a new card implement a captured/synthetic parser with live fetch default off.

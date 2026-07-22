---
card_id: REPAIR-UI-MFR-01-02
status: VERIFIED_REPAIR_CANDIDATE
---

# Repair verification

## Change boundary

Added only an ASCII lexical allowlist before `date.fromisoformat()`:
`[0-9]{4}-[0-9]{2}-[0-9]{2}`. Added regression coverage for compact and ISO-week
forms. No UI, weekly baseline, ranking, model, runtime, deployment, or prior
review/Repair1 evidence was changed.

## Gates

- Focused radar tests: 9 passed.
- Affected tests: 15 passed.
- Boundary matrix: 51/51 passed.
- Closed schema/CORS/OpenAPI/GET-only: passed.
- Python compile: passed.
- `git diff --check`: passed.
- Frontend typecheck and Vite production build: passed using the identical
  frontend source in a clean worktree and local cached dependencies; this
  worktree's partial node_modules could not complete offline install because
  the klinecharts tarball was absent from the local store. No download occurred.
- Browser radar smoke: passed; see `browser-evidence.txt`.

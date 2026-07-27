# Phase 0 Red Baseline

- captured_at_utc: `2026-07-27T10:53:17Z`
- baseline_sha: `b07b685b07d8a5944a86a92803c4198f96929f4b`
- worktree_state_before_source_fix: tests-only dirty
- contract_sha256: `ea9d2618dfff8efbcbff452415999483a9b5771b4c4ff1aa41c60538aea6bd39`
- autonomous_research_sha256: `eeeb51af2dbe7da14aa315745219a72a08242b49904a2d7bc1e19cb41d98b617`
- matrix_sha256: `ecedb9bc82488bca78d60edb9d72392c2194b69b574b138d14ecdfbc4ec7b7b8`
- phase0_test_file_sha256: `6d43a657f563a19bd4b61d4875f9dfaf8d7a252d8be331d811f5180768afdd84`
- phase0_test_diff_git_hash: `44e050ace6c2e57c4a02b83f81585d58d61abb53`

## Core trust-boundary red

Command:

```bash
.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py \
  -k 'manager_registered_local_family or statistical_family_contract_has_81 or statistical_partition_rejects or available_data_canary_dry_run'
```

Result:

```text
4 failed, 33 deselected in 33.72s
real 34.32
```

The decisive red is
`test_public_matrix_rejects_manager_registered_local_family`. Its fixture builds a
content-addressed pre-registration, receives `REGISTERED` from the append-only registry,
declares the three executed combinations as a `local_profile` correction family, and
supplies six independent episode units with `p=0.015625` and two robust neighbors per row.
The current public matrix authority path returns a family that lets
`multiple_testing_gate()` produce:

```text
ok=true
evidence_complete=true
correction_family_size=3
corrected_alpha=0.016666666666666666
reason_code=ROBUST_CANDIDATE_AVAILABLE
```

The desired rejection assertion therefore fails with `assert True is False`. This is the
preserved executable proof that registry acceptance and a deterministic experiment ID are
currently sufficient for a caller-selected three-combination statistical family.

## Phase 0 contract-test reds

The other three failures are intentionally separate missing-contract seams:

- no immutable `statistical_family_contract()` authority exists;
- no legal-profile union / duplicate / missing validator exists;
- no closed-mode dry-run episode-gap status exists.

They fail with `AttributeError`, not with statistical conclusions, and are not used as proof
of the three-family exploit.

## Existing positive baseline

Command:

```bash
.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py \
  -k 'parameter_universe_inventory_is_deterministic_and_honest or closed_manager_cli_writes_registration_split_and_append_only_trace'
```

Result:

```text
2 passed, 35 deselected in 1.20s
real 1.64
```

This preserves the pre-fix positive facts that the contract enumerates 720 legal
combinations and the closed manager produces an 81-tested / 720-global registration and
append-only state trace. It does not prove the public matrix trust boundary.

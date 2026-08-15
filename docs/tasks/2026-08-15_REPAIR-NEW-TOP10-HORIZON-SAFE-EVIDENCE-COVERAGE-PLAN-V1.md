---
id: REPAIR-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: code-repair
priority: P1
role: repair
cycle: 15
thickness: strict
risk: medium
model: gpt-5.5
reasoning: high
model_reason: Reviewer 已重現單一 P1 authority-root normalization bypass；固定 candidate、固定 finding、core-bounded repair 採 GPT-5.5 high。
rejected_candidate_sha: e8755ba96ca662cf76383cfdb870ad1c9931acec
production_change_allowed: false
network_allowed: false
---

# Repair Horizon-safe Evidence Coverage Plan V1

## 工作名稱

修復 authority-root symlink／traversal normalization bypass。

## 固定 Finding

- `app/research/shadow_replay_coverage_plan.py:386` 在 authority binding 前對 caller path `.resolve()`。
- `--authority-root` 使用 `/tmp` symlink alias，或含 `..` traversal 且最後落到 main worktree，verifier 仍 exit 0／PASS。
- NO-GO 核心結論已由 Reviewer 獨立證明正確，不得改 horizon 或 date semantics。

## 允許修改

- `app/research/shadow_replay_coverage_plan.py`
- `tests/test_shadow_replay_coverage_plan.py`
- 必要時更新 `docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1/coverage_plan.json`，但只限 deterministic verifier identity 漂移。

## Requirements

1. 在任何 `.resolve()` 前驗證原始 authority-root path。
2. 拒絕 `..` component、任何 symlink component、symlink alias、path escape，以及 `absolute() != resolve()`。
3. 合法固定 main authority root 繼續 build／verify PASS。
4. 新增 CLI 級 symlink alias、traversal、nested symlink component 負向測試；全部 controlled fail，零寫入。
5. 不擴大 accepted authority、不改 NO-GO 結論、不新增 fallback。
6. 保持 repo-relative deterministic evidence；production、queue、scheduler、rankings 零 mutation。

## Verification

- Targeted tests與Card E availability regressions。
- Reviewer 原兩個 repro 必須 fail closed。
- Committed verifier、`py_compile`、JSON validation、二跑 byte identity、`git diff --check`。
- 單一 repair candidate commit；clean；不得 merge／push／deploy。

## 交付

- Repair candidate SHA、finding closure證據、tests、diff範圍、剩餘風險。

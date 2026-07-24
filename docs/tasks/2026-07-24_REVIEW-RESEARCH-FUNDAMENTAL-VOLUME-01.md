---
card_id: REVIEW-RESEARCH-FUNDAMENTAL-VOLUME-01
chain_id: RESEARCH-FUNDAMENTAL-VOLUME-20260724
status: REVIEW_NO_GO
type: independent-post-merge-code-and-research-review
ownership: independent reviewer
base_sha: f716883503941320fd8b27a9c88b36576557ed50
reviewed_sha: 4deb72660dce9fc15f44d45e30307eb24f0caae1
reviewed_commits:
  - d97a4f5
  - 4deb726
thickness: strict
risk: research correctness, point-in-time leakage, append-only evidence integrity, daily automation regression
model: gpt-5.6-sol
reasoning: high
model_reason: 跨資料契約與 daily automation 的 post-merge 獨立審查，需檢查 leakage、selection bias、append-only 與 production boundary。
worktree: pending_visible_thread_provisioning
evidence_path: docs/evidence/REVIEW-RESEARCH-FUNDAMENTAL-VOLUME-01/review.md
---

# Fundamental Readiness + Volume Climax Shadow Independent Review

## Review role

只審不修。固定審查範圍為：

```text
f716883503941320fd8b27a9c88b36576557ed50..4deb72660dce9fc15f44d45e30307eb24f0caae1
```

已經 mainline integration 不代表 Review GO；Reviewer 必須獨立重算並檢查這兩個 commit。若 `NO_GO`，只提交 review evidence 與具體 findings，由主線另開 Repair 卡。

## Required review axes

### Fundamental readiness

- as-of join 是否與既有 feature contract 一致。
- D+10 未成熟日期是否排除。
- Top200 universe、30 檔／70% research gate、80% model gate 是否正確。
- `23/1967`、latest `3/200`、`0/252` 是否可獨立重算。
- 低 coverage 正向 IC／spread 是否明確標為 selection-biased hint，未被誤作 promotion。

### Volume climax warning shadow

- frozen signal 是否只有 `volume_ratio_20d >= 1.8 AND long_upper_shadow`。
- warning 是否只在 `RISK_ON` 啟用，其他 regime 僅記 raw signal。
- seal date 後才追加；`ranking_date` 唯一、排序、重跑冪等，既有 observation 不重算。
- source hash、config hash、warning-only 語意及 60-date gate 是否 fail closed。
- daily combined monitor failure 是否維持 research-only、不得阻斷或改寫 production ranking／推播。

## Security／privacy／scope

- 掃描 secret、token、credential、PII、本機絕對路徑。
- 禁止存取元大 secure attachment。
- 禁止外部資料抓取、ranking／model／weight 修改與正式推播。

## Required commands

```bash
<repo-root>/.venv/bin/python scripts/verify_fundamental_point_in_time_readiness.py
<repo-root>/.venv/bin/python scripts/verify_volume_climax_warning_append_only_shadow.py
<repo-root>/.venv/bin/python scripts/verify_overlay_shadow_daily_monitor.py
<repo-root>/.venv/bin/python -m pytest -q \
  tests/test_overlay_shadow_daily_automation.py \
  tests/test_daily_automation_orchestrator.py
git diff --check f716883503941320fd8b27a9c88b36576557ed50..4deb72660dce9fc15f44d45e30307eb24f0caae1
```

## Output contract

在 `docs/evidence/REVIEW-RESEARCH-FUNDAMENTAL-VOLUME-01/review.md` 記錄：

- reviewed base／SHA／tree。
- `REVIEW_GO` 或 `REVIEW_NO_GO`。
- P0–P3 findings，需含 `path:line`、觸發條件、風險與修復驗收。
- Spec axis、Standards axis、commands／exit codes、remaining risks。
- changed-file allowlist 與未重跑項目。

Review thread 只允許新增本 Review evidence 與更新本卡狀態，不得修改 reviewed implementation。

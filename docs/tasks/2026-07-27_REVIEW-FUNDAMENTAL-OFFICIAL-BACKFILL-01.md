---
id: REVIEW-FUNDAMENTAL-OFFICIAL-BACKFILL-01
status: CARD_DRAFTED
type: review
chain_id: FUNDAMENTAL-OFFICIAL-BACKFILL-01
ownership: independent_reviewer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 官方基本面 point-in-time 資料管線會影響後續研究證據，需獨立嚴格審查。
candidate_sha: ae12ef39805e812d86d9a1a8bf3a963b6052a901
base_sha: 09a9fa0
evidence_path: docs/evidence/REVIEW-FUNDAMENTAL-OFFICIAL-BACKFILL-01/
---

# REVIEW-FUNDAMENTAL-OFFICIAL-BACKFILL-01

## 目的

獨立審查 `FUNDAMENTAL-OFFICIAL-BACKFILL-01` candidate，確認 MOPS XBRL 回填、
point-in-time 防偷看契約、coverage artifact 與測試證據足以進入 mainline acceptance。

## 固定候選

- Base：`09a9fa0`
- Candidate：`ae12ef39805e812d86d9a1a8bf3a963b6052a901`
- 審查範圍：`09a9fa0...ae12ef39805e812d86d9a1a8bf3a963b6052a901`
- Reviewer 不得修改 candidate；若 `NO_GO`，回主線另開 Repair 卡。

## Allowlist

- `app/fundamentals/mops_xbrl.py`
- `app/services/fundamental_service.py`
- `scripts/import_mops_xbrl_fundamentals.py`
- `scripts/build_fundamental_point_in_time_readiness.py`
- `scripts/build_fundamental_shadow_scores.py`
- `tests/test_mops_xbrl_fundamentals.py`
- `docs/tasks/2026-07-27_FUNDAMENTAL-OFFICIAL-BACKFILL-01.md`
- `docs/evidence/FUNDAMENTAL-OFFICIAL-BACKFILL-01/**`
- `docs/evidence/RESEARCH-FUNDAMENTAL-READINESS-01/**`

## 禁止範圍

- 不改 ranking、feature promotion、production 權重或 UI。
- 不執行 merge、push、deploy。
- 不把季度 ZIP 的更補正現值宣稱為逐版本歷史真值。
- 不因總體 coverage 過門檻而忽略單一公司、季度、欄位或可用日邊界錯誤。

## 必查項目

1. Spec axis：原卡四項驗收與明確限制是否全部成立。
2. Correctness：taxonomy mapping、單位、負號、合併報表優先、缺值與重複資料。
3. Point-in-time：Q1/Q2/Q3/Q4 保守可用日、as-of query、未來值洩漏。
4. Regression：既有 repository/service、shadow score 與 readiness artifact 相容性。
5. Security/privacy：ZIP/XML/path handling、外部輸入、secret 與本機絕對路徑。
6. Testing：測試是否真正覆蓋上述風險，並重跑受影響與全套測試。
7. Evidence：result、verification、artifact 數字可由命令重現，且限制揭露一致。

## 驗證

至少執行：

```bash
cd <repo-root>
.venv/bin/python -m pytest -q tests/test_mops_xbrl_fundamentals.py
.venv/bin/python -m pytest -q
git diff --check 09a9fa0...ae12ef39805e812d86d9a1a8bf3a963b6052a901
```

若資料 cache 可用，另重跑原 verification 內的 readiness／shadow verifier；若不可用，
明確列為驗證缺口，不得用文件中的既有成功文案替代。

## 交付格式

在 `docs/evidence/REVIEW-FUNDAMENTAL-OFFICIAL-BACKFILL-01/review.md` 寫入：

- 固定 base/candidate/reviewed SHA。
- findings（含 `path:line`、觸發條件、風險、建議修法）。
- 測試與 verifier 命令、結果。
- Spec axis 與 Standards axis 分開結論。
- 最終唯一 verdict：`GO` 或 `NO_GO`。

Reviewer thread 只交付 Review verdict，不得自行接受或整合。

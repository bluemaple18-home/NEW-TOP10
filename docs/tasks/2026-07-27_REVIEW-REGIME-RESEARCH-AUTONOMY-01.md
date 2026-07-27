---
id: REVIEW-REGIME-RESEARCH-AUTONOMY-01
status: CARD_DRAFTED
type: review
chain_id: REGIME-RESEARCH-AUTONOMY-01
ownership: independent_reviewer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 研究治理、封存 OOS 與 multiple-testing 契約若失效會產生錯誤策略結論。
base_sha: 7efda43641118f36b10261b4a04e0278bba941a2
candidate_sha: 5cc87798804a48046cd9698b901e2b1bc8995871
evidence_path: docs/evidence/REVIEW-REGIME-RESEARCH-AUTONOMY-01/
---

# REVIEW-REGIME-RESEARCH-AUTONOMY-01

## 目的

獨立審查 `REGIME-RESEARCH-AUTONOMY-01` candidate 是否完整實作原卡研究憲法，
並確認 `NO_STRATEGY` 是由 fail-closed 證據推導，而非因實作缺口誤判。

## 固定候選

- Base：`7efda43641118f36b10261b4a04e0278bba941a2`
- Candidate：`5cc87798804a48046cd9698b901e2b1bc8995871`
- 範圍：`7efda43...5cc8779`
- Reviewer 不得修改 candidate、merge、push、deploy 或 promotion。

## 必查契約

1. `base_regime + family tag set` 必須 exact match，不能只靠名稱含 regime。
2. transition／`UNKNOWN` 必須排除或獨立處理，不能硬塞。
3. episode-based dev／validation／embargo／sealed OOS 不得時間洩漏。
4. sealed 日期跨實驗重用必須 fail closed。
5. 不同實驗 component stitching 必須產生新 experiment ID 與 fresh sealed data。
6. universal gate 必須逐盤勢成立，不能用全期間平均掩蓋失敗盤勢。
7. parameter universe、combination ID、topic score breakdown 必須 deterministic。
8. multiple-testing／winner's-curse 防護與狀態機不得跳階。
9. 樣本不足、缺 p-value／neighbor evidence 或無合格策略時必須輸出
   `NO_STRATEGY`，不得猜兩百萬組合來源。
10. candidate 不得改 production model、ranking、權重或 promotion。

## 審查方式

- 分開 Spec axis 與 Standards axis。
- 讀原卡、完整 diff、Phase 0 baseline／red evidence、result、verification 與 verifier report。
- 至少找一組 adversarial fixture，嘗試繞過 exact match、sealed reuse、stitching 與 universal gate。
- 確認 verifier 不是只檢查自產 artifact 的自證布林。
- 核對 state transition、hash／ID lineage、append-only／contamination 行為。
- 檢查外部輸入、路徑、無界搜尋、資源成本與隱私風險。

## 驗證

```bash
cd <repo-root>
.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py
.venv/bin/python scripts/verify_regime_research_autonomy.py
.venv/bin/python -m pytest -q
git diff --check 7efda43...5cc8779
```

完整 suite 若因獨立 worktree 缺歷史 artifacts 失敗，必須以可寫隔離 clone 重現並列出
精確 failed checks；不得直接忽略，也不得把環境缺口當 candidate regression。

## 交付

寫入 `docs/evidence/REVIEW-REGIME-RESEARCH-AUTONOMY-01/review.md`：

- 固定 base／candidate／reviewed SHA。
- findings（`path:line`、觸發條件、風險、建議修法）。
- adversarial 測試、完整命令與結果。
- Spec／Standards 兩軸結論。
- 唯一 verdict：`GO` 或 `NO_GO`。

Reviewer 只交付 verdict；不得自行接受或整合。

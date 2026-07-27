---
id: REVIEW-REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01
status: CARD_DRAFTED
type: review
chain_id: REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01
ownership: independent_reviewer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 驗證 statistical-family authority、partition coverage 與 available-data canary 未產生假策略結論。
base_sha: f656c18a6ec716d40c824d83174419abbeaf2530
candidate_sha: 47cd110f17ce0f008de86156820d83436d1072dd
evidence_path: docs/evidence/REVIEW-REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01/
---

# REVIEW-REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01

## 目的

獨立審查 successor candidate 是否封閉小型 fake family 繞過，並確認 81／720、
partition coverage 與 available-data canary 的結果可重現且沒有被包裝成策略結論。

## 固定候選

- Base：`f656c18a6ec716d40c824d83174419abbeaf2530`
- Candidate：`47cd110f17ce0f008de86156820d83436d1072dd`
- Reviewer 不得修改 candidate、merge、push、deploy 或 promotion。

## 必查項目

1. Public matrix CLI 不得接受 caller 自行簽發的 3-combination family。
2. Statistical authority 必須綁 immutable contract hash 與 manager-issued registration。
3. 81 tested IDs 必須全部屬於 720 global IDs，無重複／遺漏，校正分母固定 720。
4. Fake contract、global hash、partition、tested IDs 與 registry alias 必須 fail closed。
5. Partition coverage `242/720` 與缺 `478` 必須可重現；不得宣稱已跑完整 720。
6. Available-data canary 的 `RISK_OFF|`、13 episodes、獨立 units `2/14`、
   `INSUFFICIENT_EVIDENCE` 與 state trace 必須由實際資料推導。
7. Canary 不得修改 production model、ranking、權重或 promotion。
8. Verifier 必須固定 candidate，不能由自產 receipt 布林自證。

## Adversarial Review

- 嘗試重新 content-address 一份 3-family registration。
- 嘗試使用合法 registry record 搭配不同 contract/global family。
- 嘗試 duplicate／missing／out-of-universe tested IDs。
- 嘗試把 `242/720` 改寫成 complete 或把 `2/14` 改寫為 `NO_STRATEGY`。
- 核對 command、input hash、output、timing、counts 與 state trace。

## 驗證

```bash
cd <repo-root>
.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py
.venv/bin/python scripts/verify_regime_research_autonomy.py \
  --base 7efda43641118f36b10261b4a04e0278bba941a2 \
  --candidate 47cd110f17ce0f008de86156820d83436d1072dd
.venv/bin/python -m pytest -q
git diff --check f656c18...47cd110
```

Reviewer 必須從固定 candidate 重新執行 canaries，不得只讀 delivery summary。

## 交付

寫入 `docs/evidence/REVIEW-REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01/review.md`：

- findings
- adversarial fixtures
- canary reproduction
- Spec／Standards axes
- 唯一 verdict `GO`／`NO_GO`
- 完整 reviewed SHA 與 evidence commit SHA

Reviewer 不得自行接受或整合。

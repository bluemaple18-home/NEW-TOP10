# Daily V2 Parity

Daily V2 parity 不直接啟動 production；它只讀四份 evidence：

- production `daily-run-status.v1`
- `top10.daily-workflow-v2.run-manifest.v1`
- `top10.daily-v2.real-shadow-manifest.v1`
- `top10.daily-v2.ranking-comparison.v1`

```bash
uv run python scripts/run_daily_v2_parity.py \
  --production-status <status.json> \
  --workflow-manifest <manifest.json> \
  --real-shadow-manifest <manifest.json> \
  --ranking-comparison <comparison.json> \
  --shadow-root <shadow-root> \
  --workflow-profile fixture

uv run python scripts/verify_daily_v2_parity.py
```

## Production promotion

Parity `GO` 不等於 production switch `GO`。正式 promotion decision 另要求：

- 至少兩個不同日期的 production-equivalent parity GO。
- timeout、partial output、stale input failure injection 全部通過。
- persistent resume 與所有副作用 idempotency 有證據。
- wrapper／launchd rollback 已實際演練。
- script governance 無 production contract gap 與未處理 dynamic import edge。
- 固定 base/candidate SHA 的獨立 review 為 GO。
- file-backed verifier 可由 repo root 以外的位置重算所有來源。
- ranking comparison 由實體 baseline/shadow CSV 重算，不能只驗 comparison JSON digest。
- manifest 內嵌的自簽 attestation 不構成 production-equivalent 信任根。
- repo 內自製的 acceptance/review JSON，即使 schema、digest、固定 SHA 與 exit code 完整，也不構成獨立信任根。

決策 builder 只輸出 `promote` 或 `retain_current_production`，永不執行切換：

```bash
uv run python scripts/build_daily_v2_promotion_decision.py \
  --parity .work/ARCH-UPGRADE-03/evidence/daily_v2_parity.json \
  --parity .work/ARCH-UPGRADE-03/evidence/daily_v2_parity_2026-07-09.json \
  --script-governance .work/ARCH-UPGRADE-05/evidence/script_governance.json \
  --base-sha <reviewed-base-full-sha> \
  --candidate-sha <reviewed-candidate-full-sha>
uv run python scripts/verify_daily_v2_promotion_decision.py \
  --base-sha <reviewed-base-full-sha> \
  --candidate-sha <reviewed-candidate-full-sha>
```

## 判定邊界

- mismatch 固定分類為 `expected_difference`、`contract_gap`、`data_mismatch`、`status_mismatch`、`failure_semantics`、`unsafe_side_effect`。
- `parity.status=GO` 只代表所提供 evidence 行為一致。
- `workflow_profile=fixture` 永遠保留 `production_equivalent_workflow` blocker，不得授權 production switch。
- 目前沒有 repo 外信任根可簽發 production-equivalent、acceptance 與 independent review，因此 production promotion 維持 fail-closed。
- timeout/failure 兩邊一致時可以是 parity GO，但因缺少成功執行證據，production switch 仍是 NO-GO。
- live send、source mutation、run directory 逃出 shadow root 或 evidence 宣稱已切 production，全部 fail closed。

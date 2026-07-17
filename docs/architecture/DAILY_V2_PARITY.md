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

## 判定邊界

- mismatch 固定分類為 `expected_difference`、`contract_gap`、`data_mismatch`、`status_mismatch`、`failure_semantics`、`unsafe_side_effect`。
- `parity.status=GO` 只代表所提供 evidence 行為一致。
- `workflow_profile=fixture` 永遠保留 `production_equivalent_workflow` blocker，不得授權 production switch。
- timeout/failure 兩邊一致時可以是 parity GO，但因缺少成功執行證據，production switch 仍是 NO-GO。
- live send、source mutation、run directory 逃出 shadow root 或 evidence 宣稱已切 production，全部 fail closed。

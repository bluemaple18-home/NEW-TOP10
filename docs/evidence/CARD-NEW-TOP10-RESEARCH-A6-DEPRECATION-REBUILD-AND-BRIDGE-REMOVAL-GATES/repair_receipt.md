# A6 Repair-1 receipt

基線：`bb617e98aabefcc52bbf7cb1834fb5fba715d60a`。修復候選必須以本次提交 SHA 作為 `--candidate-ref`，不可用工作樹狀態取代。

## Fixed-SHA rebuild

在 checkout 該固定 SHA 後執行：

```bash
uv run pytest -q tests/test_research_spine_a6_closure.py tests/test_research_spine_a6_bridge_removals.py
uv run python scripts/verify_research_spine_a6_fixed_fixture.py --base-ref bb617e98aabefcc52bbf7cb1834fb5fba715d60a --candidate-ref HEAD --output /private/tmp/a6-fixed-sha-receipt.json
```

第二個命令以 repo 內 fixture helper 建立包含 A3 migration manifest/record 的 corpus；其 closure output root 是私有暫存目錄。直接 closure CLI 只接受不存在的 output root，或含 `.a6-closure-generated-root` marker 的前次 generated root；repository child、corpus、project 與未標記目錄皆 fail closed。

## P1 closure evidence

- inventory：source-derived surface map 缺任一 bridge 回 `MISSING_SOURCE_BRIDGE`。
- membership：attempt、intent、receipt 的 run/intent/attempt-event 交叉 membership 不一致回明確錯誤。
- bridge removal：每列只接受存在的 bridge-specific pytest function，inventory 自我測試不可作為退場證據。
- scope：`scope_guards` 由 `base..candidate` 的 git diff 計算；diff 不可讀即拒絕。
- surface scan：只掃 `app/research` 與 `scripts` 的 Python source；每個 `run_history` functional surface 都必須由 manifest 指到已盤點 bridge，並在 closure receipt 保存 inputs、matches 與 unmapped。

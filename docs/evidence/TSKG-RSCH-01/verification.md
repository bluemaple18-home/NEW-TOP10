# TSKG-RSCH-01 verification

- Builder：`scripts/build_tskg_research_adoption_inventory.py`
- 測試：`tests/test_tskg_research_adoption_inventory.py`
- 固定日期：`2026-07-20`
- 兩次獨立輸出經 `cmp` 比對相同。
- 結果：21 items；`GRANDFATHERED=2`、`CHECK_ON_REUSE=9`、`REQUIRED_NOW=10`、manual review 0。
- 保護條件：`read_only=true`、`reruns_research=false`、`changes_verdict=false`、`changes_promotion=false`。

結論：清冊可作為導入起點；不要求舊研究全面重驗。

# TOP10 整合候選獨立審查

- objective：獨立裁決整合版是否保留已安裝發布鎖、子程序終止與送達保護，是否有相依遺漏或 no-send 邊界退化。
- scope：docs/evidence/TOP10-INTEGRATED-CANDIDATE-20261022/delivery-import.json、delivery-import.diff、full-code-comparison.json、source-manifest.json 與18個移植檔的直接相依；來源 manifest SHA d6da9efdcafcee8f86a44282c830bcc92bc99dc28745d65efac8c13000429ab7。兩位盲 verdict，A著重鎖／程序生命週期，B著重收據／相依完整性。
- constraints：read-only reviewer；不改code，不建立檔案／工具隔離、不執行正式sender／wrapper、不操作production或外接；不讀另一位review結論。只使用現有受管測試收據與唯讀native查詢；有需執行反例則回傳精確mock case，由主線受管執行。
- acceptance：P0/P1須列可重現觸發、路徑行號與修正；無阻塞則PASS_DEV_INTEGRATION，不能宣稱production放行。standard既有實作移植，因包含supervisor termination，兩位獨立檢查failure states；繼承當前模型，無降級。
- status／evidence：IN_PROGRESS；回歸、兩輪no-send由主線執行，review結果寫入同一 evidence 根；未提供真實外送或production驗收。

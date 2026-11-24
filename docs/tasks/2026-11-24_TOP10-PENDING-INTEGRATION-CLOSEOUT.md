# TOP10 剩餘工作區差異版本整合
- objective：核對並整合目前約1.6萬新增行的程式／測試／文件，完成可追溯本地提交；不再把工作區搬檔稱為版本已結案。
- scope：base 25348435c5049c5d2ac486fe504c8c0abd4d19fd；pending-integration-20261124/final-integration-receipt.json 所列精確 scope 清單（原128份regular檔、本卡與實測所需測試fixture）；歷史symlink／scratch另封存不入程式提交。
- constraints：保留既有內容與回復；不動外接另一份working tree的未提交差異、不push／deploy／恢復review排程、不重送daily或GPT、不改ai-core policy。
- acceptance：現有回歸工具驗證受影響路徑、兩份獨立審查無未解P0/P1、來源hash可核對、本地commit記錄完整、工作區沒有漏掉的程式差異。
- status：LOCAL_COMMIT_READY；程式與測試凍結供最後雙人複核；提交成功後以 final-integration-receipt.json 的 commit_sha、精確清單與驗證結果結案。受限原生案例明列未驗，正式啟用不放行。先前51測試只證局部，不外推全批。
- evidence：pending-integration-20261124/最終 scope、validation-final.json、review-a-final.md、review-b-final.md、final-integration-receipt.json；最終CC回報 CODEX-VERSION-INTEGRATION-TO-CC-20261125.md。

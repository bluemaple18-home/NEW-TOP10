# CLEANUP-21 狀態

狀態：實作完成；必要驗證已執行，存在一項因刪除揭露的後續孤兒與一項 scope 外測試失敗。

範圍：僅刪除三支 `delete_candidate/high` 研究腳本，並從 script reference audit 的核准例外移除對應路徑。

驗證摘要：lifecycle audit 與受影響單元測試通過；reference audit 的 strict-new 因本卡刪除目標原為另一支 script 的唯一 consumer 而失敗，完整 pytest 另有一項不屬本卡 diff 的失敗，詳見 `evidence/verification.txt`。

下一步：建立單一 atomic commit；後續以新卡處理 survivor script 與 ledger 測試，禁止在本卡擴修。

# TOP10 主線整合與推送
- objective：將本機已驗的兩個提交與 origin/main 五個提交整合、驗證並正常推送，消除本機／遠端分岔。
- scope：ours 2e0f04818d05eda214a71a018f19743e654d7f72；remote 4f27bb80b0780f6056f3e9bc2a5a68313d2ccf06；base 25348435c5049c5d2ac486fe504c8c0abd4d19fd；16份衝突與自動合併的遠端改動。
- constraints：保留雙方已驗行為、外接 owned-root／signal／帳號 guard；不force push、不reset／clean、不重跑正式報牌／review、不部署或恢復排程，保留歷史證據與備份。
- acceptance：無衝突或漏併差異；合併後原生十項及受影響回歸通過、獨立複核無P0/P1；本機main推送成功且遠端SHA一致，工作區乾淨。
- status：IN_PROGRESS；19,121新增行已在本機commit，原工作區乾淨；目前已讀取遠端並進入可追溯三方合併，尚未推送。
- evidence：<external-checks>/EXTERNAL-REVIEW-PATH-RESTORE-20261124/formal-review/push-integration-20261125/。

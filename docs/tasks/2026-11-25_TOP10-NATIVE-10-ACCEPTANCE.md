# TOP10 十項原生驗收補齊
- objective：實測補齊前次明列未驗的十項案例，通過後才結案並回報 CC。
- scope：外接 cache confinement 1、source-write probe 1、FOG shared-helper 4、daily lifecycle cleanup 4；基準 3c5a17ca57424edbc9a2e6d9203b0d3d0822aec1。
- constraints：保留原斷言及真實原生隔離；daily／FOG payload 仍走既有外接 lifecycle active owned root；不改 Core／政策、不建環境或常駐服務、不重送報牌／review、不恢復排程。
- acceptance：十項真跑通過；拒寫、真訊號、逾時、來源不變、process group 收束、root／marker 清理及小型 evidence 各有回執；受影響回歸與兩份獨立複核通過；補正本機版本與 CC 狀態。
- status：NATIVE_10_PASS_PENDING_REVIEW_AND_COMMIT；十項同批真跑10 PASS／54.57秒、controller exit0；原巢狀 apply 與誤選coordinator no-fork檢查的失敗紀錄保留。受影響回歸與最終雙人複核、提交仍待完成，以 final-receipt.json 的實際SHA及狀態結案。
- evidence：<external-checks>/EXTERNAL-REVIEW-PATH-RESTORE-20261124/formal-review/native-10-acceptance-20261125/。

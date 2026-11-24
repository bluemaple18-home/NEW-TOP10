# TOP10 授權恢復與外接驗證

- objective：按 Owner「授權」執行已審查的單次開發隔離恢復；接續原順序搬外接，完整回歸與兩輪 no-send。
- scope：exact marker SHA de32b6c7a6d6e183c76a58d7b097f579fc3f84f4e64778f3ca9692bfcc7ad626；舊 root 原地保留；外接候選須容量、卷身分與來源一致性通過。
- constraints：不重開機、不刪舊 root、不改一般 recovery、不解除 ai-core 其他隔離、不部署、不發送；正式 denied/plist 不變，Production NO-GO；內建原件保留回退。
- acceptance：單次恢復完整收據與既有准入 gate 通過；外接候選 source/venv/path 正確；外接完整回歸與兩輪各自獨立 no-send 通過並具容量／清理證據。
- status：EXTERNAL_VALIDATION_COMPLETE / PRODUCTION_NO_GO；外接副本完成，290 passed／61 subtests passed，兩輪獨立no-send各5步成功；內建原件保留。首次LightGBM失敗未定因，單測與完整重跑通過。
- evidence：docs/evidence/TOP10-INTEGRATED-CANDIDATE-20261022/NON-REBOOT-RECOVERY-PROPOSAL.md、owner-authorized-recovery.py、owner-recovery-preflight/。
- decision：Owner 接受本次缺少歷史後代完整停止證據；不把當下空查詢或根保留當作等強證明。
- final_evidence：docs/evidence/TOP10-INTEGRATED-CANDIDATE-20261022/RESULT-20261024.md；後續寫入使用外接工作樹。

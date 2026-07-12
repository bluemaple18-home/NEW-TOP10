from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_research_decision_brief import build_brief
from scripts.build_top10_ops_progress_message import render_ops_message
from scripts.send_top10_ops_report import write_ops_event


class Top10OpsReportTest(unittest.TestCase):
    def test_render_ops_message_includes_blocker_and_external_disagreement(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            rollup_path = artifacts / "harness_status" / "2026-06-24" / "daily-2026-06-24" / "rollup.json"
            rollup_path.parent.mkdir(parents=True, exist_ok=True)
            rollup = sample_rollup()
            external = {
                "valid_provider_count": 2,
                "disagreements": [{"title": "2330 only flagged by gemini", "detail": "risk view opposite"}],
                "today_misses": [{"stock_id": "2317", "reason": "AI thinks setup is stronger than our list"}],
                "safety": {"needs_human_review": True},
            }

            research_brief = {
                "_path": artifacts / "research_decisions" / "research_decision_brief_2026-06-24.json",
                "decision_requests": [
                    {
                        "priority": "high",
                        "title": "外部 AI 檢核有分歧，需要決定後續處置",
                        "recommended_option": "同意轉成研究卡，交給迷霧與研究 worker 排隊驗證。",
                        "options": ["同意轉成研究卡", "先人工複核", "暫時擱置"],
                    }
                ],
            }

            message = render_ops_message(
                rollup,
                external,
                rollup_path=rollup_path,
                artifacts_dir=artifacts,
                research_decision_brief=research_brief,
            )

            self.assertIn("TOP10 工作進度｜2026-06-24", message)
            self.assertIn("阻塞項目", message)
            self.assertIn("資料品質閘門", message)
            self.assertIn("2330 只有這個外部 AI 標記 Gemini", message)
            self.assertIn("2317", message)
            self.assertIn("審核決策", message)
            self.assertIn("待拍板事項：`1`", message)
            self.assertIn("#review-approval", message)
            self.assertIn("外部 AI 檢核有分歧，需要決定後續處置", message)
            self.assertNotIn("同意轉成研究卡", message)
            self.assertNotIn("不能直接改排名", message)
            self.assertIn("需要拍板時會另送 #review-approval", message)

    def test_build_research_decision_brief_collects_external_and_queue_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            external_dir = artifacts / "external_review" / "2026-06-24"
            external_dir.mkdir(parents=True)
            (external_dir / "external_review_summary_2026-06-24.json").write_text(
                json.dumps(
                    {
                        "review_date": "2026-06-24",
                        "valid_provider_count": 2,
                        "disagreements": [{"title": "2330 only flagged by gemini", "detail": "risk view opposite"}],
                        "today_misses": [{"symbol": "2317", "issue": "AI thinks setup is stronger than our list"}],
                        "research_hypotheses": [{"hypothesis": "測試"}],
                        "safety": {"needs_human_review": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            research_dir = artifacts / "autonomous_research"
            research_dir.mkdir()
            (research_dir / "next_action_queue.json").write_text(
                json.dumps(
                    {
                        "actions": [
                            {
                                "topic_id": "strategy-matrix:test",
                                "manager_status": "confirmed_for_next_replay",
                                "next_action": "promote_to_longer_replay_candidate",
                                "score": 42,
                                "last_decision": "CONFIRMED_FOR_NEXT_REPLAY",
                                "candidate_dir": "artifacts/backtest/test_candidate",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (research_dir / "manager_summary.json").write_text(
                json.dumps({"status": "OK", "next_action_count": 1}, ensure_ascii=False),
                encoding="utf-8",
            )
            (research_dir / "research_campaign_progress_2026-06-24.json").write_text(
                json.dumps(
                    {
                        "summary": {
                            "expanded_processed": 10,
                            "expanded_universe_total": 100,
                            "expanded_progress_pct": 0.1,
                            "next_action": "FOLLOWUP_EXISTING_SIGNALS",
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            fog_dir = artifacts / "research_map"
            fog_dir.mkdir()
            (fog_dir / "research_fog_map_verification_latest.json").write_text(
                json.dumps({"status": "OK"}, ensure_ascii=False),
                encoding="utf-8",
            )

            brief = build_brief("2026-06-24", artifacts)

            self.assertEqual(brief["status"], "NEEDS_DECISION")
            self.assertEqual(brief["summary"]["decision_count"], 2)
            titles = [item["title"] for item in brief["decision_requests"]]
            self.assertIn("TOP10 報牌外部檢核有分歧，需要決定後續處置", titles)
            self.assertIn("候選策略已確認可進下一階段 replay", titles)
            self.assertTrue(brief["boundaries"]["does_not_change_ranking"])
            first_card = brief["decision_requests"][0]["pm_card"]
            self.assertIn("card_id", first_card)
            self.assertIn("topic_name", first_card)
            self.assertIn("system_area", first_card)
            self.assertIn("potential_improvement", first_card)
            self.assertIn("decision_point", first_card)
            self.assertIn("next_harness", first_card)
            self.assertIn("decision_boundary", first_card)
            self.assertTrue(first_card["button_labels"]["approve"].startswith("核准 "))

    def test_performance_review_cards_become_pm_review_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            (artifacts / "daily_performance_review_2026-06-24.json").write_text(
                json.dumps(
                    {
                        "schema_version": "daily-performance-review.v1",
                        "date": "2026-06-24",
                        "status": "NEEDS_REVIEW",
                        "summary": {"finding_count": 2, "high_count": 1, "research_card_count": 1},
                        "findings": [
                            {"title": "D+1 平均報酬為負"},
                            {"title": "D+3 bucket 回撤偏大"},
                        ],
                        "research_cards": [
                            {
                                "task_id": "PERF-REVIEW-2026-06-24-ENTRY-TIMING",
                                "purpose": "拆 D+1/D+3 偏弱來源。",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            brief = build_brief("2026-06-24", artifacts)
            performance_decisions = [
                item for item in brief["decision_requests"] if item["id"].startswith("performance-review-")
            ]

            self.assertEqual(len(performance_decisions), 1)
            card = performance_decisions[0]["pm_card"]
            self.assertTrue(card["card_id"].startswith("PERF260624-"))
            self.assertEqual(card["status"], "待決策")
            self.assertIn("報牌", card["topic_name"])
            self.assertIn("TOP10", card["system_area"])
            self.assertIn("核准 " + card["card_id"], card["button_labels"]["approve"])
            self.assertIn("不代表改報牌", card["decision_boundary"])

            message = render_ops_message(
                sample_rollup(),
                None,
                rollup_path=artifacts / "harness_status" / "2026-06-24" / "daily-2026-06-24" / "rollup.json",
                artifacts_dir=artifacts,
                research_decision_brief=brief,
            )
            self.assertIn("審核決策", message)
            self.assertIn("待拍板事項：`1`", message)
            self.assertIn("#review-approval", message)
            self.assertIn("每日報牌復盤觸發研究候選", message)
            self.assertNotIn(card["card_id"], message)
            self.assertNotIn("處理哪裡", message)
            self.assertNotIn("可能提升", message)
            self.assertNotIn("按鈕", message)

    def test_write_ops_event_updates_rollup(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            event_dir = artifacts / "harness_status" / "2026-06-24" / "daily-2026-06-24" / "events"
            event_dir.mkdir(parents=True, exist_ok=True)
            status = {
                "generated_at": "2026-06-24T12:00:00+00:00",
                "run_date": "2026-06-24",
                "run_id": "daily-2026-06-24",
                "status": "OK",
                "message_path": "ops_progress_message_2026-06-24.md",
                "rollup_path": "harness_status/2026-06-24/daily-2026-06-24/rollup.json",
                "output_path": "ops_progress_send_status_2026-06-24.json",
                "dry_run": False,
                "send_attempted": True,
                "exit_code": 0,
                "errors": [],
            }

            write_ops_event(status, artifacts_dir=artifacts, manifest_path=Path("docs/architecture/top10_harness_team.dashboard.json"))

            event_path = event_dir / "ops_reporter.json"
            self.assertTrue(event_path.exists())
            event = json.loads(event_path.read_text(encoding="utf-8"))
            self.assertEqual(event["agent_id"], "ops_reporter")
            self.assertEqual(event["status"], "ok")
            self.assertEqual(event["discord_channel"], "ops_progress_channel")
            latest = artifacts / "harness_status" / "2026-06-24" / "latest_rollup.json"
            self.assertTrue(latest.exists())

    def test_ops_message_includes_pm_research_harness_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            status_dir = artifacts / "pm_research_harness"
            status_dir.mkdir(parents=True)
            status_path = status_dir / "pm_research_harness_loop_2026-06-24.json"
            status_path.write_text(
                json.dumps(
                    {
                        "status": "OK",
                        "topic_runs": 2,
                        "pending_approval_count": 0,
                        "loop_enabled_after": True,
                        "consecutive_no_approval_runs": 3,
                        "max_continuation_runs": 8,
                        "pm_review_cards_sent": False,
                        "pm_review_cards_dry_run": False,
                        "research_artifact": "artifacts/autonomous_research/pm_research_harness_2026-06-24.json",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            from scripts.build_top10_ops_progress_message import load_pm_research_status

            pm_status = load_pm_research_status(artifacts, "2026-06-24")
            message = render_ops_message(
                sample_rollup(),
                None,
                rollup_path=artifacts / "harness_status" / "2026-06-24" / "daily-2026-06-24" / "rollup.json",
                artifacts_dir=artifacts,
                pm_research_status=pm_status,
            )
            self.assertIn("PM 研究核准 loop", message)
            self.assertIn("本輪已執行 2 個研究題", message)
            self.assertIn("研究 loop 仍在延續", message)
            self.assertNotIn("topic runs", message)
            self.assertNotIn("loop enabled", message)

    def test_ops_message_summarizes_strategy_map_without_internal_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            strategy_map = {
                "_path": artifacts / "research_council" / "strategy_archetype_evidence_map_2026-06-24.json",
                "market_thesis": {"label": "強趨勢 + 高波動"},
                "archetypes": [
                    {
                        "priority": 1,
                        "label": "高位防追高型",
                        "current_evidence": {
                            "next_action_count": 13,
                            "followup_signal_count": 0,
                            "evidence_status": "PARTIAL_MECHANISM_EVIDENCE",
                        },
                    },
                    {
                        "priority": 2,
                        "label": "急殺保護型",
                        "current_evidence": {
                            "next_action_count": 14,
                            "followup_signal_count": 20,
                            "evidence_status": "NEEDS_TRIGGER_VALIDATION",
                        },
                    },
                ],
            }

            message = render_ops_message(
                sample_rollup(),
                None,
                rollup_path=artifacts / "harness_status" / "2026-06-24" / "daily-2026-06-24" / "rollup.json",
                artifacts_dir=artifacts,
                strategy_map=strategy_map,
            )

            self.assertIn("目前盤面：強趨勢 + 高波動。", message)
            self.assertIn("優先研究：高位防追高型、急殺保護型。", message)
            self.assertIn("已有部分機制證據", message)
            self.assertIn("先驗證觸發條件", message)
            self.assertNotIn("next_action", message)
            self.assertNotIn("followup", message)

    def test_ops_message_translates_pending_pm_loop_without_empty_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            rollup = {
                "run_date": "2026-06-24",
                "run_id": "daily-2026-06-24",
                "status": "warning",
                "summary": {"agent_count": 15, "event_count": 14, "failed_count": 0, "warning_count": 1, "missing_count": 1},
                "agents": [
                    {
                        "agent_id": "pm_research_harness",
                        "status": "pending",
                    }
                ],
            }

            message = render_ops_message(
                rollup,
                None,
                rollup_path=artifacts / "harness_status" / "2026-06-24" / "daily-2026-06-24" / "rollup.json",
                artifacts_dir=artifacts,
            )

            self.assertIn("等待審核卡或下一輪排程", message)
            self.assertNotIn("沒有細節", message)


def sample_rollup() -> dict:
    return {
        "run_date": "2026-06-24",
        "run_id": "daily-2026-06-24",
        "status": "failed",
        "summary": {
            "agent_count": 15,
            "event_count": 8,
            "failed_count": 1,
            "warning_count": 1,
            "missing_count": 3,
        },
        "agents": [
            {
                "agent_id": "data_quality_gate",
                "label": "data_quality_gate",
                "status": "failed",
                "failure_reason": "coverage below threshold",
                "next_action": "do not publish ranking until data is repaired",
            },
            {
                "agent_id": "external_review_harness",
                "label": "external_review_harness",
                "status": "pending",
                "next_action": "wait for daily OK before external review",
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()

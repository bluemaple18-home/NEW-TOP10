from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.build_pm_clarification_review_cards as clarification_builder
from scripts.build_pm_clarification_review_cards import build_clarification_review_cards


class PMClarificationReviewCardsTests(unittest.TestCase):
    def test_builds_clearer_review_card_from_clarification_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_run_dir = root / "artifacts" / "pm_review_cards" / "source"
            output_run_dir = root / "artifacts" / "pm_review_cards" / "clarification"
            source_run_dir.mkdir(parents=True)
            (source_run_dir / "cards.json").write_text(
                json.dumps(
                    {
                        "schema_version": "top10.pm_review_cards.v1",
                        "project_domain": "TOP10_STOCK",
                        "run_dir": "artifacts/pm_review_cards/source",
                        "cards": {
                            "RH1": {
                                "card_id": "RH1",
                                "project_domain": "TOP10_STOCK",
                                "title": "外部檢核分歧",
                                "owner": "disagreement_next_actions",
                                "next_harness": "disagreement_next_actions",
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (source_run_dir / "RH1.md").write_text(
                "\n".join(
                    [
                        "RH1｜外部檢核分歧",
                        "",
                        "素材/證據：",
                        "- artifacts/external_review/a.json: 可追溯 artifact",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            external_path = root / "artifacts" / "external_review" / "a.json"
            external_path.parent.mkdir(parents=True)
            external_path.write_text(
                json.dumps(
                    {
                        "schema_version": "external-review-summary.v1",
                        "today_misses": [
                            {
                                "symbol": "3163",
                                "name": "波若威",
                                "provider": "gemini",
                                "evidence": "系統列為 Rank 1，但 Gemini 指出開高走低與追高風險。",
                            }
                        ],
                        "tomorrow_watch": {"avoid_chasing": ["3163"]},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (source_run_dir / "clarification_queue.jsonl").write_text(
                json.dumps(
                    {
                        "card_id": "RH1",
                        "project_domain": "TOP10_STOCK",
                        "decision": "needs_review",
                        "title": "外部檢核分歧",
                        "owner": "disagreement_next_actions",
                        "next_harness": "disagreement_next_actions",
                        "run_dir": "artifacts/pm_review_cards/source",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            manifest = build_clarification_review_cards(
                source_run_dir=source_run_dir,
                output_run_dir=output_run_dir,
                date_text="2026-07-09",
                max_cards=5,
            )

            self.assertEqual(manifest["status"], "READY")
            self.assertEqual(manifest["built_count"], 1)
            cards = json.loads((output_run_dir / "cards.json").read_text(encoding="utf-8"))
            new_card_id = manifest["built_cards"][0]["card_id"]
            self.assertEqual(cards["cards"][new_card_id]["source_card_id"], "RH1")
            markdown = (output_run_dir / f"{new_card_id}.md").read_text(encoding="utf-8")
            self.assertIn("補說明重送：外部檢核分歧", markdown)
            self.assertIn("一句話問題", markdown)
            self.assertIn("要你決定", markdown)
            self.assertIn("判斷落差", markdown)
            self.assertIn("我們這邊", markdown)
            self.assertIn("外部檢核", markdown)
            self.assertIn("落差", markdown)
            self.assertIn("證據", markdown)
            self.assertIn("邊界", markdown)
            self.assertNotIn("背景：", markdown)
            self.assertNotIn("目前問題：", markdown)
            self.assertNotIn("請你判斷：", markdown)
            self.assertNotIn("建議動作：", markdown)
            self.assertNotIn("為什麼現在要決定：", markdown)
            self.assertNotIn("要你拍板：", markdown)
            self.assertNotIn("核准後會發生什麼", markdown)
            self.assertNotIn("不核准會停止什麼", markdown)
            self.assertIn("artifacts/external_review/a.json", markdown)

    def test_empty_queue_still_writes_empty_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_run_dir = root / "artifacts" / "pm_review_cards" / "source"
            output_run_dir = root / "artifacts" / "pm_review_cards" / "clarification"
            source_run_dir.mkdir(parents=True)
            (source_run_dir / "cards.json").write_text(
                json.dumps(
                    {
                        "schema_version": "top10.pm_review_cards.v1",
                        "project_domain": "TOP10_STOCK",
                        "run_dir": "artifacts/pm_review_cards/source",
                        "cards": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            manifest = build_clarification_review_cards(
                source_run_dir=source_run_dir,
                output_run_dir=output_run_dir,
                date_text="2026-07-09",
                max_cards=5,
            )

            self.assertEqual(manifest["status"], "EMPTY")
            self.assertEqual(manifest["built_count"], 0)
            self.assertTrue((output_run_dir / "cards.json").exists())

    def test_llm_rewrite_is_used_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_run_dir, output_run_dir = self._sample_source_dirs(Path(tmp))
            llm_markdown = "\n".join(
                [
                    "CL260709-000000-01｜補說明重送：外部檢核分歧",
                    "來源卡：RH1",
                    "狀態：補說明後待決策",
                    "",
                    "一句話問題：外部檢核分歧需要判斷是否進入 research-only 複核。",
                    "要你決定：是否建立 research-only 複核任務；不拍板就不會形成可追溯研究證據。",
                    "判斷落差：LLM 不應保留這段。",
                    "證據：",
                    "- LLM 不應保留這段證據",
                    "邊界：核准只代表 research-only 複核，不代表改正式 Top10、改推播或 production promotion。",
                ]
            )
            with patch.object(
                clarification_builder,
                "rewrite_with_llm",
                return_value=(llm_markdown, {"status": "OK", "provider": "gemini", "selected_model": "gemini-test"}),
            ):
                manifest = build_clarification_review_cards(
                    source_run_dir=source_run_dir,
                    output_run_dir=output_run_dir,
                    date_text="2026-07-09",
                    max_cards=5,
                    use_llm=True,
                    args=object(),
                )

            new_card_id = manifest["built_cards"][0]["card_id"]
            markdown = (output_run_dir / f"{new_card_id}.md").read_text(encoding="utf-8")
            self.assertIn("要你決定：是否建立 research-only 複核任務", markdown)
            self.assertIn("判斷落差", markdown)
            self.assertEqual(manifest["llm_results"][0]["status"], "OK")
            self.assertEqual(manifest["llm_results"][0]["selected_model"], "gemini-test")

    def test_llm_failure_falls_back_to_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_run_dir, output_run_dir = self._sample_source_dirs(Path(tmp))
            with patch.object(clarification_builder, "rewrite_with_llm", side_effect=RuntimeError("llm boom")):
                manifest = build_clarification_review_cards(
                    source_run_dir=source_run_dir,
                    output_run_dir=output_run_dir,
                    date_text="2026-07-09",
                    max_cards=5,
                    use_llm=True,
                    args=object(),
                )

            new_card_id = manifest["built_cards"][0]["card_id"]
            markdown = (output_run_dir / f"{new_card_id}.md").read_text(encoding="utf-8")
            self.assertIn("一句話問題", markdown)
            self.assertIn("要你決定", markdown)
            self.assertEqual(manifest["llm_results"][0]["status"], "FALLBACK")
            self.assertIn("llm boom", manifest["llm_results"][0]["errors"][0])

    def test_short_llm_section_is_replaced_from_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_run_dir, output_run_dir = self._sample_source_dirs(Path(tmp))
            llm_markdown = "\n".join(
                [
                    "CL260709-000000-01｜補說明重送：外部檢核分歧",
                    "來源卡：RH1",
                    "狀態：補說明後待決策",
                    "",
                    "一句話問題：外部檢核分歧需要判斷是否進入 research-only 複核。",
                    "要你決定：半截",
                    "判斷落差：我們這邊看成可追蹤題材；Gemini 看成 avoid_chasing；落差在於動能訊號和追高風險的判讀不同。",
                    "證據：",
                    "- artifacts/external_review/a.json: 可追溯 artifact",
                    "邊界：核准只代表 research-only 複核，不代表改正式 Top10、改推播或 production promotion。",
                ]
            )
            with patch.object(
                clarification_builder,
                "run_gemini",
                return_value=llm_markdown,
            ):
                args = type(
                    "Args",
                    (),
                    {
                        "env_file": "",
                        "models": "gemini-test",
                        "timeout_seconds": 1,
                        "max_output_tokens": 2000,
                        "temperature": 0.1,
                    },
                )()
                with patch.object(clarification_builder, "load_env_file", return_value={}), patch.dict(
                    clarification_builder.os.environ,
                    {"GEMINI_API_KEYS": "fake-key"},
                    clear=False,
                ):
                    manifest = build_clarification_review_cards(
                        source_run_dir=source_run_dir,
                        output_run_dir=output_run_dir,
                        date_text="2026-07-09",
                        max_cards=5,
                        use_llm=True,
                        args=args,
                    )

            new_card_id = manifest["built_cards"][0]["card_id"]
            markdown = (output_run_dir / f"{new_card_id}.md").read_text(encoding="utf-8")
            self.assertNotIn("要你決定：半截", markdown)
            self.assertIn("要你決定", markdown)
            self.assertIn("只有你核准後才會形成可追溯研究證據", markdown)

    def _sample_source_dirs(self, root: Path) -> tuple[Path, Path]:
        source_run_dir = root / "artifacts" / "pm_review_cards" / "source"
        output_run_dir = root / "artifacts" / "pm_review_cards" / "clarification"
        source_run_dir.mkdir(parents=True)
        (source_run_dir / "cards.json").write_text(
            json.dumps(
                {
                    "schema_version": "top10.pm_review_cards.v1",
                    "project_domain": "TOP10_STOCK",
                    "run_dir": "artifacts/pm_review_cards/source",
                    "cards": {
                        "RH1": {
                            "card_id": "RH1",
                            "project_domain": "TOP10_STOCK",
                            "title": "外部檢核分歧",
                            "owner": "disagreement_next_actions",
                            "next_harness": "disagreement_next_actions",
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (source_run_dir / "RH1.md").write_text(
            "\n".join(
                [
                    "RH1｜外部檢核分歧",
                    "",
                    "素材/證據：",
                    "- artifacts/external_review/a.json: 可追溯 artifact",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        external_path = root / "artifacts" / "external_review" / "a.json"
        external_path.parent.mkdir(parents=True)
        external_path.write_text(
            json.dumps(
                {
                    "schema_version": "external-review-summary.v1",
                    "today_misses": [
                        {
                            "symbol": "3163",
                            "name": "波若威",
                            "provider": "gemini",
                            "evidence": "系統列為 Rank 1，但 Gemini 指出開高走低與追高風險。",
                        }
                    ],
                    "tomorrow_watch": {"avoid_chasing": ["3163"]},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (source_run_dir / "clarification_queue.jsonl").write_text(
            json.dumps(
                {
                    "card_id": "RH1",
                    "project_domain": "TOP10_STOCK",
                    "decision": "needs_review",
                    "title": "外部檢核分歧",
                    "owner": "disagreement_next_actions",
                    "next_harness": "disagreement_next_actions",
                    "run_dir": "artifacts/pm_review_cards/source",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return source_run_dir, output_run_dir


if __name__ == "__main__":
    unittest.main()

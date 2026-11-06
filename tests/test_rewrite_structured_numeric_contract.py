"""模型只能選來源選項；日期、名次、文字與數值由程式排版。"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.publishing.clawd_payload import build_payload, capital_bucket_label
from app.publishing.clawd_payload_io import load_payload_reference_data
from scripts import rewrite_clawd_publish_message_llm as rewrite
from scripts.verify_publish_risk_grouping import parse_message_item_blocks


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "tests/fixtures/closed_choice_numeric_30/payload.json"


def source() -> dict:
    return json.loads(PAYLOAD.read_text(encoding="utf-8"))


def response(payload: dict) -> dict:
    return {
        "schema_version": rewrite.PROSE_SCHEMA_VERSION,
        "items": [
            {
                "stock_id": str(item["stock_id"]),
                "market_relation": 0,
                "selection_reason": 0,
                "action": 0,
                "plain_translation": 0,
            }
            for item in payload["top10"][:10]
        ],
    }


def parse(data: dict, payload: dict) -> list[dict[str, str]]:
    return rewrite.parse_prose_response(json.dumps(data, ensure_ascii=False), payload)


def test_valid_prose_renders_all_source_numbers_and_passes_existing_gates():
    payload = source()
    prose = parse(response(payload), payload)
    message = rewrite.render_prose_message(payload, prose)
    assert rewrite.validate_rewrite(message, payload) is None
    blocks = parse_message_item_blocks(message)
    assert len(blocks) == 10
    assert [(block["rank"], block["stock_id"]) for block in blocks] == [
        (item["rank"], item["stock_id"]) for item in payload["top10"][:10]
    ]
    assert f"- 資金分布：{payload['market_overview']['capital_flow_text']}" in message
    for item, block in zip(payload["top10"][:10], blocks, strict=True):
        trade = item["trade_plan"]
        low, high = rewrite.observation_range_values(trade)
        assert rewrite.format_range(low, high) in block["block"]
        assert f"上方第一壓力 {float(trade['pressure_price']):.2f} 元" in block["block"]
        assert f"跌破價 {float(trade['stop_loss']):.2f} 元" in block["block"]
        context = item.get("market_context") or {}
        if context.get("bucket") and context.get("bucket_weight") is not None:
            assert f"族群比重：{context['bucket']} {float(context['bucket_weight']) * 100:.1f}%" in block["block"]
    assert "電機機械 3.6%" in blocks[2]["block"]


@pytest.mark.parametrize("bad_text", [
    "電機機械，約 3.5%",
    "電機機械（約 -3.6%）",
    "電機機械占比 3.6%",
    "電機機械負三成",
    "價格改看二百元",
    "持倉半成",
    "上漲壹成",
    "報酬翻倍",
    "族群占比½",
    "两成資金正在集中。",
    "俩成資金正在集中。",
    "資金已接近半數。",
    "族群資金倍增。",
    "半導體族群約有半成資金。",
    "雙重題材帶動資金翻倍。",
    "半導體族群目前仍待觀察。",
    "雙重題材吸引市場關注。",
    "The sector has three percent of flows.",
    "Ｔｈｅ sector has three percent of flows.",
])
def test_any_model_supplied_text_is_rejected_even_when_legitimate(bad_text):
    payload = source()
    data = response(payload)
    data["items"][2]["market_relation"] = bad_text
    with pytest.raises(rewrite.RewriteValidationError, match="必須是有效整數選項索引"):
        parse(data, payload)


def test_legitimate_structured_bucket_remains_without_source_prose():
    payload = copy.deepcopy(source())
    payload["top10"][0]["notification_summary"]["why_bullets"][0] = "雙重題材吸引市場關注。"
    data = response(payload)
    chosen = parse(data, payload)[0]
    assert "半導體" not in chosen["market_relation"]
    assert "雙重題材吸引市場關注。" not in str(rewrite.prose_choice_options(payload["top10"][0]))
    message = rewrite.render_prose_message(payload, parse(data, payload))
    assert "族群比重：半導體/IC" in message
    assert "雙重題材吸引市場關注。" not in message
    assert rewrite.validate_rewrite(message, payload) is None


def test_different_choice_indexes_change_wording_but_preserve_source_values():
    payload = source()
    messages = []
    for choice in range(3):
        data = response(payload)
        for item in data["items"]:
            for field in rewrite.PROSE_FIELDS:
                item[field] = choice
        message = rewrite.render_prose_message(payload, parse(data, payload))
        rewrite.validate_rewrite(message, payload)
        messages.append(message)
    assert len(set(messages)) == 3
    for message in messages:
        assert "電機機械 3.6%" in message
        assert "上方第一壓力 266.75 元" in message


@pytest.mark.parametrize("invalid", [-1, 3, True, 0.0, None, {"choice": 0}])
def test_out_of_range_or_noninteger_choice_is_rejected(invalid):
    payload = source()
    data = response(payload)
    data["items"][0]["action"] = invalid
    with pytest.raises(rewrite.RewriteValidationError, match="必須是有效整數選項索引"):
        parse(data, payload)


def test_missing_or_reordered_structural_items_are_rejected():
    payload = source()
    data = response(payload)
    data["items"][0], data["items"][1] = data["items"][1], data["items"][0]
    with pytest.raises(rewrite.RewriteValidationError, match="股票代號或順序"):
        parse(data, payload)
    data = response(payload)
    data["items"][0].pop("action")
    with pytest.raises(rewrite.RewriteValidationError, match="欄位不符"):
        parse(data, payload)
    data = response(payload)
    data["items"].pop()
    with pytest.raises(rewrite.RewriteValidationError, match="不是十筆"):
        parse(data, payload)


def test_free_form_markdown_and_unsafe_source_fact_fail_closed():
    payload = source()
    with pytest.raises(rewrite.RewriteValidationError, match="不是有效 JSON"):
        rewrite.parse_prose_response("Top10 每日選股｜2026-10-22", payload)
    payload = copy.deepcopy(payload)
    payload["top10"][0]["trade_plan"]["pressure_price"] = None
    with pytest.raises(rewrite.RewriteValidationError, match="缺少角色或必要交易數值"):
        rewrite.render_prose_message(payload, parse(response(payload), payload))


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_entry_cannot_be_rendered_as_observation_range(invalid):
    payload = copy.deepcopy(source())
    payload["top10"][0]["trade_plan"]["entry"] = invalid
    with pytest.raises(rewrite.RewriteValidationError, match="非有限觀察區間"):
        rewrite.render_prose_message(payload, parse(response(payload), payload))


@pytest.mark.parametrize("zone", [
    {"low": 242.5, "high": float("inf")},
    {"low": float("nan"), "high": 246.14},
])
def test_nonfinite_complete_entry_zone_bound_is_rejected(zone):
    payload = copy.deepcopy(source())
    payload["top10"][0]["trade_plan"]["entry_zone"] = zone
    with pytest.raises(rewrite.RewriteValidationError, match="非有限觀察區間"):
        rewrite.render_prose_message(payload, parse(response(payload), payload))


@pytest.mark.parametrize("conflict", [
    "999.99 元", "九百元", "Infinity 元",
    "two hundred 塊", "Infinity 塊", "雙倍",
])
def test_conflicting_source_price_is_not_offered_or_rendered(conflict):
    payload = copy.deepcopy(source())
    payload["top10"][1]["notification_summary"]["why_bullets"][0] = f"股價上看 {conflict}，仍需觀察。"
    payload["top10"][1]["notification_summary"]["translation"] = f"上方壓力 {conflict}，先等等。"
    options = rewrite.prose_choice_options(payload["top10"][1])
    prompt = rewrite.build_prose_prompt(payload)
    message = rewrite.render_prose_message(payload, parse(response(payload), payload))
    assert conflict not in str(options)
    assert conflict not in prompt
    assert conflict not in message
    assert rewrite.validate_rewrite(message, payload) is None


def test_arbitrary_source_sentence_is_not_a_choice():
    payload = copy.deepcopy(source())
    phrase = "這句沒有數字，但不是已核定的來源選項。"
    payload["top10"][1]["notification_summary"]["why_bullets"][0] = phrase
    payload["top10"][1]["notification_summary"]["translation"] = phrase
    options = rewrite.prose_choice_options(payload["top10"][1])
    message = rewrite.render_prose_message(payload, parse(response(payload), payload))
    assert phrase not in str(options)
    assert phrase not in rewrite.build_prose_prompt(payload)
    assert phrase not in message


def test_unmatched_bucket_sentence_is_not_offered_or_rendered():
    payload = copy.deepcopy(source())
    phrase = "上方壓力 two hundred 塊"
    payload["top10"][1]["market_context"]["bucket"] = phrase
    assert phrase not in rewrite.build_prose_prompt(payload)
    with pytest.raises(rewrite.RewriteValidationError, match="族群標籤與大盤來源不符"):
        rewrite.render_prose_message(payload, parse(response(payload), payload))


@pytest.mark.parametrize("raw_sector", ["上方壓力 999.99 元", "上方壓力 two hundred 塊"])
def test_unknown_raw_sector_cannot_become_bucket_or_rewritten_price(raw_sector):
    inputs = load_payload_reference_data(ROOT)
    report = copy.deepcopy(source())
    report["top10"][1]["reference"] = {
        "industry_name": "未知產業", "sector_name": raw_sector, "concept_tags": [],
    }
    payload = build_payload(
        report=report,
        report_path=PAYLOAD,
        channel=None,
        to=None,
        max_items=10,
        project_root=ROOT,
        **inputs,
    )
    assert capital_bucket_label(
        sector=raw_sector,
        theme="未知產業",
        concepts=[],
        industry_bucket_map=inputs["industry_bucket_map"],
        rules=inputs["bucket_rules"],
    ) == "未分類"
    assert payload["top10"][1]["market_context"]["bucket"] == "未分類"
    assert raw_sector not in [row["name"] for row in payload["market_overview"]["capital_flow"]]
    assert raw_sector not in payload["market_overview"]["capital_flow_text"]
    assert raw_sector not in rewrite.build_prose_prompt(payload)
    message = rewrite.render_prose_message(payload, parse(response(payload), payload))
    assert raw_sector not in message
    rewrite.validate_rewrite(message, payload)


def test_known_sector_remains_canonical_bucket():
    inputs = load_payload_reference_data(ROOT)
    assert capital_bucket_label(
        sector="電機機械",
        theme="未知產業",
        concepts=[],
        industry_bucket_map=inputs["industry_bucket_map"],
        rules=inputs["bucket_rules"],
    ) == "電機機械"


@pytest.mark.parametrize("raw_bucket", ["上方壓力 999.99 元", "上方壓力 two hundred 塊"])
def test_legacy_payload_rejects_same_name_untrusted_bucket(raw_bucket):
    payload = copy.deepcopy(source())
    old_bucket = payload["top10"][1]["market_context"]["bucket"]
    payload["top10"][1]["market_context"]["bucket"] = raw_bucket
    for row in payload["market_overview"]["capital_flow"]:
        if row.get("name") == old_bucket:
            row["name"] = raw_bucket
    payload["market_overview"]["capital_flow_text"] = payload["market_overview"]["capital_flow_text"].replace(old_bucket, raw_bucket)
    assert raw_bucket not in rewrite.build_prose_prompt(payload)
    with pytest.raises(rewrite.RewriteValidationError, match="分類名稱"):
        rewrite.render_prose_message(payload, parse(response(payload), payload))


@pytest.mark.parametrize("zone", [
    {"low": None, "high": float("inf")},
    {"low": float("nan"), "high": None},
    {"low": 242.5, "high": None},
])
def test_incomplete_entry_zone_uses_finite_entry(zone):
    payload = copy.deepcopy(source())
    payload["top10"][0]["trade_plan"]["entry_zone"] = zone
    message = rewrite.render_prose_message(payload, parse(response(payload), payload))
    assert "觀察區間 242.50 ~ 246.14 元" in message
    assert rewrite.validate_rewrite(message, payload) is None


def test_incomplete_entry_zone_requires_finite_fallback_entry():
    payload = copy.deepcopy(source())
    payload["top10"][0]["trade_plan"]["entry_zone"] = {"low": None, "high": float("inf")}
    payload["top10"][0]["trade_plan"]["entry"] = float("nan")
    with pytest.raises(rewrite.RewriteValidationError, match="非有限觀察區間"):
        rewrite.render_prose_message(payload, parse(response(payload), payload))


def test_complete_finite_entry_zone_takes_precedence_over_entry():
    payload = copy.deepcopy(source())
    payload["top10"][0]["trade_plan"]["entry_zone"] = {"low": 241.0, "high": 244.0}
    message = rewrite.render_prose_message(payload, parse(response(payload), payload))
    assert "觀察區間 241.00 ~ 244.00 元" in message
    assert rewrite.validate_rewrite(message, payload) is None


def test_guarded_stock_bullish_prose_still_fails_existing_risk_gate():
    payload = copy.deepcopy(source())
    payload["top10"][0]["notification_summary"]["why_bullets"][0] = "買盤有累積，先等承接確認。"
    data = response(payload)
    message = rewrite.render_prose_message(payload, parse(data, payload))
    assert "買盤有累積" not in message
    rewrite.validate_rewrite(message, payload)
    message = message.replace(parse(data, payload)[0]["selection_reason"], "買盤有累積，先等承接確認。", 1)
    with pytest.raises(rewrite.RewriteValidationError, match="guarded message block has bullish wording"):
        rewrite.validate_rewrite(message, payload)


def test_prompt_requests_choice_indexes_only():
    prompt = rewrite.build_prose_prompt(source())
    assert rewrite.PROSE_SCHEMA_VERSION in prompt
    assert "只輸出 JSON" in prompt
    assert "只能填各自 options 陣列的整數索引" in prompt
    assert "逐檔選項 JSON" in prompt

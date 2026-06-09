#!/usr/bin/env python3
"""驗證 Top10 推播分級不把風險股包裝成主攻。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_SECTION_TITLES = ("主攻觀察", "等確認", "只等拉回", "候補觀察", "風險警示")
ROLE_LABEL_BY_PAYLOAD_ROLE = {
    "primary": "主攻觀察",
    "confirm": "等確認",
    "pullback": "只等拉回",
    "backup": "候補觀察",
    "risk": "風險警示",
}
FORBIDDEN_RISK_WORDS = ("買盤有累積", "可觀察進場")
CONTEXTUAL_BULLISH_WORDS = ("主攻", "追價", "轉強")
TAPE_GUARDED_ACTIONS = {"EXCLUDE", "DOWNGRADE", "COPY_GUARD"}
RR_GUARDED_ACTIONS = {"WAIT_PULLBACK", "WAIT_CONFIRM"}
NEGATION_MARKERS = ("不能", "不可", "不得", "不是", "不該", "不適合", "不列", "不要", "先不要", "否決")
CAUTION_MARKERS = ("保守", "謹慎", "小心", "別急", "不急")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify publish risk grouping payload/message")
    parser.add_argument("--date", default=None, help="指定日期 YYYY-MM-DD；未指定時找最新 payload")
    parser.add_argument("--payload", default=None, help="指定 clawd_publish_payload JSON")
    parser.add_argument("--message", default=None, help="指定 clawd_publish_message Markdown")
    parser.add_argument("--artifacts-dir", default="artifacts")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_dir = resolve_path(args.artifacts_dir)
    payload_path = resolve_payload_path(artifacts_dir, args.date, args.payload)
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    message_path = resolve_message_path(artifacts_dir, payload, args.message)
    message = message_path.read_text(encoding="utf-8")
    errors = verify(payload, message)
    status = "OK" if not errors else "FAILED"
    print(
        json.dumps(
            {
                "status": status,
                "payload": repo_path(payload_path),
                "message": repo_path(message_path),
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not errors else 1


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def resolve_payload_path(artifacts_dir: Path, date: str | None, payload: str | None) -> Path:
    if payload:
        path = resolve_path(payload)
        if path.exists():
            return path
        raise FileNotFoundError(f"payload 不存在：{path}")
    if date:
        path = artifacts_dir / f"clawd_publish_payload_{date}.json"
        if path.exists():
            return path
        raise FileNotFoundError(f"指定日期 payload 不存在：{path}")
    files = sorted(artifacts_dir.glob("clawd_publish_payload_????-??-??.json"))
    if not files:
        raise FileNotFoundError("找不到 clawd_publish_payload_*.json")
    return files[-1]


def resolve_message_path(artifacts_dir: Path, payload: dict[str, Any], message: str | None) -> Path:
    if message:
        path = resolve_path(message)
        if path.exists():
            return path
        raise FileNotFoundError(f"message 不存在：{path}")
    payload_message = (payload.get("artifacts") or {}).get("message")
    if payload_message:
        path = resolve_path(payload_message)
        if path.exists():
            return path
    ranking_date = payload.get("ranking_date")
    path = artifacts_dir / f"clawd_publish_message_{ranking_date}.md"
    if path.exists():
        return path
    raise FileNotFoundError(f"找不到對應 message：{path}")


def verify(payload: dict[str, Any], message: str) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != "clawd-publish-payload.v1":
        errors.append("schema_version must be clawd-publish-payload.v1")
    top10 = payload.get("top10") if isinstance(payload.get("top10"), list) else []
    if len(top10) != 10:
        errors.append(f"payload top10 must contain exactly 10 items, got {len(top10)}")
    message_items = parse_message_item_blocks(message)
    if len(message_items) != 10:
        errors.append(f"message must contain exactly 10 detailed stock blocks, got {len(message_items)}")
    message_by_key = {(item["rank"], item["stock_id"]): item for item in message_items}
    expected_keys = [(int(item.get("rank")), str(item.get("stock_id") or "").zfill(4)) for item in top10 if item.get("rank")]
    actual_keys = [(item["rank"], item["stock_id"]) for item in message_items]
    if actual_keys != expected_keys:
        errors.append(f"message detailed stock order must follow payload Top10 order: got {actual_keys}, expected {expected_keys}")
    roles = {str(item.get("list_role") or "") for item in top10}
    for role, section in ROLE_LABEL_BY_PAYLOAD_ROLE.items():
        if role in roles and section not in message:
            errors.append(f"message missing {section} section for role={role}")
    for item in top10:
        stock_id = str(item.get("stock_id") or "").zfill(4)
        rank = item.get("rank")
        role = str(item.get("list_role") or "")
        tape = item.get("tape") if isinstance(item.get("tape"), dict) else {}
        trade = item.get("trade_plan") if isinstance(item.get("trade_plan"), dict) else {}
        tape_action = str(tape.get("tape_guard_action") or "")
        rr_action = str(trade.get("rr_guard_action") or "")
        if tape_action == "EXCLUDE" and role != "risk":
            errors.append(f"{stock_id}: tape EXCLUDE must be role=risk, got {role}")
        if tape_action == "DOWNGRADE" and role != "pullback":
            errors.append(f"{stock_id}: tape DOWNGRADE must be role=pullback, got {role}")
        if tape_action == "COPY_GUARD" and role != "confirm":
            errors.append(f"{stock_id}: tape COPY_GUARD must be role=confirm, got {role}")
        if rr_action == "WAIT_PULLBACK" and role != "pullback":
            errors.append(f"{stock_id}: rr WAIT_PULLBACK must be role=pullback, got {role}")
        if rr_action == "WAIT_CONFIRM" and role != "confirm":
            errors.append(f"{stock_id}: rr WAIT_CONFIRM must be role=confirm, got {role}")
        item_key = (int(rank), stock_id) if rank else None
        message_item = message_by_key.get(item_key) if item_key else None
        if rank and not message_item:
            errors.append(f"{stock_id}: message missing exact rank line {rank}. {stock_id}")
        actual_label = str((message_item or {}).get("role_label") or "")
        expected_label = ROLE_LABEL_BY_PAYLOAD_ROLE.get(role)
        if expected_label and actual_label and actual_label != expected_label:
            errors.append(f"{stock_id}: message role label must be {expected_label}, got {actual_label}")
        if tape_action == "EXCLUDE" and actual_label and actual_label != "風險警示":
            errors.append(f"{stock_id}: tape EXCLUDE must only appear in 風險警示, got {actual_label}")
        if tape_action in {"DOWNGRADE", "COPY_GUARD"} and actual_label == "主攻觀察":
            errors.append(f"{stock_id}: tape {tape_action} must not appear in 主攻觀察")
        if rr_action in {"WAIT_PULLBACK", "WAIT_CONFIRM"} and actual_label == "主攻觀察":
            errors.append(f"{stock_id}: rr {rr_action} must not appear in 主攻觀察")
        if (tape_action in TAPE_GUARDED_ACTIONS) or (rr_action in RR_GUARDED_ACTIONS):
            block = str((message_item or {}).get("block") or message_block(message, stock_id))
            hits = bullish_wording_hits(block)
            if hits:
                errors.append(f"{stock_id}: guarded message block has bullish wording {hits}")
    return errors


def parse_message_item_blocks(message: str) -> list[dict[str, Any]]:
    labels = "|".join(map(re.escape, PUBLISH_SECTION_TITLES))
    label_pattern = re.compile(rf"(?m)^(?P<label>{labels})$")
    rank_pattern = re.compile(r"(?m)^(?P<rank>\d+)\.\s+(?P<stock_id>\d{4,6})(?:\D|$).*$")
    label_matches = list(label_pattern.finditer(message))
    rank_matches = list(rank_pattern.finditer(message))
    sections: list[dict[str, Any]] = []
    for index, match in enumerate(label_matches):
        end = label_matches[index + 1].start() if index + 1 < len(label_matches) else len(message)
        sections.append({"label": match.group("label"), "start": match.start(), "end": end})
    items: list[dict[str, Any]] = []
    for rank_index, match in enumerate(rank_matches):
        start = match.start()
        section = next((section for section in sections if section["start"] < start < section["end"]), None)
        if section is None:
            continue
        next_start = section["end"]
        for later in rank_matches[rank_index + 1 :]:
            if start < later.start() < section["end"]:
                next_start = later.start()
                break
        stock_id = str(match.group("stock_id")).zfill(4)
        items.append(
            {
                "rank": int(match.group("rank")),
                "stock_id": stock_id,
                "role_label": section["label"],
                "start": start,
                "end": next_start,
                "block": message[start:next_start],
            }
        )
    return items


def parse_message_sections(message: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    pattern = re.compile(rf"(?m)^({'|'.join(map(re.escape, PUBLISH_SECTION_TITLES))})$")
    matches = list(pattern.finditer(message))
    for index, match in enumerate(matches):
        title = match.group(1)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(message)
        sections[title] = message[match.start() : end]
    return sections


def stock_sections(sections: dict[str, str], stock_id: str) -> set[str]:
    pattern = re.compile(rf"(?m)^\d+\. {re.escape(stock_id)}(?:\D|$)")
    return {title for title, block in sections.items() if pattern.search(block)}


def exact_rank_line_positions(message: str, top10: list[dict[str, Any]]) -> list[tuple[int, int]]:
    positions: list[tuple[int, int]] = []
    for item in top10:
        rank = item.get("rank")
        stock_id = str(item.get("stock_id") or "").zfill(4)
        if not rank or not stock_id:
            continue
        pattern = re.compile(rf"(?m)^{int(rank)}\.\s+{re.escape(stock_id)}(?:\D|$)")
        match = pattern.search(message)
        if match:
            positions.append((int(rank), match.start()))
    return positions


def bullish_wording_hits(text: str) -> list[str]:
    hits = [word for word in FORBIDDEN_RISK_WORDS if word in text]
    for word in CONTEXTUAL_BULLISH_WORDS:
        for match in re.finditer(re.escape(word), text):
            prefix = text[max(0, match.start() - 12) : match.start()]
            context = text[max(0, match.start() - 12) : min(len(text), match.end() + 12)]
            if any(marker in prefix for marker in NEGATION_MARKERS) or any(marker in context for marker in CAUTION_MARKERS):
                continue
            hits.append(word)
    return hits


def message_block(message: str, stock_id: str) -> str:
    section_titles = "|".join(map(re.escape, PUBLISH_SECTION_TITLES))
    pattern = re.compile(rf"(?ms)^\d+\. {re.escape(stock_id)} .*?(?=^\d+\. \d{{4}} |^(?:{section_titles})$|\n風險提醒|\Z)")
    match = pattern.search(message)
    return match.group(0) if match else ""


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())

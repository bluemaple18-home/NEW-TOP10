#!/usr/bin/env python3
"""用外部免費 LLM 金鑰改寫每日推播訊息。

這支腳本只做最後一層「操盤手口吻」編輯：
- 輸入仍以 deterministic Clawd payload 為事實來源。
- 不改 ranking、模型分數、交易計畫。
- 不讀 New Clawd / Discord / gateway 設定。
- LLM 失敗只留下 status，daily 主流程可保留 deterministic message。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.verify_publish_risk_grouping import ROLE_LABEL_BY_PAYLOAD_ROLE, parse_message_item_blocks  # noqa: E402

STATUS_SCHEMA_VERSION = "clawd-llm-rewrite-status.v1"
DEFAULT_ENV_FILE = Path.home() / ".config" / "ai-core" / "legacy_review.env"
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_FALLBACK_MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite"]


def main() -> int:
    parser = argparse.ArgumentParser(description="rewrite Top10 Clawd message with Gemini LLM keys")
    parser.add_argument("--date", default=None, help="payload 日期，格式 YYYY-MM-DD；未指定時使用最新 payload")
    parser.add_argument("--payload", default=None, help="指定 clawd_publish_payload JSON")
    parser.add_argument("--message", default=None, help="指定要覆寫的 message Markdown")
    parser.add_argument("--output", default=None, help="指定 rewrite status JSON")
    parser.add_argument("--env-file", default=os.environ.get("TOP10_LLM_REWRITE_ENV_FILE") or str(DEFAULT_ENV_FILE))
    parser.add_argument("--models", default=None, help="逗號分隔 Gemini 模型清單；未指定時讀 LEGACY_REVIEW_MODEL")
    parser.add_argument("--timeout-seconds", type=int, default=int(os.environ.get("TOP10_LLM_REWRITE_TIMEOUT_SECONDS", "90")))
    parser.add_argument("--max-output-tokens", type=int, default=int(os.environ.get("TOP10_LLM_REWRITE_MAX_OUTPUT_TOKENS", "7200")))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("TOP10_LLM_REWRITE_TEMPERATURE", "0.55")))
    parser.add_argument("--no-in-place", action="store_true", help="只輸出 .llm.md，不覆寫 canonical message")
    args = parser.parse_args()

    artifacts_dir = PROJECT_ROOT / "artifacts"
    payload_path = resolve_payload_path(artifacts_dir, args.date, args.payload)
    payload = load_json(payload_path)
    ranking_date = str(payload.get("ranking_date") or date_from_payload_path(payload_path))
    message_path = resolve_message_path(artifacts_dir, ranking_date, args.message)
    output_path = resolve_output_path(artifacts_dir, ranking_date, args.output)
    llm_message_path = artifacts_dir / f"clawd_publish_message_llm_{ranking_date}.md"
    deterministic_path = artifacts_dir / f"clawd_publish_message_deterministic_{ranking_date}.md"

    file_env = load_env_file(Path(args.env_file).expanduser()) if args.env_file else {}
    merged_env = {**file_env, **os.environ}
    keys = rotate_values(split_values(str(merged_env.get("GEMINI_API_KEYS") or "")), ranking_date)
    models = rotate_values(resolve_models(args.models, merged_env), ranking_date)

    status: dict[str, Any] = {
        "schema_version": STATUS_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ranking_date": ranking_date,
        "payload_path": str(payload_path),
        "source_message_path": str(message_path),
        "llm_message_path": str(llm_message_path),
        "canonical_message_path": str(message_path),
        "env_file": compact_home(str(Path(args.env_file).expanduser())) if args.env_file else None,
        "models_attempted": [],
        "status": "RUNNING",
        "selected_model": None,
        "selected_key_index": None,
        "message_chars": None,
        "errors": [],
    }

    try:
        if not keys:
            raise RuntimeError("找不到 GEMINI_API_KEYS")
        source_message = message_path.read_text(encoding="utf-8") if message_path.exists() else str(payload.get("message_markdown") or "")
        prompt = build_prompt(payload, source_message)
        rewritten = None
        selected_model = None
        selected_key_index = None
        attempts = build_attempts(models, keys, ranking_date)

        for model, key_index, api_key in attempts:
            status["models_attempted"].append({"model": model, "key_index": key_index})
            try:
                rewritten = run_gemini(
                    model=model,
                    api_key=api_key,
                    prompt=prompt,
                    timeout_seconds=args.timeout_seconds,
                    max_output_tokens=args.max_output_tokens,
                    temperature=args.temperature,
                )
                rewritten = normalize_markdown(rewritten)
                validate_rewrite(rewritten, payload)
                selected_model = model
                selected_key_index = key_index
                break
            except Exception as exc:  # noqa: BLE001 - LLM 只是最後編輯層，失敗要可觀測但不阻斷。
                status["errors"].append(f"{model} key#{key_index}: {exc}")

        if not rewritten or not selected_model:
            raise RuntimeError("所有 Gemini 改寫嘗試都失敗，保留 deterministic message")

        llm_message_path.write_text(rewritten, encoding="utf-8")
        if not args.no_in_place:
            if message_path.exists() and not deterministic_path.exists():
                deterministic_path.write_text(message_path.read_text(encoding="utf-8"), encoding="utf-8")
            message_path.write_text(rewritten, encoding="utf-8")
            payload["message_markdown"] = rewritten
            payload["message_stats"] = {
                **dict(payload.get("message_stats") or {}),
                "characters": len(rewritten),
                "llm_rewritten": True,
                "llm_provider": "gemini",
                "llm_model": selected_model,
                "llm_key_index": selected_key_index,
            }
            payload.setdefault("artifacts", {})["message_llm"] = str(llm_message_path)
            payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        status["status"] = "OK"
        status["selected_model"] = selected_model
        status["selected_key_index"] = selected_key_index
        status["message_chars"] = len(rewritten)
    except Exception as exc:  # noqa: BLE001 - fallback 是設計的一部分。
        status["status"] = "FALLBACK"
        status["errors"].append(str(exc))
        if not args.no_in_place and deterministic_path.exists():
            deterministic_message = deterministic_path.read_text(encoding="utf-8")
            message_path.write_text(deterministic_message, encoding="utf-8")
            payload["message_markdown"] = deterministic_message
            payload["message_stats"] = {
                **dict(payload.get("message_stats") or {}),
                "characters": len(deterministic_message),
                "llm_rewritten": False,
                "llm_fallback": True,
            }
            payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    output_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "CLAWD_LLM_REWRITE "
        f"status={status['status']} model={status.get('selected_model')} output={output_path}"
    )
    return 0


def resolve_payload_path(artifacts_dir: Path, date: str | None, payload: str | None) -> Path:
    if payload:
        path = Path(payload)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if path.exists():
            return path
        raise FileNotFoundError(f"指定 payload 不存在：{path}")
    if date:
        path = artifacts_dir / f"clawd_publish_payload_{date}.json"
        if path.exists():
            return path
        raise FileNotFoundError(f"指定日期 payload 不存在：{path}")
    files = sorted(artifacts_dir.glob("clawd_publish_payload_*.json"))
    if not files:
        raise FileNotFoundError("找不到 clawd_publish_payload_*.json")
    return files[-1]


def resolve_message_path(artifacts_dir: Path, ranking_date: str, message: str | None) -> Path:
    if message:
        path = Path(message)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path
    return artifacts_dir / f"clawd_publish_message_{ranking_date}.md"


def resolve_output_path(artifacts_dir: Path, ranking_date: str, output: str | None) -> Path:
    if output:
        path = Path(output)
        return path if path.is_absolute() else PROJECT_ROOT / path
    return artifacts_dir / f"clawd_publish_llm_rewrite_{ranking_date}.json"


def date_from_payload_path(path: Path) -> str:
    match = re.search(r"clawd_publish_payload_(\d{4}-\d{2}-\d{2})\.json$", path.name)
    if not match:
        raise ValueError(f"payload 檔名無法解析日期：{path}")
    return match.group(1)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        values[key] = unquote_env_value(value.strip())
    return values


def unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def split_values(raw: str) -> list[str]:
    return [part.strip() for part in re.split(r"[\s,;]+", raw) if part.strip()]


def resolve_models(cli_models: str | None, env: dict[str, str]) -> list[str]:
    raw = cli_models or env.get("TOP10_LLM_REWRITE_MODELS") or env.get("LEGACY_REVIEW_MODEL") or DEFAULT_MODEL
    candidates = split_values(str(raw))
    if not cli_models and not env.get("TOP10_LLM_REWRITE_MODELS"):
        classify_provider = str(env.get("LEGACY_CLASSIFY_PROVIDER") or "").strip()
        classify_model = str(env.get("LEGACY_CLASSIFY_MODEL") or "").strip()
        if classify_model and (classify_provider in {"gemini", "google"} or classify_model.startswith("gemini-")):
            candidates.append(classify_model)
        fallback_raw = env.get("TOP10_LLM_REWRITE_FALLBACK_MODELS") or ",".join(DEFAULT_FALLBACK_MODELS)
        candidates.extend(split_values(str(fallback_raw)))

    models = []
    for candidate in candidates:
        model = normalize_gemini_model(candidate)
        if model and model not in models:
            models.append(model)
    return models


def normalize_gemini_model(model: str) -> str:
    model = model.strip()
    if "/" in model:
        provider, name = model.split("/", 1)
        if provider not in {"google", "gemini"}:
            raise ValueError(f"只支援 Gemini provider，不支援：{provider}")
        model = name
    if model.startswith("models/"):
        model = model[len("models/") :]
    return model


def rotate_values(values: list[str], ranking_date: str) -> list[str]:
    if not values:
        return []
    offset = sum(ord(char) for char in ranking_date) % len(values)
    return values[offset:] + values[:offset]


def build_attempts(models: list[str], keys: list[str], ranking_date: str) -> list[tuple[str, int, str]]:
    attempts = []
    for model in models:
        for key_offset, api_key in enumerate(keys):
            attempts.append((model, key_offset + 1, api_key))
    if not attempts:
        return []
    offset = sum(ord(char) for char in f"{ranking_date}|attempts") % len(attempts)
    return attempts[offset:] + attempts[:offset]


def run_gemini(
    model: str,
    api_key: str,
    prompt: str,
    timeout_seconds: int,
    max_output_tokens: int,
    temperature: float,
) -> str:
    query = parse.urlencode({"key": api_key})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{parse.quote(model)}:generateContent?{query}"
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
        "systemInstruction": {
            "parts": [
                {
                    "text": "你是專業但講人話的台股操盤手助理。只根據使用者提供的資料改寫，不新增未提供的事實。"
                }
            ]
        },
    }
    req = request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {redact_key_text(body_text)}") from exc
    parts = (
        (data.get("candidates") or [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    text = "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict)).strip()
    if not text:
        raise RuntimeError("Gemini 回傳空內容")
    return text


def build_prompt(payload: dict[str, Any], source_message: str) -> str:
    facts = compact_payload_facts(payload)
    source_hint = source_message[:1200].strip()
    return "\n".join(
        [
            "請把以下台股 Top10 推播改寫成「專業操盤手帶盤，但股市小白聽得懂」的版本。",
            "",
            "硬性規則：",
            "- 必須使用繁體中文。",
            "- 必須保留日期、10 檔順序、股票代號、股票名稱。",
            "- 必須保留每檔原始排名格式，例如 facts 裡 rank=3、stock_id=2302，就必須寫成「3. 2302 麗正」。",
            "- 逐檔內容必須照 1 到 10 的排名順序輸出，不可因主攻觀察、等確認、只等拉回而重新排序。",
            "- 必須保留大盤情況、資金分布百分比、資金重心、熱門概念。",
            "- 每檔都要有：跟今天盤勢的關係、為什麼入選、怎麼看、白話翻譯。",
            "- 每檔第一句先給結論，讓小白三秒內知道強不強。",
            "- 每檔都要串回今日大盤與族群脈絡，不要各寫各的。",
            "- 觀察區間必須照 facts 的 observation_range 寫，不可把 target_price 當成區間上緣。",
            "- 跌破價與上方壓力要保留；上方壓力只放在「上方第一壓力」，不要混進觀察區間。",
            "- 可以把技術術語翻成白話，但不要新增沒有提供的資料。",
            "- 不要出現建議資金百分比、建議部位百分比、勝率、模型把握度。",
            "- 不要承諾一定上漲，不要叫使用者重壓，不要寫成研究報告。",
            "- 不要每檔使用同一句風險提醒或同一句白話翻譯。",
            "- 輸出只要推播訊息正文，不要包 code block。",
            "- 不要使用 Markdown 標題語法，不要出現 #、##、###、####。",
            "- 段落標籤請用純文字，例如：今日大盤與資金、為什麼入選：、怎麼看：、白話翻譯：。",
            "- 分組只當每檔標籤使用，不可把股票分組重排。",
            "",
            "語氣方向：",
            "- 像真人操盤手盤後快速講重點。",
            "- 一段一句重點，短、清楚、有市場感。",
            "- 強勢股講資金追價；支線股講為什麼能擠進名單；候補股講為什麼先觀察。",
            "",
            "請使用這個固定骨架：",
            "Top10 每日選股｜YYYY-MM-DD",
            "今日大盤與資金",
            "今日 10 檔總覽（照 1 到 10 列出）",
            "逐檔重點（照 1 到 10 寫，每檔可標主攻觀察/等確認/只等拉回/候補觀察/風險警示）",
            "每檔使用：分組標籤 / 跟今天盤勢的關係： / 為什麼入選： / 怎麼看： / 白話翻譯：",
            "",
            "事實資料 JSON：",
            json.dumps(facts, ensure_ascii=False, separators=(",", ":")),
            "",
            "原始訊息開頭只供格式參考，請不要照抄罐頭句：",
            source_hint,
        ]
    )


def compact_payload_facts(payload: dict[str, Any]) -> dict[str, Any]:
    items = []
    for item in payload.get("top10", [])[:10]:
        group = item.get("audience_group") if isinstance(item.get("audience_group"), dict) else {}
        summary = item.get("notification_summary") if isinstance(item.get("notification_summary"), dict) else {}
        trade = item.get("trade_plan") if isinstance(item.get("trade_plan"), dict) else {}
        context = item.get("market_context") if isinstance(item.get("market_context"), dict) else {}
        entry_low, entry_high = observation_range_values(trade)
        items.append(
            {
                "rank": item.get("rank"),
                "stock_id": item.get("stock_id"),
                "stock_name": item.get("stock_name"),
                "theme": group.get("theme") or group.get("sector"),
                "sector": group.get("sector"),
                "concepts": list(group.get("concepts") or [])[:5],
                "list_role": item.get("list_role"),
                "market_context": {
                    "bucket": context.get("bucket"),
                    "bucket_weight": context.get("bucket_weight"),
                    "is_lead_bucket": context.get("is_lead_bucket"),
                    "lead_bucket": context.get("lead_bucket"),
                    "market": context.get("market"),
                    "matched_hot_concepts": context.get("matched_hot_concepts"),
                },
                "conclusion": summary.get("conclusion"),
                "why_bullets": list(summary.get("why_bullets") or [])[:4],
                "translation": summary.get("translation"),
                "risk": summary.get("risk"),
                "trade_plan": {
                    "observation_range": format_range(entry_low, entry_high),
                    "stop_loss": trade.get("stop_loss"),
                    "target_price": trade.get("target_price"),
                },
                "signals": list(item.get("raw_signals") or [])[:8],
            }
        )
    return {
        "ranking_date": payload.get("ranking_date"),
        "summary": payload.get("summary"),
        "market_overview": payload.get("market_overview"),
        "risk_notes": (payload.get("risk") or {}).get("notes"),
        "top10": items,
    }


def observation_range_values(trade: dict[str, Any]) -> tuple[float | None, float | None]:
    zone = trade.get("entry_zone")
    if isinstance(zone, dict):
        low = number_value(zone.get("low"))
        high = number_value(zone.get("high"))
        if low is not None and high is not None:
            return min(low, high), max(low, high)
    entry = number_value(trade.get("entry"))
    if entry is None:
        return None, None
    return entry, round(entry * 1.015, 2)


def format_range(low: float | None, high: float | None) -> str | None:
    if low is None or high is None:
        return None
    return f"{low:.2f} ~ {high:.2f} 元"


def number_value(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:markdown)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip() + "\n"


def validate_rewrite(message: str, payload: dict[str, Any]) -> None:
    if len(message) < 1200:
        raise ValueError("LLM 訊息過短，疑似沒有完整改寫")
    if len(message) > 12000:
        raise ValueError("LLM 訊息過長，可能不適合推播")
    ranking_date = str(payload.get("ranking_date") or "")
    if ranking_date and ranking_date not in message:
        raise ValueError("LLM 訊息缺少排名日期")
    rank_positions: list[tuple[int, int]] = []
    for item in payload.get("top10", [])[:10]:
        rank = item.get("rank")
        stock_id = str(item.get("stock_id") or "").strip()
        stock_name = str(item.get("stock_name") or "").strip()
        if stock_id and stock_id not in message:
            raise ValueError(f"LLM 訊息缺少股票代號 {stock_id}")
        if stock_name and stock_name not in message:
            raise ValueError(f"LLM 訊息缺少股票名稱 {stock_name}")
        if rank and stock_id:
            match = re.search(rf"(?m)^{int(rank)}\.\s+{re.escape(stock_id)}(?:\D|$)", message)
            if not match:
                raise ValueError(f"LLM 訊息未保留正確排名格式：{rank}. {stock_id}")
            rank_positions.append((int(rank), match.start()))
        trade = item.get("trade_plan") if isinstance(item.get("trade_plan"), dict) else {}
        entry_low, entry_high = observation_range_values(trade)
        expected_range = format_range(entry_low, entry_high)
        if expected_range and expected_range not in message:
            raise ValueError(f"LLM 訊息未保留 {stock_id} 正確觀察區間：{expected_range}")
        target = number_value(trade.get("target_price"))
        if entry_low is not None and target is not None:
            wrong_range = f"{entry_low:.2f} ~ {target:.2f} 元"
            if wrong_range in message:
                raise ValueError(f"LLM 訊息把 {stock_id} 目標價誤寫成觀察區間")
    expected_ranks = [int(item.get("rank")) for item in payload.get("top10", [])[:10] if item.get("rank")]
    ordered_ranks = [rank for rank, _ in sorted(rank_positions, key=lambda item: item[1])]
    if ordered_ranks != expected_ranks:
        raise ValueError(f"LLM 訊息排名順序錯誤：got={ordered_ranks}, expected={expected_ranks}")
    required_sections = ["大盤", "資金", "為什麼入選", "怎麼看", "白話翻譯"]
    missing = [section for section in required_sections if section not in message]
    if missing:
        raise ValueError(f"LLM 訊息缺少必要段落：{', '.join(missing)}")
    section_by_role = {
        "primary": "主攻觀察",
        "confirm": "等確認",
        "pullback": "只等拉回",
        "backup": "候補觀察",
        "risk": "風險警示",
    }
    roles = {str(item.get("list_role") or "") for item in payload.get("top10", [])[:10]}
    missing_role_sections = [section for role, section in section_by_role.items() if role in roles and section not in message]
    if missing_role_sections:
        raise ValueError(f"LLM 訊息缺少分組標題：{', '.join(missing_role_sections)}")
    message_items = parse_message_item_blocks(message)
    if len(message_items) != 10:
        raise ValueError(f"LLM 訊息逐檔區塊數量錯誤：got={len(message_items)}, expected=10")
    expected_keys = [(int(item.get("rank")), str(item.get("stock_id") or "").zfill(4)) for item in payload.get("top10", [])[:10] if item.get("rank")]
    actual_keys = [(item["rank"], item["stock_id"]) for item in message_items]
    if actual_keys != expected_keys:
        raise ValueError(f"LLM 訊息逐檔順序錯誤：got={actual_keys}, expected={expected_keys}")
    message_by_key = {(item["rank"], item["stock_id"]): item for item in message_items}
    for item in payload.get("top10", [])[:10]:
        if not item.get("rank"):
            continue
        stock_id = str(item.get("stock_id") or "").zfill(4)
        role = str(item.get("list_role") or "")
        expected_label = ROLE_LABEL_BY_PAYLOAD_ROLE.get(role)
        message_item = message_by_key.get((int(item.get("rank")), stock_id))
        actual_label = str((message_item or {}).get("role_label") or "")
        if expected_label and actual_label != expected_label:
            raise ValueError(f"LLM 訊息 {stock_id} 分組錯誤：got={actual_label}, expected={expected_label}")
    if message.count("為什麼入選") < 8 or message.count("白話翻譯") < 8:
        raise ValueError("LLM 訊息沒有完整覆蓋足夠多檔股票")
    if re.search(r"(?m)^#{1,6}\s+", message):
        raise ValueError("LLM 訊息不可使用 Markdown # 標題，請改用純文字段落標籤")
    banned_patterns = [
        r"建議(?:資金|部位)\s*\d",
        r"(?:勝率|模型把握度)\s*\d",
        r"\d+(?:\.\d+)?%\s*(?:資金|部位|勝率|模型把握度)",
    ]
    for pattern in banned_patterns:
        if re.search(pattern, message):
            raise ValueError(f"LLM 訊息包含禁止格式：{pattern}")


def compact_home(path_text: str) -> str:
    home = str(Path.home())
    if path_text.startswith(home):
        return "~" + path_text[len(home) :]
    return path_text


def redact_key_text(text: str) -> str:
    return re.sub(r"AIza[0-9A-Za-z_-]+", "<redacted>", text)


if __name__ == "__main__":
    raise SystemExit(main())

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
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.verify_publish_risk_grouping import ROLE_LABEL_BY_PAYLOAD_ROLE, parse_message_item_blocks, verify as verify_risk_grouping  # noqa: E402
from app.publishing.clawd_payload import canonical_capital_bucket_names  # noqa: E402
from app.publishing.clawd_payload_io import load_notification_industry_buckets, load_notification_theme_buckets  # noqa: E402

STATUS_SCHEMA_VERSION = "clawd-llm-rewrite-status.v1"
DEFAULT_ENV_FILE = Path.home() / ".config" / "ai-core" / "legacy_review.env"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
PROSE_SCHEMA_VERSION = "clawd-prose-choice.v1"
PROSE_FIELDS = ("market_relation", "selection_reason", "action", "plain_translation")
FULL_TEXT_CONTRACT = "clawd-full-text-candidate.v1"


class RewriteValidationError(ValueError):
    """保留單次改寫的全部契約違規，供狀態收據追溯。"""

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("；".join(violations))


def aliases_source_file(target: Path, sources: tuple[Path, ...]) -> bool:
    """以實際檔案身分辨識別名；無法判定時保守拒絕。"""
    for source in sources:
        try:
            if target.samefile(source):
                return True
        except FileNotFoundError:
            continue
        except OSError:
            return True
    return False


def isolated_candidate_request(args: argparse.Namespace) -> bool:
    """只允許同一個 repo 外隔離目錄中的明確日期與輸入輸出。"""
    if (not args.no_in_place or not args.date or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date)
            or not all((args.payload, args.message, args.output))):
        return False
    try:
        paths = [Path(value).expanduser().resolve() for value in (args.payload, args.message, args.output)]
        candidate_path = paths[1].parent / f"clawd_publish_message_llm_{args.date}.md"
        if Path(args.output).expanduser().is_symlink() or candidate_path.is_symlink():
            return False
        candidate = candidate_path.resolve()
    except (OSError, RuntimeError):
        return False
    if len(set(paths)) != 3 or len({path.parent for path in paths}) != 1:
        return False
    if candidate in paths or candidate.is_relative_to(PROJECT_ROOT.resolve()):
        return False
    if aliases_source_file(candidate_path, (paths[0], paths[1])) or aliases_source_file(
        paths[2], (paths[0], paths[1])
    ) or aliases_source_file(candidate_path, (paths[2],)):
        return False
    return all(not path.is_relative_to(PROJECT_ROOT.resolve()) for path in paths)


def write_isolation_fallback(args: argparse.Namespace) -> None:
    """拒絕非隔離請求時，只寫既有狀態收據，不碰訊息或 payload。"""
    if not all((args.output, args.payload, args.message)):
        return
    try:
        ranking_date = args.date or date_from_payload_path(Path(args.payload or ""))
        artifacts_dir = PROJECT_ROOT / "artifacts"
        payload_path = resolve_payload_path(artifacts_dir, ranking_date, args.payload)
        message_path = resolve_message_path(artifacts_dir, ranking_date, args.message)
        requested_output = resolve_output_path(artifacts_dir, ranking_date, args.output)
        if requested_output.is_symlink():
            return
        output_path = requested_output.resolve()
        inputs = {Path(value).expanduser().resolve() for value in (args.payload, args.message) if value}
        if output_path in inputs or output_path.suffix != ".json":
            return
        if output_path.is_relative_to(PROJECT_ROOT.resolve()) and (
            output_path.parent != PROJECT_ROOT / "artifacts"
            or output_path.name != f"clawd_publish_llm_rewrite_{ranking_date}.json"
        ):
            return
        streak = fallback_streak(output_path.parent, ranking_date, "FALLBACK")
        status = {
            "schema_version": STATUS_SCHEMA_VERSION,
            "rewrite_contract": FULL_TEXT_CONTRACT,
            "ranking_date": ranking_date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "FALLBACK",
            "reason_code": "ISOLATION_REQUIRED",
            "candidate_only": True,
            "models_attempted": [],
            "validation_failures": [],
            "errors": ["缺少隔離候選條件"],
            "consecutive_fallback_days": streak,
            "degraded": streak >= 2,
        }
        if aliases_source_file(output_path, (payload_path, message_path)):
            return
        candidate_path = message_path.parent / f"clawd_publish_message_llm_{ranking_date}.md"
        if aliases_source_file(output_path, (candidate_path,)):
            return
        output_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError, RuntimeError):
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="rewrite Top10 Clawd message with Gemini LLM keys")
    parser.add_argument("--date", default=None, help="隔離候選的指定日期，格式 YYYY-MM-DD")
    parser.add_argument("--payload", default=None, help="指定 clawd_publish_payload JSON")
    parser.add_argument("--message", default=None, help="指定只讀來源 message Markdown")
    parser.add_argument("--output", default=None, help="指定 rewrite status JSON")
    parser.add_argument("--env-file", default=os.environ.get("TOP10_LLM_REWRITE_ENV_FILE") or str(DEFAULT_ENV_FILE))
    parser.add_argument("--models", default=None, help="Gemini 文案模型；目前只接受 gemini-3.5-flash-lite")
    parser.add_argument("--timeout-seconds", type=int, default=int(os.environ.get("TOP10_LLM_REWRITE_TIMEOUT_SECONDS", "90")))
    parser.add_argument("--max-output-tokens", type=int, default=int(os.environ.get("TOP10_LLM_REWRITE_MAX_OUTPUT_TOKENS", "7200")))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("TOP10_LLM_REWRITE_TEMPERATURE", "0.55")))
    parser.add_argument("--no-in-place", action="store_true", help="隔離候選必填；只輸出 .llm.md")
    args = parser.parse_args()

    if not isolated_candidate_request(args):
        write_isolation_fallback(args)
        print("CLAWD_LLM_REWRITE status=FALLBACK reason=ISOLATION_REQUIRED")
        return 0

    artifacts_dir = PROJECT_ROOT / "artifacts"
    payload_path = resolve_payload_path(artifacts_dir, args.date, args.payload)
    ranking_date = args.date
    message_path = resolve_message_path(artifacts_dir, ranking_date, args.message)
    output_path = resolve_output_path(artifacts_dir, ranking_date, args.output)
    # 指定隔離訊息路徑時，衍生檔必須留在同一目錄，避免驗收寫入正式 artifacts。
    message_dir = message_path.parent
    llm_message_path = message_dir / f"clawd_publish_message_llm_{ranking_date}.md"

    status: dict[str, Any] = {
        "schema_version": STATUS_SCHEMA_VERSION,
        "rewrite_contract": FULL_TEXT_CONTRACT,
        "candidate_only": True,
        "content_review_required": True,
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
        "validation_failures": [],
    }

    try:
        payload = load_json(payload_path)
        if str(payload.get("ranking_date") or "") != ranking_date:
            raise RewriteValidationError(["指定日期與 payload ranking_date 不符"])
        source_message = message_path.read_text(encoding="utf-8")
        # 選句 renderer 已驗過來源的有限數值與分類；送前沿用同一條契約。
        source_prose = []
        for source in payload.get("top10", [])[:10]:
            choices = prose_choice_options(source)
            source_prose.append({field: choices[field][0] for field in PROSE_FIELDS})
        render_prose_message(payload, source_prose)
        prompt = build_prompt(payload, source_message)
        file_env = load_env_file(Path(args.env_file).expanduser()) if args.env_file else {}
        merged_env = {**file_env, **os.environ}
        keys = rotate_values(split_values(str(merged_env.get("GEMINI_API_KEYS") or "")), ranking_date)
        models = rotate_values(resolve_models(args.models, merged_env), ranking_date)
        if not keys:
            raise RuntimeError("找不到 GEMINI_API_KEYS")
        rewritten = None
        selected_model = None
        selected_key_index = None
        attempts = build_attempts(models, keys, ranking_date)

        for model, key_index, api_key in attempts:
            status["models_attempted"].append({"model": model, "key_index": key_index})
            try:
                response = run_gemini(
                    model=model,
                    api_key=api_key,
                    prompt=prompt,
                    timeout_seconds=args.timeout_seconds,
                    max_output_tokens=args.max_output_tokens,
                    temperature=args.temperature,
                )
                rewritten = response
                validate_rewrite(rewritten, payload)
                selected_model = model
                selected_key_index = key_index
                break
            except RewriteValidationError as exc:
                violations = [redact_key_text(item).replace(api_key, "<redacted>") for item in exc.violations]
                status["validation_failures"].append(
                    {"model": model, "key_index": key_index, "violations": violations}
                )
                status["errors"].append(f"{model} key#{key_index}: {'；'.join(violations)}")
                break
            except Exception as exc:  # noqa: BLE001 - LLM 只是最後編輯層，失敗要可觀測但不阻斷。
                # 第三方或網路例外可能附帶含金鑰的請求網址，收據不得記錄原文。
                error_text = redact_key_text(str(exc)).replace(api_key, "<redacted>")
                status["errors"].append(f"{model} key#{key_index}: {error_text}")

        if not rewritten or not selected_model:
            raise RuntimeError("所有 Gemini 改寫嘗試都失敗，保留 deterministic message")

        if aliases_source_file(llm_message_path, (payload_path, message_path)) or aliases_source_file(
            output_path, (payload_path, message_path)
        ) or aliases_source_file(llm_message_path, (output_path,)):
            raise RewriteValidationError(["候選或收據路徑與來源為同一檔案"])
        llm_message_path.write_text(rewritten, encoding="utf-8")

        status["status"] = "REVIEW_REQUIRED"
        status["selected_model"] = selected_model
        status["selected_key_index"] = selected_key_index
        status["message_chars"] = len(rewritten)
    except Exception as exc:  # noqa: BLE001 - fallback 是設計的一部分。
        status["status"] = "FALLBACK"
        status["errors"].append(redact_key_text(str(exc)))

    streak = fallback_streak(output_path.parent, ranking_date, status["status"])
    status["consecutive_fallback_days"] = streak
    status["degraded"] = streak >= 2
    if aliases_source_file(output_path, (payload_path, message_path, llm_message_path)):
        print("CLAWD_LLM_REWRITE status=FALLBACK reason=OUTPUT_ALIAS")
        return 0
    output_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "CLAWD_LLM_REWRITE "
        f"status={status['status']} model={status.get('selected_model')} output={output_path}"
    )
    return 0


def fallback_streak(status_dir: Path, ranking_date: str, current_status: str) -> int:
    if current_status != "FALLBACK":
        return 0
    # 以最近一次較早的 Daily 收據判斷連續執行日；缺檔或日期不符不計入。
    previous = sorted(status_dir.glob("clawd_publish_llm_rewrite_????-??-??.json"), reverse=True)
    for path in previous:
        prior_date = path.stem.removeprefix("clawd_publish_llm_rewrite_")
        if prior_date >= ranking_date:
            continue
        try:
            prior = load_json(path)
        except (OSError, ValueError, TypeError):
            return 1
        if prior.get("ranking_date") != prior_date or prior.get("status") != "FALLBACK":
            return 1
        try:
            prior_streak = max(1, int(prior.get("consecutive_fallback_days") or 1))
        except (TypeError, ValueError):
            prior_streak = 1
        return 1 + prior_streak
    return 1


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
    raw = cli_models or env.get("TOP10_LLM_REWRITE_MODELS") or DEFAULT_MODEL
    candidates = split_values(str(raw))
    models = []
    for candidate in candidates:
        model = normalize_gemini_model(candidate)
        if model != DEFAULT_MODEL:
            raise ValueError(f"TOP10 文案模型只接受 {DEFAULT_MODEL}，收到 {model}")
        if model and model not in models:
            models.append(model)
    if not models:
        raise ValueError("TOP10 文案模型不可為空")
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
    if model != DEFAULT_MODEL:
        raise ValueError(f"TOP10 文案模型只接受 {DEFAULT_MODEL}，收到 {model}")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
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
            "thinkingConfig": {"thinkingLevel": "LOW"},
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
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {redact_key_text(body_text)}") from exc
    candidate = (data.get("candidates") or [{}])[0]
    if candidate.get("finishReason") == "MAX_TOKENS":
        raise RuntimeError("Gemini 輸出額度不足，回應遭截斷")
    parts = candidate.get("content", {}).get("parts", [])
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
            "- 每檔 trade_plan.observation_range 已是算好的完整成品字串；觀察區間請逐字照抄，不要自行計算或拼接。",
            "- 跌破價要保留；「上方第一壓力」只准逐字照抄每檔 trade_plan.pressure_price 成品字串。signals 裡的「壓力」是歷史突破參考位，不是上方第一壓力；不可把 target_price 當成觀察區間上緣。",
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


def build_prose_prompt(payload: dict[str, Any]) -> str:
    """只請模型選來源文字選項；不接受模型自行撰寫文案。"""
    items = []
    for source in payload.get("top10", [])[:10]:
        items.append({
            "stock_id": str(source.get("stock_id") or ""),
            "options": prose_choice_options(source),
        })
    return "\n".join(
        [
            "請為台股 Top10 的每檔股票，從提供的文案選項中選擇適合的說法。",
            "只輸出 JSON 物件，不要 Markdown、code block 或額外欄位。",
            f'頂層格式：{{"schema_version":"{PROSE_SCHEMA_VERSION}","items":[...]}}',
            'items 須按來源順序有十筆；每筆格式：{"stock_id":"來源代號","market_relation":0,"selection_reason":1,"action":2,"plain_translation":0}。',
            "四個欄位只能填各自 options 陣列的整數索引，不可填文字、價格、百分比或其他資料。",
            "日期、排名、股票名稱、角色與所有數值由程式從 payload 排版。",
            "逐檔選項 JSON：",
            json.dumps(items, ensure_ascii=False, separators=(",", ":")),
        ]
    )


def prose_choice_options(source: dict[str, Any]) -> dict[str, tuple[str, str, str]]:
    """只用固定保守句組成選項；模型與來源自由敘述都不能注入文案。"""
    role = str(source.get("list_role") or "")
    actions = {
        "primary": (
            "先看觀察區間附近能否有承接，再決定是否行動。",
            "入選仍須等價格條件確認，不急著採取動作。",
            "按照交易計畫追蹤，條件未到先保持觀察。",
        ),
        "confirm": (
            "先等盤面確認，再看交易計畫是否能執行。",
            "條件還要確認，現在先保持觀察。",
            "把價格與承接狀況一起核對，未確認前不急著動作。",
        ),
        "pullback": (
            "先等拉回與承接確認，再看是否符合交易計畫。",
            "目前以等待為主，價格條件未到就先觀察。",
            "不要急著行動，先確認拉回後能否守住區間。",
        ),
        "backup": (
            "先放觀察名單，等條件更清楚再評估。",
            "候補先追蹤，價格與承接確認前不急著動作。",
            "保持耐心，等盤面提供更明確的訊號。",
        ),
        "risk": (
            "風險先行，等不利條件解除再觀察。",
            "目前先控風險，交易條件未確認前不動作。",
            "優先核對風險與跌破價，不急著進場。",
        ),
    }
    return {
        "market_relation": (
            "先看盤勢與個股走勢能否同步。",
            "今天先回到盤面脈絡觀察這檔。",
            "盤面仍有變化，留意個股的相對表現。",
        ),
        "selection_reason": (
            "入選名單仍值得追蹤，後續要核對交易條件。",
            "入選只是觀察起點，仍須看盤面後續反應。",
            "進入名單代表值得觀察，仍要依交易計畫決定動作。",
        ),
        "action": actions.get(role, actions["risk"]),
        "plain_translation": (
            "先觀察後續表現，條件未明時別急著行動。",
            "先看接下來的表現，條件未明時別急著行動。",
            "這檔可以追蹤，但是否行動仍要看價格條件。",
        ),
    }


def parse_prose_response(response: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    """只接受選項索引；輸出文字一律來自程式產生的來源選項。"""
    try:
        data = json.loads(response.strip())
    except (json.JSONDecodeError, TypeError) as exc:
        raise RewriteValidationError(["模型回應不是有效 JSON 物件"]) from exc
    violations: list[str] = []
    if not isinstance(data, dict) or set(data) != {"schema_version", "items"}:
        raise RewriteValidationError(["模型回應頂層欄位不符結構契約"])
    if data.get("schema_version") != PROSE_SCHEMA_VERSION:
        violations.append("模型回應 schema_version 不符")
    items = data.get("items")
    expected = payload.get("top10", [])[:10]
    if not isinstance(items, list) or len(items) != 10 or len(expected) != 10:
        raise RewriteValidationError(violations + ["模型回應逐檔數量不是十筆"])
    accepted: list[dict[str, str]] = []
    for index, (item, source) in enumerate(zip(items, expected, strict=True), start=1):
        stock_id = str(source.get("stock_id") or "")
        if not isinstance(item, dict) or set(item) != {"stock_id", *PROSE_FIELDS}:
            violations.append(f"第 {index} 檔欄位不符結構契約")
            continue
        if str(item.get("stock_id")) != stock_id:
            violations.append(f"第 {index} 檔股票代號或順序不符：expected={stock_id}")
        accepted_item: dict[str, str] = {"stock_id": stock_id}
        choices = prose_choice_options(source)
        for field in PROSE_FIELDS:
            value = item.get(field)
            if type(value) is not int or value < 0 or value >= len(choices[field]):
                violations.append(f"第 {index} 檔 {field} 必須是有效整數選項索引")
            else:
                accepted_item[field] = choices[field][value]
        accepted.append(accepted_item)
    if violations:
        raise RewriteValidationError(violations)
    return accepted


def render_prose_message(payload: dict[str, Any], prose: list[dict[str, str]]) -> str:
    """以來源 payload 固定數值與身分，只插入模型的無數字文字。"""
    source_items = payload.get("top10", [])[:10]
    market = payload.get("market_overview")
    required_market = ("market_text", "capital_flow_text", "hot_groups_text", "hot_concepts_text")
    if not isinstance(market, dict) or any(not market.get(field) for field in required_market):
        raise RewriteValidationError(["payload 缺少必要大盤或資金欄位"])
    known_buckets = {
        row.get("name") for row in market.get("capital_flow", [])
        if isinstance(row, dict) and row.get("sector") != "現金"
    }
    canonical_buckets = canonical_capital_bucket_names(
        load_notification_industry_buckets(PROJECT_ROOT),
        load_notification_theme_buckets(PROJECT_ROOT),
    )
    if not known_buckets.issubset(canonical_buckets):
        raise RewriteValidationError(["payload 資金分類名稱不在既有分類表中"])
    if len(source_items) != 10 or len(prose) != 10:
        raise RewriteValidationError(["payload 或文字逐檔數量不是十筆"])
    lines = [
        f"Top10 每日選股｜{payload.get('ranking_date')}", "", "今日大盤與資金",
        f"- 大盤情況：{market['market_text']}",
        f"- 資金分布：{market['capital_flow_text']}",
        f"- 資金重心：{market['hot_groups_text']}",
        f"- 熱門概念：{market['hot_concepts_text']}", "", "今日 10 檔總覽",
    ]
    for source in source_items:
        lines.append(f"{source['rank']}. {source['stock_id']} {source['stock_name']}")
    lines.extend(["", "逐檔重點"])
    for source, item in zip(source_items, prose, strict=True):
        trade = source.get("trade_plan") or {}
        context = source.get("market_context") or {}
        if context.get("bucket") and context["bucket"] not in known_buckets:
            raise RewriteValidationError([f"payload {source.get('stock_id')} 族群標籤與大盤來源不符"])
        if context.get("bucket") and context["bucket"] not in canonical_buckets:
            raise RewriteValidationError([f"payload {source.get('stock_id')} 族群分類名稱不在既有分類表中"])
        role_label = ROLE_LABEL_BY_PAYLOAD_ROLE.get(str(source.get("list_role") or ""))
        low, high = observation_range_values(trade)
        observation_range = format_range(low, high)
        pressure = number_value(trade.get("pressure_price"))
        stop = number_value(trade.get("stop_loss"))
        if stop is None:
            stop = number_value(trade.get("trend_invalidation_price"))
        weight = number_value(context.get("bucket_weight"))
        if not role_label or not observation_range or pressure is None or stop is None:
            raise RewriteValidationError([f"payload {source.get('stock_id')} 缺少角色或必要交易數值"])
        if low is None or high is None or not math.isfinite(low) or not math.isfinite(high):
            raise RewriteValidationError([f"payload {source.get('stock_id')} 含非有限觀察區間"])
        if not all(math.isfinite(value) for value in (pressure, stop)) or (weight is not None and not math.isfinite(weight)):
            raise RewriteValidationError([f"payload {source.get('stock_id')} 含非有限數值"])
        lines.extend([
            "", f"{source['rank']}. {source['stock_id']} {source['stock_name']}",
            f"分組標籤：{role_label}",
            f"跟今天盤勢的關係：{item['market_relation']}",
        ])
        if context.get("bucket") and weight is not None:
            lines.append(f"族群比重：{context['bucket']} {weight * 100:.1f}%")
        lines.extend([
            f"為什麼入選：{item['selection_reason']}",
            f"怎麼看：{item['action']} 觀察區間 {observation_range}，上方第一壓力 {pressure:.2f} 元，跌破價 {stop:.2f} 元。",
            f"白話翻譯：{item['plain_translation']}",
        ])
    return "\n".join(lines).strip() + "\n"


def compact_payload_facts(payload: dict[str, Any]) -> dict[str, Any]:
    items = []
    for item in payload.get("top10", [])[:10]:
        group = item.get("audience_group") if isinstance(item.get("audience_group"), dict) else {}
        summary = item.get("notification_summary") if isinstance(item.get("notification_summary"), dict) else {}
        trade = item.get("trade_plan") if isinstance(item.get("trade_plan"), dict) else {}
        context = item.get("market_context") if isinstance(item.get("market_context"), dict) else {}
        entry_low, entry_high = observation_range_values(trade)
        pressure = number_value(trade.get("pressure_price"))
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
                    "pressure_price": f"{pressure:.2f} 元" if pressure is not None else None,
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


def bucket_weight_mentions(block: str, bucket: str) -> list[str]:
    """只取與該族群明確相連的百分比，逐一保留供數值核對。"""
    value = r"(?P<shown>(?:負\s*|[+\-−－]\s*)?\d+(?:\.\d+)?)\s*[%％]"
    patterns = (
        rf"^(?:(?!漲幅|漲跌|報酬)[^%％]){{0,40}}?[（(]\s*(?:約\s*)?{value}",
        rf"^\s*[，,]\s*(?:約\s*)?{value}",
        rf"^\s*[:：]\s*(?:約\s*)?{value}",
        rf"^\s*約\s*{value}",
        rf"^\s*(?:族群|產業)?\s+{value}",
        rf"(?:族群比重|比重|占比)\s*(?:約|為|[:：])?\s*{value}",
    )
    found: dict[int, str] = {}
    for mention in re.finditer(re.escape(bucket), block):
        clause = re.split(r"[。；;！？!?\n]|\s/\s", block[mention.end() :], maxsplit=1)[0][:80]
        for pattern in patterns:
            for match in re.finditer(pattern, clause):
                found[mention.end() + match.start("shown")] = match.group("shown")
    return list(found.values())


def normalize_markdown(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:markdown)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip() + "\n"


def validate_rewrite(message: str, payload: dict[str, Any]) -> None:
    violations = collect_rewrite_violations(message, payload) + verify_risk_grouping(payload, message)
    if violations:
        raise RewriteValidationError(violations)


def collect_rewrite_violations(message: str, payload: dict[str, Any]) -> list[str]:
    """一次掃描完整契約；任何一項違規仍拒收改寫。"""
    violations: list[str] = []
    if len(message) < 1200:
        violations.append("LLM 訊息過短，疑似沒有完整改寫")
    if len(message) > 12000:
        violations.append("LLM 訊息過長，可能不適合推播")
    ranking_date = str(payload.get("ranking_date") or "")
    if ranking_date and ranking_date not in message:
        violations.append("LLM 訊息缺少排名日期")
    rank_positions: list[tuple[int, int]] = []
    for item in payload.get("top10", [])[:10]:
        rank = item.get("rank")
        stock_id = str(item.get("stock_id") or "").strip()
        stock_name = str(item.get("stock_name") or "").strip()
        if stock_id and stock_id not in message:
            violations.append(f"LLM 訊息缺少股票代號 {stock_id}")
        if stock_name and stock_name not in message:
            violations.append(f"LLM 訊息缺少股票名稱 {stock_name}")
        if rank and stock_id:
            match = re.search(rf"(?m)^{int(rank)}\.\s+{re.escape(stock_id)}(?:\D|$)", message)
            if not match:
                violations.append(f"LLM 訊息未保留正確排名格式：{rank}. {stock_id}")
            else:
                rank_positions.append((int(rank), match.start()))
        trade = item.get("trade_plan") if isinstance(item.get("trade_plan"), dict) else {}
        entry_low, entry_high = observation_range_values(trade)
        expected_range = format_range(entry_low, entry_high)
        if expected_range and expected_range not in message:
            violations.append(f"LLM 訊息未保留 {stock_id} 正確觀察區間：{expected_range}")
        target = number_value(trade.get("target_price"))
        if entry_low is not None and target is not None:
            wrong_range = f"{entry_low:.2f} ~ {target:.2f} 元"
            if wrong_range in message:
                violations.append(f"LLM 訊息把 {stock_id} 目標價誤寫成觀察區間")
    expected_ranks = [int(item.get("rank")) for item in payload.get("top10", [])[:10] if item.get("rank")]
    ordered_ranks = [rank for rank, _ in sorted(rank_positions, key=lambda item: item[1])]
    if ordered_ranks != expected_ranks:
        violations.append(f"LLM 訊息排名順序錯誤：got={ordered_ranks}, expected={expected_ranks}")
    required_sections = ["大盤", "資金", "為什麼入選", "怎麼看", "白話翻譯"]
    missing = [section for section in required_sections if section not in message]
    if missing:
        violations.append(f"LLM 訊息缺少必要段落：{', '.join(missing)}")
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
        violations.append(f"LLM 訊息缺少分組標題：{', '.join(missing_role_sections)}")
    message_items = parse_message_item_blocks(message)
    if len(message_items) != 10:
        violations.append(f"LLM 訊息逐檔區塊數量錯誤：got={len(message_items)}, expected=10")
    expected_keys = [(int(item.get("rank")), str(item.get("stock_id") or "").zfill(4)) for item in payload.get("top10", [])[:10] if item.get("rank")]
    actual_keys = [(item["rank"], item["stock_id"]) for item in message_items]
    if actual_keys != expected_keys:
        violations.append(f"LLM 訊息逐檔順序錯誤：got={actual_keys}, expected={expected_keys}")
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
            violations.append(f"LLM 訊息 {stock_id} 分組錯誤：got={actual_label}, expected={expected_label}")
        if message_item is None:
            continue
        block = str(message_item["block"])
        context = item.get("market_context") if isinstance(item.get("market_context"), dict) else {}
        bucket = str(context.get("bucket") or "").strip()
        if bucket:
            # 只核對文案實際寫出的族群比重；缺席不是完整性違規。
            shown_weights = bucket_weight_mentions(block, bucket)
            source_weight = number_value(context.get("bucket_weight"))
            for shown in shown_weights:
                if source_weight is None:
                    violations.append(f"LLM 訊息 {stock_id} 族群比重缺少來源：got={shown}%")
                else:
                    expected_weight = f"{source_weight * 100:.1f}"
                    normalized = re.sub(r"\s+", "", shown.replace("負", "-").replace("−", "-").replace("－", "-"))
                    if float(normalized) != float(expected_weight):
                        violations.append(
                            f"LLM 訊息 {stock_id} 族群比重不符：got={shown}%, expected={expected_weight}%"
                        )
        trade = item.get("trade_plan") if isinstance(item.get("trade_plan"), dict) else {}
        pressure = number_value(trade.get("pressure_price"))
        pressure_matches = re.findall(r"上方第一壓力(?:先看)?\s*[:：]?\s*([\d,]+(?:\.\d+)?)", block)
        if pressure is not None:
            if not pressure_matches:
                violations.append(f"LLM 訊息 {stock_id} 缺少上方第一壓力：expected={pressure:.2f}")
            for pressure_text in pressure_matches:
                if round(float(pressure_text.replace(",", "")), 2) != round(pressure, 2):
                    violations.append(
                        f"LLM 訊息 {stock_id} 上方第一壓力不符：got={pressure_text}, expected={pressure:.2f}"
                    )
        allowed_stops = {
            round(value, 2)
            for value in (number_value(trade.get("trend_invalidation_price")), number_value(trade.get("stop_loss")))
            if value is not None
        }
        stop_matches = re.findall(r"(?:跌破價|跌破|趨勢失效價另看)\s*[:：]?\s*([\d,]+(?:\.\d+)?)", block)
        if allowed_stops:
            if not stop_matches:
                violations.append(f"LLM 訊息 {stock_id} 缺少跌破價或趨勢失效價")
            for stop_text in stop_matches:
                if round(float(stop_text.replace(",", "")), 2) not in allowed_stops:
                    violations.append(
                        f"LLM 訊息 {stock_id} 跌破價不符：got={stop_text}, expected={sorted(allowed_stops)}"
                    )
    if message.count("為什麼入選") < 8 or message.count("白話翻譯") < 8:
        violations.append("LLM 訊息沒有完整覆蓋足夠多檔股票")
    if re.search(r"(?m)^#{1,6}\s+", message):
        violations.append("LLM 訊息不可使用 Markdown # 標題，請改用純文字段落標籤")
    banned_patterns = [
        r"建議(?:資金|部位)\s*\d",
        r"(?:勝率|模型把握度)\s*\d",
        r"\d+(?:\.\d+)?%\s*(?:資金|部位|勝率|模型把握度)",
    ]
    for pattern in banned_patterns:
        if re.search(pattern, message):
            violations.append(f"LLM 訊息包含禁止格式：{pattern}")
    return violations


def compact_home(path_text: str) -> str:
    home = str(Path.home())
    if path_text.startswith(home):
        return "~" + path_text[len(home) :]
    return path_text


def redact_key_text(text: str) -> str:
    return re.sub(r"AIza[0-9A-Za-z_-]+", "<redacted>", text)


if __name__ == "__main__":
    raise SystemExit(main())

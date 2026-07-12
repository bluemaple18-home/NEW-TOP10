#!/usr/bin/env python3
"""把 PM 補說明池轉成更清楚的 review card，必要時重送 Discord。

本腳本只處理 `needs_review` 決策後的補說明重送：
- 讀取既有 clarification_queue.jsonl。
- 產生新的 PM review card run_dir。
- 可選擇透過 OpenClaw gateway 送到 review-approval。

不改 ranking、不訓練模型、不改推播。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.rewrite_clawd_publish_message_llm import (  # noqa: E402
    DEFAULT_ENV_FILE,
    build_attempts,
    load_env_file,
    normalize_markdown,
    resolve_models,
    rotate_values,
    run_gemini,
    split_values,
)

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
PROJECT_DOMAIN = "TOP10_STOCK"
SCHEMA_VERSION = "top10-pm-clarification-review-cards.v1"
DEFAULT_LLM_MODEL = "gemini-2.5-flash"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build PM clarification review cards")
    parser.add_argument("--source-run-dir", required=True, help="repo-relative PM review card run dir")
    parser.add_argument("--date", default=None)
    parser.add_argument("--max-cards", type=int, default=5)
    parser.add_argument("--output-run-dir", default=None)
    parser.add_argument("--config", default="config/automation.yaml")
    parser.add_argument("--send-cards", action="store_true")
    parser.add_argument("--dry-run-send", action="store_true")
    parser.add_argument("--target", default=None)
    parser.add_argument("--node-bin", default=None)
    parser.add_argument("--openclaw-entry", default=None)
    parser.add_argument("--use-llm", action="store_true", help="用 Gemini 重寫補說明卡；失敗時回退模板")
    parser.add_argument("--env-file", default=os.environ.get("TOP10_LLM_REWRITE_ENV_FILE") or str(DEFAULT_ENV_FILE))
    parser.add_argument("--models", default=None, help="逗號分隔 Gemini 模型清單；未指定時讀既有 env")
    parser.add_argument("--timeout-seconds", type=int, default=int(os.environ.get("TOP10_PM_CLARIFICATION_LLM_TIMEOUT_SECONDS", "90")))
    parser.add_argument("--max-output-tokens", type=int, default=int(os.environ.get("TOP10_PM_CLARIFICATION_LLM_MAX_OUTPUT_TOKENS", "3000")))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("TOP10_PM_CLARIFICATION_LLM_TEMPERATURE", "0.35")))
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def read_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return fallback or {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else (fallback or {})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def local_date(config: dict[str, Any]) -> str:
    timezone_name = str(config.get("timezone") or "Asia/Taipei")
    return datetime.now(ZoneInfo(timezone_name)).date().isoformat()


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def gateway_defaults(config: dict[str, Any]) -> tuple[str, str, str]:
    notify = config.get("notify") if isinstance(config.get("notify"), dict) else {}
    node_bin = str(notify.get("clawd_cli_node") or "/opt/homebrew/opt/node/bin/node")
    openclaw_entry = str(Path.home() / "new clawd" / "openclaw.mjs")
    target = str(notify.get("review_approval_clawd_to") or notify.get("ops_clawd_to") or "channel:1519179377336651796")
    return node_bin, openclaw_entry, target


def source_card_markdown(source_run_dir: Path, card_id: str) -> str:
    path = source_run_dir / f"{card_id}.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def first_bullets(markdown: str, limit: int = 4) -> list[str]:
    bullets = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped)
        if len(bullets) >= limit:
            break
    return bullets


def artifact_paths_from_markdown(markdown: str) -> list[str]:
    paths = []
    for line in markdown.splitlines():
        stripped = line.strip().lstrip("-").strip()
        candidate = stripped.split(":", 1)[0].strip()
        if candidate.startswith("artifacts/") and candidate.endswith(".json"):
            paths.append(candidate)
    return paths


def read_external_review_summary(original_markdown: str) -> dict[str, Any]:
    for path_text in artifact_paths_from_markdown(original_markdown):
        if "/external_review/" not in path_text:
            continue
        path = resolve_path(path_text)
        payload = read_json(path, {})
        if payload.get("schema_version") == "external-review-summary.v1":
            return payload
    return {}


def build_judgment_gap_lines(summary: dict[str, Any]) -> list[str]:
    misses = [item for item in summary.get("today_misses", []) if isinstance(item, dict)]
    if not misses:
        return [
            "- 我們這邊：原卡表示 TOP10 系統與外部檢核有分歧，但缺少逐項落差整理。",
            "- 外部檢核：summary 未提供可解析的 today_misses。",
            "- 落差：需要先補齊外部檢核與系統判斷的對照表，再決定是否進研究。",
        ]
    provider_names = sorted({str(item.get("provider") or "external") for item in misses})
    provider_label = " / ".join(provider_names)
    symbols = [str(item.get("symbol") or "").strip() for item in misses if item.get("symbol")]
    avoid = []
    tomorrow = summary.get("tomorrow_watch") if isinstance(summary.get("tomorrow_watch"), dict) else {}
    if isinstance(tomorrow.get("avoid_chasing"), list):
        avoid = [str(item) for item in tomorrow["avoid_chasing"] if str(item) in symbols]
    return [
        f"- 我們這邊：TOP10 系統把 {', '.join(symbols) or '這些標的'} 放在本期報牌/候選判斷脈絡中，需要 PM 決定是否後續複核。",
        f"- {provider_label}：外部檢核把 {', '.join(avoid or symbols)} 標成 avoid_chasing / today_misses。",
        "- 落差：系統偏向把它們視為可追蹤的動能/突破題材；外部檢核認為其中存在追高、開高走低、停損過寬或風報比失衡風險。",
    ]


def build_evidence_lines(summary: dict[str, Any], original_markdown: str) -> list[str]:
    rows = []
    misses = [item for item in summary.get("today_misses", []) if isinstance(item, dict)]
    for item in misses[:4]:
        symbol = str(item.get("symbol") or "").strip()
        name = str(item.get("name") or "").strip()
        provider = str(item.get("provider") or "external").strip()
        evidence = str(item.get("evidence") or item.get("issue") or "").strip()
        if len(evidence) > 150:
            evidence = evidence[:147].rstrip() + "..."
        label = f"{symbol} {name}".strip()
        rows.append(f"- {label}｜{provider}: {evidence}")
    for path_text in artifact_paths_from_markdown(original_markdown):
        if "/external_review/" in path_text:
            rows.append(f"- {path_text}: 外部檢核 summary，可追溯完整 reviewer 原文與 normalize 結果")
            break
    return rows or first_bullets(original_markdown)


def build_clarification_markdown(new_card_id: str, row: dict[str, Any], original_markdown: str) -> str:
    source_card_id = str(row.get("card_id") or "")
    title = str(row.get("title") or source_card_id or new_card_id)
    next_harness = str(row.get("next_harness") or row.get("owner") or "manual_followup")
    run_dir = str(row.get("run_dir") or "")
    summary = read_external_review_summary(original_markdown)
    evidence_lines = build_evidence_lines(summary, original_markdown)
    judgment_gap = build_judgment_gap_lines(summary)
    lines = [
        f"專案：{PROJECT_DOMAIN}｜台股 TOP10 研究審核",
        "",
        f"{new_card_id}｜補說明重送：{title}",
        f"來源卡：{source_card_id}",
        "狀態：補說明後待決策",
        "",
        "一句話問題：",
        f"外部檢核對「{title}」提出分歧，現在要判斷這些分歧值不值得轉成內部研究/人工複核。",
        "",
        "要你決定：",
        f"是否交給 `{next_harness}` 做 research-only 複核。因為外部意見不能直接改正式排名或推播，只有你核准後才會形成可追溯研究證據；延後代表晚點再問，不核准代表關閉這張卡。",
        "",
        "判斷落差：",
        *judgment_gap,
        "",
        "證據：",
    ]
    if evidence_lines:
        lines.extend(evidence_lines)
    else:
        lines.append(f"- {run_dir}: 原始 PM review card run_dir")
    lines.extend(
        [
            "",
            "邊界：只允許 research-only 或人工複核；不採納外部 AI 結論、不改排名、不改推播、不訓練模型、不做 production promotion。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_llm_prompt(new_card_id: str, row: dict[str, Any], template_markdown: str, original_markdown: str) -> str:
    source_card_id = str(row.get("card_id") or "")
    title = str(row.get("title") or source_card_id or new_card_id)
    return "\n".join(
        [
            "請把 TOP10 PM 審核卡重寫成 PM 看得懂的繁體中文任務卡。",
            "",
            "重要限制：",
            "- 只能根據輸入資料改寫，不得新增未提供的股票結論、績效數字、交易建議或模型判斷。",
            "- 不要解釋四顆按鈕怎麼用。",
            "- 不要寫教學文；請直接把這張任務卡本身寫清楚。",
            "- 必須保留 research-only 邊界：不能改正式 Top10、權重、模型、推播或 production promotion。",
            "- 不得建議買賣、進出場、目標價、停損價或倉位。",
            "",
            "輸出格式：",
            f"{new_card_id}｜補說明重送：{title}",
            f"來源卡：{source_card_id}",
            "狀態：補說明後待決策",
            "",
            "一句話問題：",
            "要你決定：",
            "判斷落差：",
            "證據：",
            "邊界：",
            "",
            "去重要求：",
            "- 每一段只能講一個新資訊，不要重複說「轉成研究」四次。",
            "- 判斷落差必須寫清楚主詞：我們這邊怎麼判斷、Gemini/外部檢核怎麼判斷、兩者落差在哪。",
            "- 證據段只能支撐判斷落差，不要只貼股票片段讓 PM 自己猜。",
            "- 不要寫「背景 / 目前問題 / 請你判斷 / 建議動作 / 為什麼現在要決定 / 要你拍板」這些舊標題。",
            "- 全文控制在 350 到 900 字之間。",
            "- 如果不確定格式，至少先把任務本身用人話重寫；固定欄位會由本地腳本補齊。",
            "",
            "請輸出 Markdown，不要包 ```。",
            "",
            "原卡 Markdown：",
            original_markdown[:5000],
            "",
            "模板草稿，可參考但請改寫得更像人話：",
            template_markdown[:5000],
            "",
            "結構化 queue row：",
            json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True)[:3000],
        ]
    )


def section_text(markdown: str, heading: str) -> str:
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        stripped_line = line.strip()
        inline_prefix = f"{heading}："
        if stripped_line.startswith(inline_prefix) and stripped_line != inline_prefix:
            inline_body = stripped_line[len(inline_prefix) :].strip()
            collected = [inline_body] if inline_body else []
            for next_line in lines[index + 1 :]:
                stripped = next_line.strip()
                if stripped.endswith("：") and not stripped.startswith("- "):
                    break
                if stripped:
                    collected.append(next_line)
            return "\n".join(collected).strip()
        if stripped_line == inline_prefix:
            collected = []
            for next_line in lines[index + 1 :]:
                stripped = next_line.strip()
                if stripped.endswith("：") and not stripped.startswith("- "):
                    break
                if stripped:
                    collected.append(next_line)
            return "\n".join(collected).strip()
    return ""


def replace_section(markdown: str, heading: str, body: str) -> str:
    lines = markdown.splitlines()
    start = None
    end = None
    for index, line in enumerate(lines):
        if line.strip() == f"{heading}：":
            start = index
            end = len(lines)
            for next_index, next_line in enumerate(lines[index + 1 :], start=index + 1):
                stripped = next_line.strip()
                if stripped.endswith("：") and not stripped.startswith("- "):
                    end = next_index
                    break
            break
    replacement = [f"{heading}：", *body.splitlines()]
    if start is None:
        return f"{markdown.rstrip()}\n\n" + "\n".join(replacement)
    return "\n".join([*lines[:start], *replacement, *lines[end:]]).strip()


def ensure_pm_card_sections(markdown: str, template_markdown: str) -> str:
    text = markdown.strip()
    for heading in ["一句話問題", "要你決定", "判斷落差", "證據", "邊界"]:
        if heading in {"判斷落差", "證據"}:
            fallback = section_text(template_markdown, heading)
            if fallback:
                text = replace_section(text, heading, fallback)
            continue
        existing = section_text(text, heading)
        if len(existing) >= 20:
            continue
        fallback = section_text(template_markdown, heading)
        if fallback:
            text = replace_section(text, heading, fallback)
    return text.strip() + "\n"


def validate_llm_markdown(markdown: str, *, new_card_id: str, source_card_id: str) -> None:
    if len(markdown.strip()) < 80:
        raise ValueError("LLM 補說明卡過短")
    if len(markdown) > 5000:
        raise ValueError("LLM 補說明卡過長")
    required = [
        new_card_id,
        source_card_id,
        "一句話問題",
        "要你決定",
        "判斷落差",
        "證據",
    ]
    missing = [item for item in required if item and item not in markdown]
    if missing:
        raise ValueError(f"LLM 補說明卡缺少必要文字：{missing}")
    flexible_required = {
        "要你決定": ["要你決定", "要你拍板", "請你判斷"],
        "判斷落差": ["判斷落差", "我們這邊", "Gemini"],
        "證據": ["證據", "需要看的證據"],
        "邊界": ["邊界", "決策邊界"],
    }
    missing_flexible = [
        key for key, aliases in flexible_required.items() if not any(alias in markdown for alias in aliases)
    ]
    if missing_flexible:
        raise ValueError(f"LLM 補說明卡缺少必要段落：{missing_flexible}")
    short_sections = [
        heading
        for heading in ["一句話問題", "要你決定", "判斷落差", "證據", "邊界"]
        if len(section_text(markdown, heading)) < 20
    ]
    if short_sections:
        raise ValueError(f"LLM 補說明卡段落過短：{short_sections}")
    if not any(term in markdown for term in ["research-only", "研究/人工複核", "研究任務", "複核任務"]):
        raise ValueError("LLM 補說明卡缺少 research-only 或中文等價邊界")
    duplicate_old_headers = ["背景：", "目前問題：", "請你判斷：", "建議動作：", "為什麼現在要決定：", "要你拍板："]
    hits_old_headers = [item for item in duplicate_old_headers if item in markdown]
    if hits_old_headers:
        raise ValueError(f"LLM 補說明卡使用舊式重複標題：{hits_old_headers}")
    forbidden = [
        "建議買",
        "建議賣",
        "買進",
        "賣出",
        "目標價",
        "建議停損價",
        "上線 production",
    ]
    hits = [item for item in forbidden if item in markdown]
    if hits:
        raise ValueError(f"LLM 補說明卡含禁止承諾或交易語句：{hits}")


def rewrite_with_llm(
    *,
    new_card_id: str,
    row: dict[str, Any],
    template_markdown: str,
    original_markdown: str,
    args: argparse.Namespace,
    date_text: str,
) -> tuple[str, dict[str, Any]]:
    file_env = load_env_file(Path(args.env_file).expanduser()) if args.env_file else {}
    merged_env = {**file_env, **os.environ}
    keys = rotate_values(split_values(str(merged_env.get("GEMINI_API_KEYS") or "")), date_text)
    models = resolve_models(args.models or DEFAULT_LLM_MODEL, merged_env)
    status: dict[str, Any] = {
        "provider": "gemini",
        "status": "RUNNING",
        "models_attempted": [],
        "selected_model": None,
        "selected_key_index": None,
        "errors": [],
    }
    if not keys:
        raise RuntimeError("找不到 GEMINI_API_KEYS")
    source_card_id = str(row.get("card_id") or "")
    prompt = build_llm_prompt(new_card_id, row, template_markdown, original_markdown)
    for model, key_index, api_key in build_attempts(models, keys, date_text):
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
            rewritten = ensure_pm_card_sections(rewritten, template_markdown)
            validate_llm_markdown(rewritten, new_card_id=new_card_id, source_card_id=source_card_id)
            status["status"] = "OK"
            status["selected_model"] = model
            status["selected_key_index"] = key_index
            return rewritten, status
        except Exception as exc:  # noqa: BLE001 - 單一模型失敗要嘗試 fallback。
            status["errors"].append(f"{model} key#{key_index}: {exc}")
    raise RuntimeError("; ".join(status["errors"]) or "LLM 補說明重寫失敗")


def build_clarification_review_cards(
    *,
    source_run_dir: Path,
    output_run_dir: Path,
    date_text: str,
    max_cards: int,
    use_llm: bool = False,
    args: argparse.Namespace | None = None,
) -> dict[str, Any]:
    cards_payload = read_json(source_run_dir / "cards.json", {})
    if cards_payload.get("project_domain") != PROJECT_DOMAIN:
        raise ValueError("source cards.json project_domain mismatch or missing")
    source_cards = cards_payload.get("cards") if isinstance(cards_payload.get("cards"), dict) else {}
    rows = [
        row
        for row in read_jsonl(source_run_dir / "clarification_queue.jsonl")
        if row.get("project_domain") == PROJECT_DOMAIN and row.get("decision") == "needs_review"
    ][:max_cards]
    output_run_dir.mkdir(parents=True, exist_ok=True)
    token = date_text.replace("-", "")[2:]
    stamp = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%H%M%S")
    output_cards: dict[str, dict[str, Any]] = {}
    built = []
    llm_results = []
    for index, row in enumerate(rows, start=1):
        source_card_id = str(row.get("card_id") or f"UNKNOWN-{index:02d}")
        source_card = source_cards.get(source_card_id) if isinstance(source_cards.get(source_card_id), dict) else {}
        new_card_id = f"CL{token}-{stamp}-{index:02d}"
        title = f"補說明重送：{row.get('title') or source_card.get('title') or source_card_id}"
        next_harness = str(row.get("next_harness") or source_card.get("next_harness") or "manual_followup")
        output_cards[new_card_id] = {
            "card_id": new_card_id,
            "project_domain": PROJECT_DOMAIN,
            "title": title,
            "owner": next_harness,
            "next_harness": next_harness,
            "source_card_id": source_card_id,
            "source_run_dir": repo_path(source_run_dir),
            "clarification_of": source_card_id,
        }
        original_markdown = source_card_markdown(source_run_dir, source_card_id)
        template_markdown = build_clarification_markdown(new_card_id, row, original_markdown)
        markdown = template_markdown
        llm_status: dict[str, Any] = {"status": "SKIPPED", "reason": "use_llm disabled"}
        if use_llm:
            if args is None:
                raise ValueError("args required when use_llm is true")
            try:
                markdown, llm_status = rewrite_with_llm(
                    new_card_id=new_card_id,
                    row=row,
                    template_markdown=template_markdown,
                    original_markdown=original_markdown,
                    args=args,
                    date_text=date_text,
                )
            except Exception as exc:  # noqa: BLE001 - 補說明可回退模板，但要留下狀態。
                llm_status = {"status": "FALLBACK", "provider": "gemini", "errors": [str(exc)]}
        (output_run_dir / f"{new_card_id}.md").write_text(markdown, encoding="utf-8")
        built.append({"card_id": new_card_id, "source_card_id": source_card_id})
        llm_results.append({"card_id": new_card_id, "source_card_id": source_card_id, **llm_status})

    output_payload = {
        "schema_version": "top10.pm_review_cards.v1",
        "project_domain": PROJECT_DOMAIN,
        "run_dir": repo_path(output_run_dir),
        "purpose": "TOP10 PM 補說明重送卡。原卡因 needs_review 進入 clarification_queue。",
        "source_run_dir": repo_path(source_run_dir),
        "cards": output_cards,
    }
    write_json(output_run_dir / "cards.json", output_payload)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "project_domain": PROJECT_DOMAIN,
        "date": date_text,
        "source_run_dir": repo_path(source_run_dir),
        "output_run_dir": repo_path(output_run_dir),
        "built_count": len(built),
        "built_cards": built,
        "llm_enabled": use_llm,
        "llm_results": llm_results,
        "status": "READY" if built else "EMPTY",
    }
    write_json(output_run_dir / "clarification_resend_manifest.json", manifest)
    return manifest


def send_pm_cards(*, run_dir: Path, config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    node_default, entry_default, target_default = gateway_defaults(config)
    node_bin = args.node_bin or node_default
    openclaw_entry = args.openclaw_entry or entry_default
    target = args.target or target_default
    params = {
        "run_dir": repo_path(run_dir),
        "target": target,
        "dry_run": bool(args.dry_run_send),
    }
    command = [
        node_bin,
        openclaw_entry,
        "gateway",
        "call",
        "top10.pm_review.send_cards",
        "--json",
        "--timeout",
        "15000",
        "--params",
        json.dumps(params, ensure_ascii=False),
    ]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True)
    return {
        "command": [*command[:9], "<params>"],
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-4000:],
        "status": "OK" if completed.returncode == 0 else "FAILED",
    }


def main() -> int:
    args = parse_args()
    config = load_config(resolve_path(args.config))
    date_text = args.date or local_date(config)
    source_run_dir = resolve_path(args.source_run_dir)
    if args.output_run_dir:
        output_run_dir = resolve_path(args.output_run_dir)
    else:
        stamp = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%H%M%S")
        output_run_dir = ARTIFACTS_DIR / "pm_review_cards" / f"{date_text}-clarification-resend-{stamp}"
    manifest = build_clarification_review_cards(
        source_run_dir=source_run_dir,
        output_run_dir=output_run_dir,
        date_text=date_text,
        max_cards=args.max_cards,
        use_llm=args.use_llm,
        args=args,
    )
    send_result = None
    if args.send_cards and manifest["built_count"]:
        send_result = send_pm_cards(run_dir=output_run_dir, config=config, args=args)
        if send_result["status"] != "OK":
            raise RuntimeError(f"failed to send clarification review cards: {send_result['stderr'] or send_result['stdout']}")
    print(json.dumps({**manifest, "send_result": send_result}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

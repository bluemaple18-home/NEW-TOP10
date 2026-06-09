#!/usr/bin/env python3
"""合併 ChatGPT / Gemini 盤後外部 review。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "external-review-summary.v1"
REVIEW_SCHEMA_VERSION = "external-review.v1"
PROVIDERS = ("chatgpt", "gemini")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build daily external review summary")
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifacts-dir", default=Path("artifacts/external_review"), type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review_dir = args.artifacts_dir / args.date
    reviews = load_reviews(review_dir, args.date)
    summary = build_summary(args.date, reviews)

    json_path = review_dir / f"external_review_summary_{args.date}.json"
    md_path = review_dir / f"external_review_summary_{args.date}.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(summary), encoding="utf-8")
    print(f"EXTERNAL_REVIEW_SUMMARY_OK json={json_path} md={md_path}")
    return 0


def load_reviews(review_dir: Path, review_date: str) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    for provider in PROVIDERS:
        path = review_dir / f"{provider}_response_{review_date}.json"
        status = review_dir / f"{provider}_collect_status_{review_date}.json"
        if not path.exists():
            reviews.append(
                {
                    "provider": provider,
                    "path": str(path),
                    "status_path": str(status),
                    "valid": False,
                    "reason": "response_missing",
                }
            )
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            reviews.append(
                {
                    "provider": provider,
                    "path": str(path),
                    "status_path": str(status),
                    "valid": False,
                    "reason": f"invalid_json:{exc}",
                }
            )
            continue
        errors = review_errors(payload, provider, review_date)
        reviews.append(
            {
                "provider": provider,
                "path": str(path),
                "status_path": str(status),
                "valid": not errors,
                "reason": "ok" if not errors else "; ".join(errors),
                "payload": payload if not errors else None,
            }
        )
    return reviews


def review_errors(payload: dict[str, Any], provider: str, review_date: str) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != REVIEW_SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    if payload.get("provider") != provider:
        errors.append("provider_mismatch")
    if payload.get("review_date") != review_date:
        errors.append("review_date_mismatch")
    safety = object_value(payload.get("safety"))
    if safety.get("algorithm_requested") is True or safety.get("contains_algorithm_claim") is True:
        errors.append("algorithm_boundary_violation")
    return errors


def build_summary(review_date: str, reviews: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [review for review in reviews if review.get("valid") and isinstance(review.get("payload"), dict)]
    payloads = [review["payload"] for review in valid]
    provider_rows = [provider_row(review) for review in reviews]
    needs_human_review = any(object_value(payload.get("safety")).get("needs_human_review") for payload in payloads)
    invalid_providers = [review["provider"] for review in reviews if not review.get("valid")]

    summary = {
        "schema_version": SCHEMA_VERSION,
        "review_date": review_date,
        "providers": provider_rows,
        "valid_provider_count": len(valid),
        "consensus": build_consensus(payloads),
        "disagreements": build_disagreements(payloads),
        "today_misses": build_today_misses(payloads),
        "tomorrow_watch": build_tomorrow_watch(payloads),
        "research_hypotheses": build_summary_hypotheses(payloads),
        "safety": {
            "needs_human_review": bool(needs_human_review or invalid_providers),
            "invalid_providers": invalid_providers,
            "algorithm_requested": any(object_value(payload.get("safety")).get("algorithm_requested") for payload in payloads),
            "contains_algorithm_claim": any(object_value(payload.get("safety")).get("contains_algorithm_claim") for payload in payloads),
        },
        "promotion_boundary": {
            "external_review_is_research_only": True,
            "promotion_ready": False,
            "may_change_ranking_or_model": False,
            "required_next_gate": "historical_replay_or_shadow_ranking_before_any_model_change",
        },
    }
    if len(valid) == 1:
        summary["single_reviewer_only"] = True
    return summary


def provider_row(review: dict[str, Any]) -> dict[str, Any]:
    payload = object_value(review.get("payload"))
    overall = object_value(payload.get("overall"))
    safety = object_value(payload.get("safety"))
    return {
        "provider": review.get("provider", ""),
        "valid": bool(review.get("valid")),
        "reason": review.get("reason", ""),
        "path": review.get("path", ""),
        "score": overall.get("score"),
        "verdict": overall.get("verdict"),
        "needs_human_review": bool(safety.get("needs_human_review", not review.get("valid"))),
    }


def build_consensus(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not payloads:
        return []
    theme_counts = count_values(payloads, ("themes", "strong"))
    watch_counts = count_values(payloads, ("tomorrow_watch", "avoid_chasing"))
    consensus: list[dict[str, Any]] = []
    for theme, providers in theme_counts.items():
        if len(providers) >= 2 or len(payloads) == 1:
            consensus.append({"type": "theme", "item": theme, "providers": sorted(providers)})
    for symbol, providers in watch_counts.items():
        if len(providers) >= 2 or len(payloads) == 1:
            consensus.append({"type": "avoid_chasing", "item": symbol, "providers": sorted(providers)})
    if not consensus and len(payloads) == 1:
        for item in list_value(payloads[0].get("observations"))[:5]:
            if isinstance(item, dict):
                consensus.append(
                    {
                        "type": item.get("type", "observation"),
                        "item": item.get("title", ""),
                        "providers": [payloads[0].get("provider", "")],
                    }
                )
    return consensus[:12]


def build_disagreements(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(payloads) < 2:
        return []
    provider_scores = {payload.get("provider", ""): object_value(payload.get("overall")).get("score") for payload in payloads}
    scores = [score for score in provider_scores.values() if isinstance(score, int)]
    disagreements: list[dict[str, Any]] = []
    if scores and max(scores) - min(scores) >= 15:
        disagreements.append(
            {
                "type": "score_gap",
                "title": "reviewer score gap",
                "detail": f"provider_scores={provider_scores}",
                "providers": sorted(provider_scores),
            }
        )
    miss_symbols = count_miss_symbols(payloads)
    for symbol, providers in miss_symbols.items():
        if len(providers) == 1 and symbol:
            disagreements.append(
                {
                    "type": "single_provider_miss",
                    "title": f"{symbol} only flagged by {next(iter(providers))}",
                    "detail": "保留單一 reviewer 標記，不在 summary 中平均掉。",
                    "providers": sorted(providers),
                }
            )
    return disagreements[:12]


def build_today_misses(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    misses: list[dict[str, Any]] = []
    for payload in payloads:
        provider = payload.get("provider", "")
        for miss in list_value(payload.get("misses")):
            if not isinstance(miss, dict):
                continue
            item = dict(miss)
            item["provider"] = provider
            misses.append(item)
    return misses[:20]


def build_tomorrow_watch(payloads: list[dict[str, Any]]) -> dict[str, list[str]]:
    result = {
        "continue": [],
        "avoid_chasing": [],
        "watch_for_reversal": [],
        "theme_candidates": [],
    }
    for payload in payloads:
        watch = object_value(payload.get("tomorrow_watch"))
        for key in result:
            result[key].extend(string_list(watch.get(key)))
    return {key: unique_strings(values)[:20] for key, values in result.items()}


def build_summary_hypotheses(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hypotheses: list[dict[str, Any]] = []
    seen: set[str] = set()
    for payload in payloads:
        provider = payload.get("provider", "")
        for item in list_value(payload.get("research_hypotheses")):
            if not isinstance(item, dict):
                continue
            key = f"{item.get('hypothesis')}|{item.get('candidate_signal_family')}"
            if key in seen:
                continue
            seen.add(key)
            row = dict(item)
            row["provider"] = provider
            hypotheses.append(row)
    return hypotheses[:20]


def count_values(payloads: list[dict[str, Any]], path: tuple[str, str]) -> dict[str, set[str]]:
    counts: dict[str, set[str]] = {}
    for payload in payloads:
        provider = str(payload.get("provider", ""))
        values = string_list(object_value(payload.get(path[0])).get(path[1]))
        for value in values:
            counts.setdefault(value, set()).add(provider)
    return counts


def count_miss_symbols(payloads: list[dict[str, Any]]) -> dict[str, set[str]]:
    counts: dict[str, set[str]] = {}
    for payload in payloads:
        provider = str(payload.get("provider", ""))
        for miss in list_value(payload.get("misses")):
            if not isinstance(miss, dict):
                continue
            symbol = str(miss.get("symbol") or "").strip()
            if symbol:
                counts.setdefault(symbol, set()).add(provider)
    return counts


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# External Review Summary｜{summary['review_date']}",
        "",
        "## Providers",
    ]
    for provider in summary["providers"]:
        lines.append(
            f"- {provider['provider']}: valid={provider['valid']} score={provider.get('score')} reason={provider.get('reason')}"
        )
    lines.extend(["", "## Consensus"])
    for item in summary["consensus"] or [{"type": "none", "item": "無雙 reviewer 共識", "providers": []}]:
        lines.append(f"- {item['type']}: {item['item']} ({', '.join(item.get('providers', []))})")
    lines.extend(["", "## Misses"])
    for miss in summary["today_misses"][:10]:
        label = f"{miss.get('symbol', '')} {miss.get('name', '')}".strip() or "未指定標的"
        lines.append(f"- {label}: {miss.get('issue')} [{miss.get('provider')}]")
    lines.extend(["", "## Tomorrow Watch"])
    for key, values in summary["tomorrow_watch"].items():
        lines.append(f"- {key}: {', '.join(values) if values else '無'}")
    lines.extend(["", "## Research Hypotheses"])
    for item in summary["research_hypotheses"][:10]:
        lines.append(f"- {item.get('hypothesis')} ({item.get('candidate_signal_family')}, {item.get('priority')})")
    lines.extend(
        [
            "",
            "## Boundary",
            "- External review is research-only.",
            "- No ranking, model, weight, publish, or promotion change is authorized by this summary.",
            "",
        ]
    )
    return "\n".join(lines)


def object_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in result:
            result.append(item)
    return result


if __name__ == "__main__":
    raise SystemExit(main())

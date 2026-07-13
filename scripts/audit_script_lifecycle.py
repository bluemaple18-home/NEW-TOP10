#!/usr/bin/env python3
"""建立 tracked scripts 的唯讀生命週期清冊。"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "config" / "script_lifecycle.yaml"
VALID_CATEGORIES = {
    "production_entrypoint",
    "maintenance",
    "research",
    "builder",
    "verifier",
    "legacy_candidate",
    "unclassified",
}


@dataclass(frozen=True)
class LifecyclePolicy:
    production_entrypoints: frozenset[str]
    prefix_categories: tuple[tuple[str, tuple[str, ...]], ...]
    overrides: dict[str, dict[str, str]]
    approved_unclassified: frozenset[str]


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_policy(path: Path = POLICY_PATH) -> LifecyclePolicy:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "script-lifecycle-policy.v1":
        raise ValueError("unsupported script lifecycle policy")

    production = frozenset(payload.get("production_entrypoints", []))
    prefix_categories: list[tuple[str, tuple[str, ...]]] = []
    for rule in payload.get("prefix_categories", []):
        category = rule.get("category")
        prefixes = rule.get("prefixes", [])
        if category not in VALID_CATEGORIES - {"production_entrypoint", "legacy_candidate", "unclassified"}:
            raise ValueError(f"invalid prefix category: {category}")
        if not prefixes or not all(isinstance(prefix, str) and prefix for prefix in prefixes):
            raise ValueError(f"invalid prefixes for {category}")
        prefix_categories.append((category, tuple(prefixes)))

    overrides = payload.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("overrides must be a mapping")
    for script_path, override in overrides.items():
        validate_script_path(script_path)
        if not isinstance(override, dict) or override.get("category") not in VALID_CATEGORIES - {"production_entrypoint", "unclassified"}:
            raise ValueError(f"invalid override for {script_path}")
        if not isinstance(override.get("reason"), str) or not override["reason"]:
            raise ValueError(f"override reason required for {script_path}")

    approved = frozenset(payload.get("approved_unclassified", []))
    for script_path in approved:
        validate_script_path(script_path)
    return LifecyclePolicy(production, tuple(prefix_categories), overrides, approved)


def validate_script_path(raw_path: str) -> str:
    if not isinstance(raw_path, str):
        raise ValueError(f"tracked script path escapes scripts/: {raw_path}")
    path = PurePosixPath(raw_path)
    if (
        path.is_absolute()
        or path.parts[:1] != ("scripts",)
        or len(path.parts) < 2
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"tracked script path escapes scripts/: {raw_path}")
    return path.as_posix()


def tracked_script_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--", "scripts/"],
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(validate_script_path(line) for line in result.stdout.splitlines() if line)


def classify(script_path: str, policy: LifecyclePolicy) -> dict[str, Any]:
    path = validate_script_path(script_path)
    filename = PurePosixPath(path).name
    if path in policy.overrides:
        override = policy.overrides[path]
        category = override["category"]
        return classification(category, False, f"override: {path}", override["reason"])
    if path in policy.production_entrypoints:
        return classification(
            "production_entrypoint",
            True,
            f"exact production allowlist: {path}",
            "明確列入 production entrypoint allowlist。",
        )
    for category, prefixes in policy.prefix_categories:
        matched = next((prefix for prefix in prefixes if filename.startswith(prefix)), None)
        if matched:
            return classification(
                category,
                False,
                f"prefix rule: {category}:{matched}",
                f"檔名符合 {category} 分類前綴 {matched}。",
            )
    return classification(
        "unclassified",
        False,
        "no exact allowlist, override, or prefix rule matched",
        "尚無足夠證據判定生命週期；需要人工 review。",
    )


def classification(category: str, entrypoint: bool, evidence: str, reason: str) -> dict[str, Any]:
    return {
        "category": category,
        "entrypoint": entrypoint,
        "reference_evidence": evidence,
        "reason": reason,
        "candidate_action": "retain" if category in {"production_entrypoint", "maintenance"} else "review",
    }


def build_inventory(policy: LifecyclePolicy, paths: Iterable[str]) -> dict[str, Any]:
    entries = []
    for raw_path in sorted(paths):
        path = validate_script_path(raw_path)
        entries.append({"path": path, **classify(path, policy)})
    unclassified = sorted(entry["path"] for entry in entries if entry["category"] == "unclassified")
    new_unclassified = sorted(set(unclassified) - policy.approved_unclassified)
    return {
        "schema_version": "script-lifecycle.v1",
        "source": "git-tracked-scripts",
        "entries": entries,
        "summary": {
            "tracked_script_count": len(entries),
            "category_counts": dict(sorted(Counter(entry["category"] for entry in entries).items())),
            "review_candidates": [
                entry["path"] for entry in entries if entry["candidate_action"] == "review"
            ],
        },
        "strict_new": {
            "approved_unclassified": sorted(policy.approved_unclassified),
            "new_unclassified": new_unclassified,
            "passed": not new_unclassified,
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立唯讀 tracked scripts 生命週期清冊。")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Git repository root")
    parser.add_argument("--policy", type=Path, default=POLICY_PATH, help="YAML policy 路徑")
    parser.add_argument("--output", type=Path, default=None, help="寫出 JSON 清冊的路徑")
    parser.add_argument("--strict-new", action="store_true", help="新 unclassified script 存在時回傳失敗")
    parser.add_argument("--json", action="store_true", help="輸出完整 JSON")
    return parser.parse_args(argv)


def render_summary(inventory: dict[str, Any]) -> str:
    counts = inventory["summary"]["category_counts"]
    count_text = ", ".join(f"{category}={count}" for category, count in counts.items())
    review_candidates = inventory["summary"]["review_candidates"][:20]
    lines = [
        f"tracked scripts: {inventory['summary']['tracked_script_count']}",
        f"category counts: {count_text}",
        f"review candidates (first {len(review_candidates)}): " + ", ".join(review_candidates),
        "strict-new: " + ("PASS" if inventory["strict_new"]["passed"] else "FAIL"),
    ]
    if inventory["strict_new"]["new_unclassified"]:
        lines.append("new unclassified: " + ", ".join(inventory["strict_new"]["new_unclassified"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    policy = load_policy(resolve_path(args.policy))
    inventory = build_inventory(policy, tracked_script_paths(resolve_path(args.root)))
    if args.output is not None:
        output = resolve_path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(inventory, ensure_ascii=False, indent=2) if args.json else render_summary(inventory))
    return 1 if args.strict_new and not inventory["strict_new"]["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

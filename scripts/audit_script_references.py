#!/usr/bin/env python3
"""盤點 tracked scripts 在程式、設定與文件中的靜態引用。"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "config" / "script_lifecycle.yaml"
SCRIPT_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_.\-/])(scripts/[A-Za-z0-9_.\-/]+)(?=$|[^A-Za-z0-9_.\-/])"
)


@dataclass(frozen=True)
class ReferencePolicy:
    protected_paths: frozenset[str]
    approved_unreferenced: frozenset[str]


def resolve_path(path: Path, root: Path = PROJECT_ROOT) -> Path:
    return path if path.is_absolute() else root / path


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


def load_policy(path: Path = POLICY_PATH) -> ReferencePolicy:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "script-lifecycle-policy.v1":
        raise ValueError("unsupported script lifecycle policy")
    production = frozenset(validate_script_path(item) for item in payload.get("production_entrypoints", []))
    reference_audit = payload.get("reference_audit", {})
    if not isinstance(reference_audit, dict):
        raise ValueError("reference_audit must be a mapping")
    approved = frozenset(
        validate_script_path(item) for item in reference_audit.get("approved_unreferenced", [])
    )
    return ReferencePolicy(protected_paths=production, approved_unreferenced=approved)


def tracked_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return sorted(item.decode("utf-8") for item in result.stdout.split(b"\0") if item)


def tracked_script_paths(root: Path) -> list[str]:
    return [path for path in tracked_paths(root) if path.startswith("scripts/")]


def load_tracked_text(root: Path, excluded_paths: frozenset[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in tracked_paths(root):
        if path in excluded_paths:
            continue
        try:
            content = (root / path).read_bytes()
            if b"\0" not in content:
                texts[path] = content.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return texts


def module_to_script(module: str, known_scripts: frozenset[str]) -> str | None:
    if not module.startswith("scripts."):
        return None
    candidate = f"scripts/{module.removeprefix('scripts.').replace('.', '/')}.py"
    return candidate if candidate in known_scripts else None


def reference(source: str, target: str, kind: str, line: int) -> dict[str, Any]:
    return {"source": source, "target": target, "kind": kind, "line": line}


def extract_references(
    source: str, text: str, known_scripts: frozenset[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    references: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for match in SCRIPT_PATH_RE.finditer(text):
        target = match.group(1)
        if target in known_scripts and target != source:
            line = text.count("\n", 0, match.start()) + 1
            references.append(reference(source, target, "path", line))
    if not source.endswith(".py"):
        return references, unknown
    try:
        tree = ast.parse(text, filename=source)
    except SyntaxError:
        return references, unknown
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = module_to_script(alias.name, known_scripts)
                if target and target != source:
                    references.append(reference(source, target, "python_import", node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.module:
            target = module_to_script(node.module, known_scripts)
            if target and target != source:
                references.append(reference(source, target, "python_import", node.lineno))
            if node.module == "scripts":
                for alias in node.names:
                    target = module_to_script(f"scripts.{alias.name}", known_scripts)
                    if target and target != source:
                        references.append(reference(source, target, "python_import", node.lineno))
        elif isinstance(node, ast.Call):
            function_name = None
            if isinstance(node.func, ast.Name):
                function_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                function_name = node.func.attr
            if function_name not in {"import_module", "__import__"} or not node.args:
                continue
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                target = module_to_script(first_arg.value, known_scripts)
                if target and target != source:
                    references.append(reference(source, target, "python_dynamic_literal", node.lineno))
            else:
                unknown.append(
                    {
                        "source": source,
                        "kind": "python_dynamic_import",
                        "line": node.lineno,
                        "reason": "dynamic Python import target cannot be resolved statically",
                    }
                )
    return references, unknown


def collect_references(
    texts: Mapping[str, str],
    script_paths: Iterable[str],
    excluded_source_targets: Mapping[str, frozenset[str]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    known_scripts = frozenset(validate_script_path(path) for path in script_paths)
    exclusions = excluded_source_targets or {}
    references: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for source in sorted(texts):
        found, unresolved = extract_references(source, texts[source], known_scripts)
        references.extend(item for item in found if item["target"] not in exclusions.get(source, frozenset()))
        unknown.extend(unresolved)
    key = lambda item: (item["source"], item.get("target", ""), item["kind"], item["line"])
    return sorted(references, key=key), sorted(unknown, key=key)


def build_inventory(
    policy: ReferencePolicy,
    script_paths: Iterable[str],
    references: Iterable[dict[str, Any]],
    unknown_references: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    paths = sorted(validate_script_path(path) for path in script_paths)
    unknown = sorted(
        unknown_references,
        key=lambda item: (item["source"], item.get("target", ""), item["kind"], item["line"]),
    )
    by_target: dict[str, list[dict[str, Any]]] = {path: [] for path in paths}
    for item in references:
        if item["target"] in by_target:
            by_target[item["target"]].append(item)
    entries: list[dict[str, Any]] = []
    for path in paths:
        evidence = sorted(by_target[path], key=lambda item: (item["source"], item["kind"], item["line"]))
        if path in policy.protected_paths:
            status = "protected"
            reason = "正式 production entrypoint allowlist；即使靜態引用為 0 也不得視為可刪。"
        elif evidence:
            status = "referenced"
            reason = "找到 tracked 靜態引用。"
        else:
            status = "suspected_orphan"
            reason = (
                "既有無引用基線 allowlist；僅代表需保留／review，不代表可刪。"
                if path in policy.approved_unreferenced
                else "未找到 tracked 靜態引用；dynamic 或外部排程仍可能存在，僅供人工 review。"
            )
        entries.append(
            {
                "path": path,
                "status": status,
                "reason": reason,
                "baseline_approved": path in policy.approved_unreferenced,
                "reference_count": len(evidence),
                "references": evidence,
            }
        )
    suspected = [entry["path"] for entry in entries if entry["status"] == "suspected_orphan"]
    new_suspected = sorted(set(suspected) - policy.approved_unreferenced)
    return {
        "schema_version": "script-reference-audit.v1",
        "source": "git-tracked-text-files",
        "entries": entries,
        "unknown_references": unknown,
        "summary": {
            "tracked_script_count": len(entries),
            "status_counts": dict(sorted(Counter(entry["status"] for entry in entries).items())),
            "unknown_reference_count": len(unknown),
            "suspected_orphans": suspected,
            "protected_paths": [entry["path"] for entry in entries if entry["status"] == "protected"],
        },
        "strict_new": {
            "approved_unreferenced": sorted(policy.approved_unreferenced),
            "new_suspected_orphans": new_suspected,
            "passed": not new_suspected,
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="盤點 tracked scripts 的靜態引用。")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Git repository root")
    parser.add_argument("--policy", type=Path, default=None, help="YAML policy 路徑")
    parser.add_argument("--output", type=Path, default=None, help="寫出 JSON 報告的路徑")
    parser.add_argument("--strict-new", action="store_true", help="新無引用 script 存在時回傳失敗")
    parser.add_argument("--json", action="store_true", help="輸出完整 JSON")
    return parser.parse_args(argv)


def render_summary(inventory: dict[str, Any]) -> str:
    counts = inventory["summary"]["status_counts"]
    count_text = ", ".join(f"{status}={count}" for status, count in counts.items())
    candidates = inventory["summary"]["suspected_orphans"][:20]
    return "\n".join(
        [
            f"tracked scripts: {inventory['summary']['tracked_script_count']}",
            f"status counts: {count_text}",
            f"unknown dynamic references: {inventory['summary']['unknown_reference_count']}",
            f"suspected orphans (first {len(candidates)}): " + ", ".join(candidates),
            "strict-new: " + ("PASS" if inventory["strict_new"]["passed"] else "FAIL"),
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = resolve_path(args.root)
    policy_path = resolve_path(args.policy, root) if args.policy is not None else root / "config" / "script_lifecycle.yaml"
    policy = load_policy(policy_path)
    output = resolve_path(args.output, root) if args.output is not None else None
    excluded = frozenset(
        [output.relative_to(root).as_posix()]
        if output is not None and output.is_relative_to(root)
        else []
    )
    scripts = tracked_script_paths(root)
    policy_source = policy_path.relative_to(root).as_posix() if policy_path.is_relative_to(root) else None
    exclusions = {policy_source: policy.approved_unreferenced} if policy_source else {}
    references, unknown = collect_references(load_tracked_text(root, excluded), scripts, exclusions)
    inventory = build_inventory(policy, scripts, references, unknown)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(inventory, ensure_ascii=False, indent=2) if args.json else render_summary(inventory))
    return 1 if args.strict_new and not inventory["strict_new"]["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

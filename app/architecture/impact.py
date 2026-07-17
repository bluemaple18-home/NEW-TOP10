"""以 Git 變更與 canonical control plane 推導增量驗證範圍。"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from collections import defaultdict, deque
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from app.architecture.control_plane import build_architecture_manifest


IMPACT_PLAN_SCHEMA_VERSION = "top10.incremental-verification-plan.v1"
GENERATED_EVIDENCE_SCHEMAS = frozenset(
    {
        "top10.architecture-manifest.v1",
        IMPACT_PLAN_SCHEMA_VERSION,
        "script-lifecycle.v1",
        "script-reference-audit.v1",
        "top10.script-governance.v1",
        "top10.daily-v2.parity-report.v1",
        "top10.daily-v2.promotion-decision.v1",
    }
)
PATH_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9_.\-/])((?:app|scripts|config|tests|docs)/[A-Za-z0-9_.\-/]+)"
)


class ImpactPlanError(ValueError):
    """增量影響計畫不符合 deterministic 契約。"""


def _git(repo_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise ImpactPlanError(completed.stderr.decode("utf-8", errors="replace").strip())
    return completed.stdout


def _git_sha(repo_root: Path) -> str:
    return _git(repo_root, "rev-parse", "HEAD").decode("utf-8").strip()


def _tracked_paths(repo_root: Path) -> list[str]:
    return sorted(part.decode("utf-8") for part in _git(repo_root, "ls-files", "-z").split(b"\0") if part)


def _normalize_changed_files(changed_files: Iterable[str], *, allow_empty: bool = False) -> list[str]:
    normalized: set[str] = set()
    for raw in changed_files:
        if not isinstance(raw, str):
            raise ImpactPlanError("changed file 必須是 repo-relative string")
        path = PurePosixPath(raw)
        if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
            raise ImpactPlanError(f"changed file 必須是安全的 repo-relative path：{raw}")
        normalized.add(path.as_posix())
    if not normalized and not allow_empty:
        raise ImpactPlanError("至少需要一個 changed file")
    return sorted(normalized)


def changed_files_from_git(repo_root: Path, base: str, head: str = "HEAD") -> list[str]:
    """讀取兩個 Git revision 間的檔案變更，不讀 working-tree mutation。"""

    output = _git(repo_root, "diff", "--name-only", "-z", base, head, "--")
    return _normalize_changed_files(
        (part.decode("utf-8") for part in output.split(b"\0") if part),
        allow_empty=True,
    )


def _module_name(path: str) -> str | None:
    if not path.endswith(".py"):
        return None
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) if parts else None


def _resolve_import(module: str, modules: Mapping[str, str]) -> str | None:
    candidate = module
    while candidate:
        if candidate in modules:
            return modules[candidate]
        candidate = candidate.rpartition(".")[0]
    return None


def _relative_module(source_module: str, source_path: str, level: int, module: str | None) -> str:
    parts = source_module.split(".")
    if not source_path.endswith("/__init__.py"):
        parts = parts[:-1]
    ascend = max(level - 1, 0)
    if ascend:
        parts = parts[:-ascend] if ascend < len(parts) else []
    if module:
        parts.extend(module.split("."))
    return ".".join(parts)


def _edge(source: str, target: str, kind: str, line: int) -> dict[str, Any]:
    return {"source": source, "target": target, "kind": kind, "line": line}


def _is_generated_evidence(path: str, text: str) -> bool:
    if not path.endswith(".json") or '"schema_version"' not in text:
        return False
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and payload.get("schema_version") in GENERATED_EVIDENCE_SCHEMAS


def _python_edges(
    source: str,
    text: str,
    modules: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_module = _module_name(source)
    if source_module is None:
        return [], []
    try:
        tree = ast.parse(text, filename=source)
    except SyntaxError as exc:
        return [], [{"source": source, "kind": "syntax_error", "line": exc.lineno or 0, "reason": str(exc)}]

    edges: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = _resolve_import(alias.name, modules)
                if target and target != source:
                    edges.append(_edge(source, target, "python_import", node.lineno))
        elif isinstance(node, ast.ImportFrom):
            module = (
                _relative_module(source_module, source, node.level, node.module)
                if node.level
                else node.module or ""
            )
            candidates = [module]
            candidates.extend(f"{module}.{alias.name}" for alias in node.names if alias.name != "*")
            for candidate in candidates:
                target = _resolve_import(candidate, modules)
                if target and target != source:
                    edges.append(_edge(source, target, "python_import", node.lineno))
        elif isinstance(node, ast.Call):
            function_name = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else None
            )
            if function_name not in {"import_module", "__import__"} or not node.args:
                continue
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                target = _resolve_import(argument.value, modules)
                if target and target != source:
                    edges.append(_edge(source, target, "python_dynamic_literal", node.lineno))
            else:
                unknown.append(
                    {
                        "source": source,
                        "kind": "python_dynamic_import",
                        "line": node.lineno,
                        "reason": "dynamic import target cannot be resolved statically",
                    }
                )
    return edges, unknown


def _dependency_graph(repo_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tracked = _tracked_paths(repo_root)
    tracked_set = frozenset(tracked)
    modules = {module: path for path in tracked if (module := _module_name(path))}
    edges: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for source in tracked:
        path = repo_root / source
        try:
            content = path.read_bytes()
            if b"\0" in content:
                continue
            text = content.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _is_generated_evidence(source, text):
            continue
        python_edges, python_unknown = _python_edges(source, text, modules)
        edges.extend(python_edges)
        unknown.extend(python_unknown)
        for match in PATH_REFERENCE_RE.finditer(text):
            target = match.group(1)
            if target in tracked_set and target != source:
                line = text.count("\n", 0, match.start()) + 1
                edges.append(_edge(source, target, "tracked_path_reference", line))
    edge_key = lambda item: (item["source"], item["target"], item["kind"], item["line"])
    unknown_key = lambda item: (item["source"], item["kind"], item["line"])
    return sorted({tuple(edge_key(item)): item for item in edges}.values(), key=edge_key), sorted(unknown, key=unknown_key)


def _reverse_impact(changed: Iterable[str], edges: Iterable[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    reverse: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        reverse[edge["target"]].append(edge)
    seen = set(changed)
    queue = deque(sorted(seen))
    evidence: list[dict[str, Any]] = []
    while queue:
        target = queue.popleft()
        for edge in reverse.get(target, []):
            evidence.append(edge)
            if edge["source"] not in seen:
                seen.add(edge["source"])
                queue.append(edge["source"])
    edge_key = lambda item: (item["source"], item["target"], item["kind"], item["line"])
    return sorted(seen), sorted({tuple(edge_key(item)): item for item in evidence}.values(), key=edge_key)


def _path_in_root(path: str, root: str) -> bool:
    normalized = root.rstrip("/")
    return path == normalized or path.startswith(f"{normalized}/")


def _manifest_digest(manifest: dict[str, Any]) -> str:
    stable_manifest = json.loads(json.dumps(manifest, ensure_ascii=False))
    stable_manifest["source"].pop("git_sha", None)
    return hashlib.sha256(
        json.dumps(stable_manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _require_source_ancestor(repo_root: Path, source_sha: str) -> None:
    if not source_sha:
        raise ImpactPlanError("impact plan 缺少 source Git SHA")
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or completed.stdout.strip() != source_sha:
        raise ImpactPlanError(f"impact plan source Git SHA 必須等於目前 HEAD：{source_sha}")


def _source_tree_digest(repo_root: Path) -> str:
    """綁定實際 tracked working tree，避免 dirty content 冒充 HEAD tree。"""

    completed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=repo_root, check=True, capture_output=True
    )
    digest = hashlib.sha256()
    for raw_path in sorted(item for item in completed.stdout.split(b"\0") if item):
        path_text = raw_path.decode("utf-8")
        path = repo_root / path_text
        if path.is_file() and path.suffix == ".json":
            try:
                if _is_generated_evidence(path_text, path.read_text(encoding="utf-8")):
                    continue
            except (OSError, UnicodeDecodeError):
                pass
        digest.update(path_text.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest() if path.is_file() else b"MISSING")
    return digest.hexdigest()


def build_incremental_verification_plan(
    repo_root: Path,
    *,
    changed_files: Iterable[str],
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """建立 changed files 的 reverse-impact 與 required verification plan。"""

    repo_root = repo_root.resolve()
    changed = _normalize_changed_files(changed_files, allow_empty=True)
    architecture_manifest = build_architecture_manifest(repo_root)
    control_plane = architecture_manifest["control_plane"]
    edges, unknown_edges = _dependency_graph(repo_root)
    impacted_files, impact_evidence = _reverse_impact(changed, edges)
    impacted_set = set(impacted_files)

    domains = {
        domain_id
        for domain_id, spec in control_plane["domains"].items()
        if any(_path_in_root(path, root) for path in impacted_files for root in spec["paths"])
    }
    entrypoints = {
        path for path in control_plane["entrypoints"] if path in impacted_set
    }
    workflows: set[str] = set()
    required_verification: set[str] = set()
    for domain_id in domains:
        required_verification.update(control_plane["domains"][domain_id].get("required_verification", []))
    for path in entrypoints:
        spec = control_plane["entrypoints"][path]
        workflows.update(spec["workflows"])
        required_verification.update(spec["required_verification"])
    for workflow_id, spec in control_plane["workflows"].items():
        if spec["owner_domain"] in domains or impacted_set.intersection(spec["entrypoints"]):
            workflows.add(workflow_id)
            required_verification.update(spec["required_verification"])
    for verification_id, spec in control_plane["verification"].items():
        if impacted_set.intersection(spec.get("paths", [])):
            required_verification.add(verification_id)

    artifacts = sorted(
        artifact_id
        for artifact_id, spec in control_plane["artifacts"].items()
        if any(ref.split(".", 1)[0] in workflows for ref in spec["producers"])
        or bool(set(spec["consumers"]) & workflows)
    )
    production_workflows = {
        workflow_id for workflow_id in workflows if control_plane["workflows"][workflow_id].get("production")
    }
    production_touched = bool(entrypoints or production_workflows)
    docs_only = all(path.startswith("docs/") for path in changed)
    unknown_fail_closed = bool(unknown_edges and not docs_only)
    if unknown_fail_closed:
        production_touched = True
        production_workflows.update(
            workflow_id
            for workflow_id, spec in control_plane["workflows"].items()
            if spec.get("production")
        )
        workflows.update(production_workflows)
        for workflow_id in production_workflows:
            required_verification.update(control_plane["workflows"][workflow_id]["required_verification"])
        required_verification.update(
            verification_id
            for verification_id in ("scheduler_ownership", "publish_guard")
            if verification_id in control_plane["verification"]
        )
    risk_level = "none" if not changed else "critical" if production_touched else "low" if docs_only else "standard"
    missing_production_verification = production_touched and not required_verification
    if missing_production_verification:
        raise ImpactPlanError("production impact 無 required verification mapping，必須 fail closed")

    normalized_request = request or {"mode": "files", "changed_files": changed}
    return {
        "schema_version": IMPACT_PLAN_SCHEMA_VERSION,
        "source": {
            "git_sha": _git_sha(repo_root),
            "tree_mode": "tracked_working_tree",
            "tracked_tree_digest": _source_tree_digest(repo_root),
            "architecture_manifest_digest": _manifest_digest(architecture_manifest),
        },
        "request": normalized_request,
        "changed_files": changed,
        "impact": {
            "files": impacted_files,
            "domains": sorted(domains),
            "entrypoints": sorted(entrypoints),
            "workflows": sorted(workflows),
            "artifacts": artifacts,
            "evidence": impact_evidence,
        },
        "required_verification": sorted(required_verification),
        "verification_commands": {
            verification_id: control_plane["verification"][verification_id]["command"]
            for verification_id in sorted(required_verification)
        },
        "unknown_edges": unknown_edges,
        "risk": {
            "level": risk_level,
            "production_touched": production_touched,
            "missing_production_verification": missing_production_verification,
            "needs_review": bool(unknown_edges and not docs_only),
            "unknown_edges_fail_closed": unknown_fail_closed,
        },
    }


def verify_incremental_verification_plan(plan: dict[str, Any], repo_root: Path) -> None:
    """依 plan request 重算完整輸出，拒絕手動刪除 gate 或 impact。"""

    if plan.get("schema_version") != IMPACT_PLAN_SCHEMA_VERSION:
        raise ImpactPlanError("不支援的 incremental verification plan schema")
    source_sha = str((plan.get("source") or {}).get("git_sha", ""))
    _require_source_ancestor(repo_root.resolve(), source_sha)
    request = plan.get("request")
    if not isinstance(request, dict):
        raise ImpactPlanError("impact plan 缺少 request")
    mode = request.get("mode")
    if mode == "files":
        changed = request.get("changed_files", [])
    elif mode == "git_diff":
        changed = changed_files_from_git(repo_root, str(request.get("base")), str(request.get("head", "HEAD")))
    else:
        raise ImpactPlanError(f"不支援的 impact request mode：{mode}")
    expected = build_incremental_verification_plan(repo_root, changed_files=changed, request=request)
    expected["source"]["git_sha"] = source_sha
    if plan != expected:
        raise ImpactPlanError("incremental verification plan 與 repo source 不一致")

"""合併 lifecycle、靜態引用與 control plane 的 script governance 清冊。"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from typing import Any, Iterable, Mapping


SCRIPT_GOVERNANCE_SCHEMA_VERSION = "top10.script-governance.v1"
CATEGORY_OWNERS = {
    "maintenance": "architecture.operations",
    "research": "research",
    "builder": "artifact.builders",
    "verifier": "verification",
    "legacy_candidate": "architecture.review",
    "unclassified": None,
}


class ScriptGovernanceError(ValueError):
    """輸入或 governance 報告違反契約。"""


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ScriptGovernanceError(f"缺少 mapping：{key}")
    return value


def _reachable_roots(
    roots: Iterable[str], references: Iterable[Mapping[str, Any]]
) -> dict[str, list[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for item in references:
        source = item.get("source")
        target = item.get("target")
        if isinstance(source, str) and isinstance(target, str) and source.startswith("scripts/"):
            graph[source].add(target)
    reached_by: dict[str, set[str]] = defaultdict(set)
    for root in sorted(set(roots)):
        queue = deque([root])
        visited: set[str] = set()
        while queue:
            path = queue.popleft()
            if path in visited:
                continue
            visited.add(path)
            reached_by[path].add(root)
            queue.extend(sorted(graph.get(path, set()) - visited))
    return {path: sorted(items) for path, items in reached_by.items()}


def _artifact_contracts(control_plane: Mapping[str, Any], workflows: set[str]) -> list[str]:
    matched = []
    for artifact_id, artifact in _mapping(control_plane, "artifacts").items():
        producers = artifact.get("producers") or []
        consumers = artifact.get("consumers") or []
        producer_workflows = {str(value).split(".", 1)[0] for value in producers}
        if workflows.intersection(producer_workflows | set(map(str, consumers))):
            matched.append(str(artifact_id))
    return sorted(matched)


def build_script_governance(
    lifecycle: Mapping[str, Any],
    references: Mapping[str, Any],
    architecture_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """產生每支 tracked script 的 owner、reachability 與契約。"""

    if lifecycle.get("schema_version") != "script-lifecycle.v1":
        raise ScriptGovernanceError("lifecycle schema 不支援")
    if references.get("schema_version") != "script-reference-audit.v1":
        raise ScriptGovernanceError("reference audit schema 不支援")
    if architecture_manifest.get("schema_version") != "top10.architecture-manifest.v1":
        raise ScriptGovernanceError("architecture manifest schema 不支援")

    control_plane = _mapping(architecture_manifest, "control_plane")
    entrypoints = _mapping(control_plane, "entrypoints")
    workflows = _mapping(control_plane, "workflows")
    domains = _mapping(control_plane, "domains")
    verifications = _mapping(control_plane, "verification")
    lifecycle_by_path = {item["path"]: item for item in lifecycle.get("entries") or []}
    reference_by_path = {item["path"]: item for item in references.get("entries") or []}
    if set(lifecycle_by_path) != set(reference_by_path):
        raise ScriptGovernanceError("lifecycle 與 reference audit tracked paths 不一致")

    roots = sorted(path for path in entrypoints if str(path).startswith("scripts/"))
    flattened_references = [
        reference
        for entry in references.get("entries") or []
        for reference in entry.get("references") or []
    ]
    reached_by = _reachable_roots(roots, flattened_references)
    entries: list[dict[str, Any]] = []
    production_gaps: list[dict[str, Any]] = []

    for path in sorted(lifecycle_by_path):
        lifecycle_entry = lifecycle_by_path[path]
        root_paths = reached_by.get(path, [])
        root_records = [entrypoints[root] for root in root_paths]
        root_workflows = {str(item) for record in root_records for item in record.get("workflows") or []}
        domain_ids = {str(record.get("domain")) for record in root_records if record.get("domain")}
        owners = sorted(
            {
                str(domains[domain_id].get("owner"))
                for domain_id in domain_ids
                if domain_id in domains and domains[domain_id].get("owner")
            }
        )
        verification_ids = {
            str(item)
            for record in root_records
            for item in record.get("required_verification") or []
        }
        for workflow_id in root_workflows:
            if workflow_id in workflows:
                verification_ids.update(map(str, workflows[workflow_id].get("required_verification") or []))
        production_reachable = bool(root_paths)
        if production_reachable:
            owner_contract = {"status": "bound", "owners": owners, "domains": sorted(domain_ids)}
            artifact_contracts = _artifact_contracts(control_plane, root_workflows)
            artifact_contract = {"status": "bound", "artifacts": artifact_contracts}
            verification_contract = {
                "status": "bound",
                "ids": sorted(verification_ids),
                "paths": sorted(
                    {
                        str(test_path)
                        for verification_id in verification_ids
                        if verification_id in verifications
                        for test_path in verifications[verification_id].get("paths") or []
                    }
                ),
            }
            missing = []
            if not owners:
                missing.append("owner")
            if not verification_ids:
                missing.append("verification")
            if not artifact_contracts:
                missing.append("artifact_contract")
            if missing:
                production_gaps.append({"path": path, "missing": missing})
        else:
            fallback_owner = CATEGORY_OWNERS.get(str(lifecycle_entry.get("category")))
            owner_contract = {
                "status": "lifecycle-owned" if fallback_owner else "review_required",
                "owners": [fallback_owner] if fallback_owner else [],
                "domains": [],
            }
            artifact_contract = {
                "status": "not_applicable_until_production_promotion",
                "artifacts": [],
            }
            verification_contract = {
                "status": "lifecycle_gate",
                "ids": ["script_governance_contract"],
                "paths": ["tests/test_script_governance.py"],
            }

        entries.append(
            {
                "path": path,
                "category": lifecycle_entry.get("category"),
                "candidate_action": "retain" if production_reachable else lifecycle_entry.get("candidate_action"),
                "reference_status": reference_by_path[path].get("status"),
                "production_reachability": {
                    "reachable": production_reachable,
                    "roots": root_paths,
                    "workflows": sorted(root_workflows),
                },
                "owner_contract": owner_contract,
                "artifact_contract": artifact_contract,
                "verification_contract": verification_contract,
            }
        )

    unclassified = sorted(item["path"] for item in entries if item["category"] == "unclassified")
    return {
        "schema_version": SCRIPT_GOVERNANCE_SCHEMA_VERSION,
        "entries": entries,
        "unknown_references": references.get("unknown_references") or [],
        "summary": {
            "tracked_script_count": len(entries),
            "production_reachable_count": sum(item["production_reachability"]["reachable"] for item in entries),
            "category_counts": dict(sorted(Counter(str(item["category"]) for item in entries).items())),
            "unclassified": unclassified,
            "production_contract_gaps": production_gaps,
        },
        "strict": {
            "passed": not unclassified and not production_gaps,
            "requirements": [
                "all_tracked_scripts_classified",
                "production_reachable_owner_bound",
                "production_reachable_artifact_contract_bound",
                "production_reachable_verification_bound",
            ],
        },
    }


def verify_script_governance(
    report: Mapping[str, Any],
    lifecycle: Mapping[str, Any],
    references: Mapping[str, Any],
    architecture_manifest: Mapping[str, Any],
) -> None:
    if report != build_script_governance(lifecycle, references, architecture_manifest):
        raise ScriptGovernanceError("script governance 與來源重算結果不一致")

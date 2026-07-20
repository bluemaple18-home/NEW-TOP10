from __future__ import annotations

from scripts.build_tskg_research_adoption_inventory import build_inventory


def _component(
    ledger_id: str,
    *,
    family: str,
    lifecycle: str,
    evidence: list[str] | None = None,
) -> dict[str, object]:
    return {
        "ledger_id": ledger_id,
        "component_family": family,
        "component_id": ledger_id.split(":", 1)[1],
        "lifecycle_status": lifecycle,
        "evidence": evidence or [],
        "promotion_ready": False,
        "changes_production_ranking": lifecycle == "production",
    }


def test_inventory_classifies_without_rerunning_research() -> None:
    ledger = {
        "schema_version": "research-component-ledger.v1",
        "components": [
            _component("research:rejected", family="research_registry", lifecycle="rejected"),
            _component("research:reference", family="research_registry", lifecycle="reference"),
            _component("research:active", family="research_registry", lifecycle="shadow"),
            _component("runtime:baseline", family="runtime_contract", lifecycle="production"),
        ],
    }

    payload = build_inventory(ledger, as_of="2026-07-20")
    rows = {row["research_id"]: row for row in payload["items"]}

    assert rows["research:rejected"]["adoption_class"] == "GRANDFATHERED"
    assert rows["research:reference"]["adoption_class"] == "CHECK_ON_REUSE"
    assert rows["research:active"]["adoption_class"] == "REQUIRED_NOW"
    assert rows["runtime:baseline"]["adoption_class"] == "CHECK_ON_REUSE"
    assert payload["contract"]["reruns_research"] is False
    assert payload["summary"]["item_count"] == 4


def test_inventory_is_stably_sorted_and_marks_unknown_lifecycle() -> None:
    ledger = {
        "schema_version": "research-component-ledger.v1",
        "components": [
            _component("research:zeta", family="research_registry", lifecycle="mystery"),
            _component("research:alpha", family="research_registry", lifecycle="diagnostic"),
        ],
    }

    first = build_inventory(ledger, as_of="2026-07-20")
    second = build_inventory(ledger, as_of="2026-07-20")

    assert first == second
    assert [row["research_id"] for row in first["items"]] == [
        "research:alpha",
        "research:zeta",
    ]
    assert first["items"][1]["adoption_class"] == "UNKNOWN"
    assert first["items"][1]["next_action"] == "MANUAL_REVIEW"


def test_inventory_reuses_component_adoption_metadata_when_present() -> None:
    component = _component(
        "research:explicit",
        family="research_registry",
        lifecycle="shadow",
        evidence=["docs/evidence/explicit.json"],
    )
    component["tskg_adoption"] = {
        "schema_version": "research-evidence-tskg-adoption.v1",
        "adoption_mode": "CHECK_ON_REUSE",
        "usage_intent": "REUSE",
        "decision": "BLOCKED",
        "hard_block": True,
    }

    payload = build_inventory(
        {"schema_version": "research-component-ledger.v1", "components": [component]},
        as_of="2026-07-20",
    )

    assert payload["items"][0]["adoption_class"] == "CHECK_ON_REUSE"
    assert payload["items"][0]["checkpoint_decision"] == "BLOCKED"
    assert payload["items"][0]["reuse_intent"] == "REUSE"
    assert payload["items"][0]["promotion_or_model_path"] is True

"""TSKG 離線 identity-to-company 垂直切片。"""

from app.tskg.flow_observation import (
    FlowObservationContractError,
    SecurityFlowObservationFixture,
)
from app.tskg.flow_read_model import (
    build_security_flow_read_model,
    query_security_flow_read_model,
)
from app.tskg.identity import IdentityResolver, ResolutionResult, ResolutionStatus
from app.tskg.flow_observation import (
    FlowObservationContractError,
    SecurityFlowObservationFixture,
)
from app.tskg.repository import FixtureRepository
from app.tskg.router import create_tskg_router
from app.tskg.service import CompanyService
from app.tskg.source_policy import (
    SourcePolicyContractError,
    SourcePolicyRegistry,
    preflight_source,
)
from app.tskg.twse_t86 import (
    T86SnapshotContractError,
    build_t86_snapshot,
    fetch_t86_snapshot,
    load_t86_snapshot,
    market_aggregate,
    write_t86_snapshot,
)

__all__ = [
    "CompanyService",
    "FlowObservationContractError",
    "FixtureRepository",
    "IdentityResolver",
    "ResolutionResult",
    "ResolutionStatus",
    "SecurityFlowObservationFixture",
    "SourcePolicyContractError",
    "SourcePolicyRegistry",
    "T86SnapshotContractError",
    "build_security_flow_read_model",
    "build_t86_snapshot",
    "create_tskg_router",
    "fetch_t86_snapshot",
    "load_t86_snapshot",
    "market_aggregate",
    "preflight_source",
    "query_security_flow_read_model",
    "write_t86_snapshot",
]

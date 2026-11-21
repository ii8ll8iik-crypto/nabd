"""Canonical Relate v2 graph schema: parcels/buildings, streets, env zones & agent memory."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .client import RelateClient

# Unique constraints in Relate automatically create backing indexes.
SCHEMA_CONSTRAINTS: List[str] = [
    "CREATE CONSTRAINT meta_slug_uniq IF NOT EXISTS FOR (m:Meta) REQUIRE m.slug IS UNIQUE",
    "CREATE CONSTRAINT junction_id_uniq IF NOT EXISTS FOR (j:Junction) REQUIRE j.id IS UNIQUE",
    "CREATE CONSTRAINT parcel_id_uniq IF NOT EXISTS FOR (p:Parcel) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT service_id_uniq IF NOT EXISTS FOR (s:Service) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT service_type_key_uniq IF NOT EXISTS FOR (t:ServiceType) REQUIRE t.key IS UNIQUE",
    "CREATE CONSTRAINT env_zone_id_uniq IF NOT EXISTS FOR (z:EnvZone) REQUIRE z.id IS UNIQUE",
    "CREATE CONSTRAINT agent_decision_id_uniq IF NOT EXISTS FOR (d:AgentDecision) REQUIRE d.id IS UNIQUE",
]

# Secondary indexes for fast filtered lookups across large cities (e.g., Manhattan / Irbid).
SCHEMA_INDEXES: List[str] = [
    "CREATE INDEX parcel_kind_idx IF NOT EXISTS FOR (p:Parcel) ON (p.kind)",
    "CREATE INDEX parcel_use_idx IF NOT EXISTS FOR (p:Parcel) ON (p.land_use)",
    "CREATE INDEX parcel_owner_idx IF NOT EXISTS FOR (p:Parcel) ON (p.ownership_status)",
    "CREATE INDEX service_cat_idx IF NOT EXISTS FOR (s:Service) ON (s.category)",
    "CREATE INDEX env_zone_type_idx IF NOT EXISTS FOR (z:EnvZone) ON (z.zone_type)",
    "CREATE INDEX decision_status_idx IF NOT EXISTS FOR (d:AgentDecision) ON (d.status)",
]


def apply_schema(client: "RelateClient") -> dict:
    """Idempotently apply all constraints and indexes to a Relate store."""
    applied_constraints = 0
    applied_indexes = 0
    for stmt in SCHEMA_CONSTRAINTS:
        try:
            client.query(stmt, tag="schema:constraint")
            applied_constraints += 1
        except RuntimeError as exc:
            if "AlreadyExists" not in str(exc):
                raise
    for stmt in SCHEMA_INDEXES:
        try:
            client.query(stmt, tag="schema:index")
            applied_indexes += 1
        except RuntimeError as exc:
            if "AlreadyExists" not in str(exc):
                raise
    return {
        "constraints_checked": len(SCHEMA_CONSTRAINTS),
        "constraints_applied": applied_constraints,
        "indexes_checked": len(SCHEMA_INDEXES),
        "indexes_applied": applied_indexes,
    }

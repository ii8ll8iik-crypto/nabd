"""Verification tests for Stage 2.1: API v2 & MCP v2 Relate Live Trace, Cypher & Agent Memory."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from fastapi import HTTPException
import pytest

from backend.api import server as api_srv
from backend.mcp import server as mcp_srv


def test_api_v2_relate_trace_cypher_and_agent_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    slug = "irbid-api-v2-test"
    shutil.copy2(Path("data/irbid-yarmouk.rl"), tmp_path / f"{slug}.rl")
    shutil.copy2(Path("data/irbid-yarmouk.build-receipt.json"), tmp_path / f"{slug}.build-receipt.json")
    monkeypatch.setattr(api_srv, "DATA_DIR", tmp_path)

    try:
        # 1. Relate store info exposes constraints, indexes & build receipt
        info_resp = api_srv.get_relate_info(slug)
        assert info_resp["slug"] == slug
        assert len(info_resp["store_info"]["constraints"]) >= 7
        assert len(info_resp["store_info"]["indexes"]) >= 13
        assert info_resp["build_receipt"] is not None

        # 2. Live traces are populated from engine boot
        traces_resp = api_srv.get_relate_traces(slug, limit=15)
        assert traces_resp["count"] >= 5

        # 3. Read-only Cypher works and blocks write clauses
        q_resp = api_srv.run_relate_cypher_api(
            slug, api_srv.RelateCypherRequest(cypher="MATCH (p:Parcel) RETURN count(p) AS n")
        )
        assert q_resp["row_count"] == 1
        assert q_resp["rows"][0]["n"] > 1000

        with pytest.raises(HTTPException) as exc_info:
            api_srv.run_relate_cypher_api(
                slug, api_srv.RelateCypherRequest(cypher="CREATE (:Forbidden {id: 'x'})")
            )
        assert exc_info.value.status_code == 400

        # 4. Persist AgentDecision with block_ownership=True & verify retrieval + ownership update
        eng = api_srv.get_engine(slug)
        sample_pid = eng.blocks[0]["id"]
        created = api_srv.create_agent_decision(
            slug,
            api_srv.AgentDecisionRequest(
                parcel_id=sample_pid,
                category="clinic",
                status="REJECTED",
                reason="Landlord declined commercial lease",
                actor="studio_test",
                metrics={"gain_J": 41.2},
                block_ownership=True,
            ),
        )
        assert created["tx_state"] == "COMMITTED"
        assert created["decision"]["status"] == "REJECTED"
        assert created["ownership_update"]["ownership_status"] == "BLOCKED_OWNERSHIP"

        listed = api_srv.get_agent_decisions(slug, limit=20)
        assert any(d["id"] == created["decision"]["id"] and d["parcel_id"] == sample_pid for d in listed["decisions"])

        # 5. Update parcel ownership directly via endpoint
        upd = api_srv.update_parcel_ownership(
            slug,
            sample_pid,
            api_srv.ParcelOwnershipRequest(ownership_status="commercial_lease_candidate", note="Cleared"),
        )
        assert upd["tx_state"] == "COMMITTED"
        assert upd["parcel"]["ownership_status"] == "commercial_lease_candidate"
    finally:
        eng = api_srv._ENGINE_CACHE.pop(slug, None)
        if eng is not None:
            eng.close()


def test_mcp_v2_agent_memory_ownership_and_live_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    slug = "irbid-mcp-v2-test"
    shutil.copy2(Path("data/irbid-yarmouk.rl"), tmp_path / f"{slug}.rl")
    monkeypatch.setattr(mcp_srv, "DATA_DIR", tmp_path)

    try:
        eng = mcp_srv._get_engine(slug)
        sample_pid = eng.blocks[1]["id"]

        # 1. Record agent decision + block ownership via MCP tool
        rec = json.loads(
            mcp_srv.record_agent_decision(
                area_slug=slug,
                parcel_id=sample_pid,
                category="cafe",
                status="WATCHLIST",
                reason="Wait for university semester peak",
                actor="claude_mcp",
                block_ownership=True,
            )
        )
        assert rec["tx_state"] == "COMMITTED"
        assert rec["decision"]["status"] == "WATCHLIST"
        assert rec["ownership_update"]["ownership_status"] == "BLOCKED_OWNERSHIP"

        # 2. Retrieve decision history filtered by parcel_id
        hist = json.loads(mcp_srv.get_site_decision_history(area_slug=slug, parcel_id=sample_pid))
        assert hist["count"] >= 1
        assert hist["decisions"][0]["reason"] == "Wait for university semester peak"

        # 3. Update ownership status via MCP tool
        own = json.loads(
            mcp_srv.set_parcel_ownership_status(
                area_slug=slug,
                parcel_id=sample_pid,
                ownership_status="mixed_lease_candidate",
                note="Heirs resolved dispute",
            )
        )
        assert own["parcel"]["ownership_status"] == "mixed_lease_candidate"

        # 4. Inspect live trace + read-only Cypher via MCP tools
        trace = json.loads(mcp_srv.get_relate_live_trace(area_slug=slug, limit=15))
        assert len(trace["traces"]) >= 5
        assert trace["store_info"]["node_count"] > 2000

        cyph = json.loads(
            mcp_srv.run_relate_cypher_readonly(
                area_slug=slug,
                cypher="MATCH (d:AgentDecision) RETURN count(d) AS cnt",
            )
        )
        assert cyph["rows"][0]["cnt"] >= 1
    finally:
        eng = mcp_srv._ENGINES.pop(slug, None)
        if eng is not None:
            eng.close()

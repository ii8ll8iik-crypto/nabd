"""Verification tests for Nabd v2 Relate Core (schema, ROLLBACK, COMMIT persistence & Live Trace)."""

from pathlib import Path
import shutil

from backend.relate_core import RelateClient, apply_schema


def test_relate_core_schema_rollback_and_commit_persistence(tmp_path: Path):
    src_db = Path("data/irbid-yarmouk.rl")
    db_copy = tmp_path / "irbid-core-test.rl"
    shutil.copy2(src_db, db_copy)

    # 1. Start live server, apply v2 constraints/indexes, verify What-If ROLLBACK & permanent COMMIT
    with RelateClient(db_copy) as client:
        schema_report = apply_schema(client)
        assert schema_report["constraints_checked"] == 7
        assert schema_report["indexes_checked"] == 6

        # Constructive What-If injection MUST be visible inside TX and vanish after ROLLBACK
        whatif_res = client.whatif_rollback(
            [
                ("CREATE (p:WhatIfFacility {id: $fid, category: $cat}) RETURN p.id AS id", {"fid": "sim-1", "cat": "clinic"}),
                ("MATCH (p:WhatIfFacility {id: $fid}) RETURN count(p) AS inside_tx", {"fid": "sim-1"}),
            ],
            tag="whatif:clinic",
        )
        assert whatif_res[0].rows[0]["id"] == "sim-1"
        assert whatif_res[1].rows[0]["inside_tx"] == 1

        after_rb = client.query("MATCH (p:WhatIfFacility) RETURN count(p) AS n", tag="verify:rollback")
        assert after_rb.rows[0]["n"] == 0

        # AgentDecision COMMIT MUST persist atomically
        commit_res = client.commit_transaction(
            [
                (
                    "CREATE (d:AgentDecision {id: $did, status: $st, reason: $rsn}) RETURN d.id AS id",
                    {"did": "dec-001", "st": "APPROVED", "rsn": "Blue ocean site with 0% cannibalization"},
                ),
                ("MATCH (d:AgentDecision {id: $did}) RETURN d.status AS status", {"did": "dec-001"}),
            ],
            tag="agent:decision",
        )
        assert commit_res[0].rows[0]["id"] == "dec-001"
        assert commit_res[1].rows[0]["status"] == "APPROVED"

        traces = client.recent_traces(limit=10)
        assert len(traces) >= 4
        assert any(t["tx_state"] == "ROLLED_BACK" for t in traces)
        assert any(t["tx_state"] == "COMMITTED" for t in traces)

    # 2. Re-open the .rl file fresh (read-only) to prove COMMIT survived server restart
    with RelateClient(db_copy, read_only=True) as ro_client:
        check = ro_client.query(
            "MATCH (d:AgentDecision {id: $did}) RETURN d.status AS status, d.reason AS reason",
            {"did": "dec-001"},
            tag="verify:reopen",
        )
        assert len(check.rows) == 1
        assert check.rows[0]["status"] == "APPROVED"


def test_v2_engine_live_whatif_parcel_optimizer_and_manhattan(tmp_path: Path):
    from backend.engine.physics import UrbanGraphEngine

    irbid_copy = tmp_path / "irbid-v2.rl"
    shutil.copy2(Path("data/irbid-yarmouk.rl"), irbid_copy)
    with UrbanGraphEngine(irbid_copy) as eng:
        assert eng.has_elevation
        assert len(eng.env_zones) >= 2
        sim = eng.simulate_injection(32.5365, 35.8555, category="clinic", monte_carlo_runs=30)
        assert sim["relate_transaction"]["tx_state"] == "ROLLED_BACK"
        assert sim["relate_transaction"]["parcel"]["parcel_id"] == sim["parcel_context"]["parcel_id"]
        assert "nearby_services" in sim["relate_transaction"]["multi_hop_context"]

        top = eng.optimize_locations(category="clinic", top_k=3, grid_size=4)
        assert len(top) >= 1 and top[0]["parcel_id"] is not None
        best_pid = top[0]["parcel_id"]

        eng.set_parcel_ownership(best_pid, "BLOCKED_OWNERSHIP", "Shared heirs dispute")
        top_after = eng.optimize_locations(category="clinic", top_k=3, grid_size=4)
        assert all(c["parcel_id"] != best_pid for c in top_after)

        dec = eng.commit_agent_decision(best_pid, "clinic", "REJECTED", "Shared heirs dispute", actor="mcp_agent")
        assert dec["status"] == "REJECTED"
        decisions = eng.list_agent_decisions()
        assert any(d["id"] == dec["id"] and d["parcel_id"] == best_pid for d in decisions)

    with UrbanGraphEngine(Path("data/manhattan-midtown.rl"), read_only=True) as m_eng:
        assert m_eng.has_elevation
        assert len(m_eng.env_zones) >= 50
        sim_day = m_eng.simulate_injection(40.7536, -73.9832, category="cafe", time_of_day="midday", monte_carlo_runs=30)
        sim_night = m_eng.simulate_injection(40.7536, -73.9832, category="cafe", time_of_day="late_night", monte_carlo_runs=30)
        assert sim_day["relate_transaction"]["tx_state"] == "READ_ONLY_CONTEXT"
        assert sim_day["parcel_context"]["parcel_id"] is not None
        assert sim_day["monte_carlo_envelope"]["p50_base"] > sim_night["monte_carlo_envelope"]["p50_base"]

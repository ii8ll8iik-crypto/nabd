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

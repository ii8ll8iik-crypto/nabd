#!/usr/bin/env python3
"""Judge verification script for Nabd v2: SHA-256 integrity, Cypher pack, ACID ROLLBACK & COMMIT persistence."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.relate_core import RelateClient

DATA_DIR = ROOT / "data"
CYPHER_DIR = ROOT / "scripts" / "cypher"
CITIES = ("irbid-yarmouk", "manhattan-midtown")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_city_bundle(slug: str) -> None:
    db_path = DATA_DIR / f"{slug}.rl"
    sha_path = DATA_DIR / f"{slug}.rl.sha256"
    assert db_path.exists(), f"Missing {db_path}"
    assert sha_path.exists(), f"Missing {sha_path}"

    expected = sha_path.read_text(encoding="utf-8").strip().split()[0]
    actual = sha256_file(db_path)
    assert actual == expected, f"SHA-256 mismatch for {slug}: {actual} != {expected}"
    print(f"[OK] {slug}.rl SHA-256 verified ({actual[:12]}...)")

    with RelateClient(db_path, read_only=True) as client:
        info = client.store_info()
        assert len(info.get("constraints", [])) >= 7, f"{slug}: expected >=7 constraints"
        assert len(info.get("indexes", [])) >= 13, f"{slug}: expected >=13 indexes"
        print(
            f"[OK] {slug}.rl schema verified: "
            f"{info['node_count']} nodes, {info['rel_count']} rels, "
            f"{len(info['constraints'])} constraints, {len(info['indexes'])} indexes"
        )

        for cypher_file in sorted(CYPHER_DIR.glob("*.cypher")):
            lines = [
                ln for ln in cypher_file.read_text(encoding="utf-8").splitlines()
                if not ln.strip().startswith("//")
            ]
            query = "\n".join(lines).strip()
            res = client.query(query, tag=f"verify:{cypher_file.stem}")
            ms = round(float(res.timings.get("elapsed_ms", 0.0)), 3)
            print(f"     -> {cypher_file.name}: {len(res.rows)} rows in {ms} ms")


def verify_acid_rollback_and_commit() -> None:
    src_db = DATA_DIR / "irbid-yarmouk.rl"
    with tempfile.TemporaryDirectory() as td:
        tmp_db = Path(td) / "acid-proof.rl"
        shutil.copy2(src_db, tmp_db)

        with RelateClient(tmp_db, read_only=False) as client:
            before = client.store_info()
            pid = client.query("MATCH (p:Parcel) RETURN p.id AS id LIMIT 1").rows[0]["id"]

            # 1. ACID ROLLBACK proof (What-If simulation leaves ZERO trace)
            rb_res = client.whatif_rollback(
                [
                    (
                        "MATCH (p:Parcel {id: $pid}) "
                        "CREATE (wf:WhatIfFacility {id: 'proof_wf_1', category: 'clinic'})-[:PROPOSED_AT]->(p) "
                        "RETURN wf.id AS wf_id",
                        {"pid": pid},
                    ),
                    (
                        "MATCH (wf:WhatIfFacility {id: 'proof_wf_1'}) RETURN count(wf) AS inside_tx",
                        {},
                    ),
                ],
                tag="verify:acid_rollback",
            )
            assert rb_res[1].rows[0]["inside_tx"] == 1
            after_rb_cnt = client.query("MATCH (wf:WhatIfFacility) RETURN count(wf) AS c").rows[0]["c"]
            after_rb = client.store_info()
            assert after_rb_cnt == 0, "ROLLBACK leaked WhatIfFacility node!"
            assert after_rb["node_count"] == before["node_count"]
            assert after_rb["rel_count"] == before["rel_count"]
            print(
                f"[OK] ACID ROLLBACK verified: node existed inside TX (1), "
                f"0 leaked after ROLLBACK, store counts unchanged ({after_rb['node_count']} nodes)."
            )

            # 2. ACID COMMIT persistence proof across server restart
            client.commit_transaction(
                [
                    (
                        "MATCH (p:Parcel {id: $pid}) "
                        "CREATE (d:AgentDecision {id: 'proof_dec_1', status: 'APPROVED', category: 'clinic', "
                        "reason: 'Verified by judge script', actor: 'judge_verifier', created_at: '2026-11-27T00:00:00Z'})"
                        "-[:EVALUATES]->(p) RETURN d.id AS id",
                        {"pid": pid},
                    )
                ],
                tag="verify:acid_commit",
            )

        # Re-open fresh read-only server to prove durability on disk
        with RelateClient(tmp_db, read_only=True) as ro_client:
            rows = ro_client.query(
                "MATCH (d:AgentDecision {id: 'proof_dec_1'})-[:EVALUATES]->(p:Parcel) "
                "RETURN d.status AS status, p.id AS parcel_id"
            ).rows
            assert len(rows) == 1 and rows[0]["status"] == "APPROVED"
            print(
                f"[OK] ACID COMMIT durability verified across Relate restart "
                f"(decision APPROVED on parcel {rows[0]['parcel_id']})."
            )


def main() -> None:
    print("=== Nabd v2 — Relate Judge Verification Suite ===")
    for city in CITIES:
        verify_city_bundle(city)
    verify_acid_rollback_and_commit()
    print("=== ALL VERIFICATIONS PASSED ===")


if __name__ == "__main__":
    main()

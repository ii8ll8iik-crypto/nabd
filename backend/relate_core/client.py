"""Persistent `relate serve` HTTP Query API v2 client with ACID ROLLBACK/COMMIT and Live Trace."""

from __future__ import annotations

import atexit
import json
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple


@dataclass
class RelateQueryResult:
    rows: List[Dict[str, Any]]
    fields: List[str]
    timings: Dict[str, Any] = field(default_factory=dict)
    counters: Dict[str, Any] = field(default_factory=dict)
    plan_cache: Optional[str] = None
    tx_state: str = "AUTO_COMMIT"


@dataclass
class RelateTraceEntry:
    timestamp: float
    tag: str
    tx_state: str
    statement: str
    parameters: Dict[str, Any]
    row_count: int
    elapsed_ms: float
    execute_ms: float
    plan_cache: Optional[str]
    counters: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class RelateClient:
    """Manages a local `relate serve --http` process for sub-millisecond transactional Cypher."""

    def __init__(
        self,
        db_path: Path | str,
        read_only: bool = False,
        database_name: str = "neo4j",
        trace_capacity: int = 80,
        startup_timeout_s: float = 8.0,
    ) -> None:
        self.db_path = Path(db_path).resolve()
        self.read_only = read_only
        self.database_name = database_name
        self.port = _find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._lock = threading.RLock()
        self._trace: Deque[RelateTraceEntry] = deque(maxlen=trace_capacity)
        self._proc: Optional[subprocess.Popen[str]] = None
        self._start(startup_timeout_s)
        atexit.register(self.close)

    def _start(self, timeout_s: float) -> None:
        cmd = [
            "relate",
            "serve",
            "--database",
            str(self.db_path),
            "--host",
            "127.0.0.1",
            "--http",
            str(self.port),
            "--auth",
            "none",
        ]
        if self.read_only:
            cmd.append("--read-only")

        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        deadline = time.monotonic() + timeout_s
        last_err: Optional[Exception] = None
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                err_out = (self._proc.stderr.read() if self._proc.stderr else "").strip()
                raise RuntimeError(f"relate serve exited early (rc={self._proc.returncode}): {err_out}")
            try:
                with urllib.request.urlopen(f"{self.base_url}/", timeout=0.5) as resp:
                    if resp.status == 200:
                        return
            except Exception as exc:
                last_err = exc
                time.sleep(0.05)
        self.close()
        raise RuntimeError(f"Timed out waiting for relate serve on {self.base_url}: {last_err}")

    def close(self) -> None:
        proc = self._proc
        if proc is None:
            return
        self._proc = None
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)

    def __enter__(self) -> "RelateClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _http(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout_s: float = 30.0,
    ) -> Tuple[int, Dict[str, Any]]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw = resp.read().decode("utf-8").strip()
                return resp.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8").strip()
            raise RuntimeError(f"Relate HTTP {exc.code} on {method} {path}: {raw}") from exc

    def _parse_envelope(
        self,
        body: Dict[str, Any],
        statement: str,
        parameters: Dict[str, Any],
        tag: str,
        tx_state: str,
    ) -> RelateQueryResult:
        if body.get("errors"):
            raise RuntimeError(f"Relate Cypher error: {body['errors']}")
        data = body.get("data") or {}
        fields = list(data.get("fields") or [])
        values = data.get("values") or []
        rows = [dict(zip(fields, row)) for row in values]
        timings = body.get("timings") or {}
        counters = body.get("counters") or {}
        plan_cache = body.get("planCache")

        entry = RelateTraceEntry(
            timestamp=time.time(),
            tag=tag,
            tx_state=tx_state,
            statement=statement.strip(),
            parameters=parameters,
            row_count=len(rows),
            elapsed_ms=round(float(timings.get("elapsed_ms", 0.0)), 3),
            execute_ms=round(float(timings.get("execute_ms", 0.0)), 3),
            plan_cache=plan_cache,
            counters=counters,
        )
        with self._lock:
            self._trace.append(entry)

        return RelateQueryResult(
            rows=rows,
            fields=fields,
            timings=timings,
            counters=counters,
            plan_cache=plan_cache,
            tx_state=tx_state,
        )

    def query(
        self,
        statement: str,
        parameters: Optional[Dict[str, Any]] = None,
        tag: str = "query",
    ) -> RelateQueryResult:
        params = dict(parameters or {})
        payload: Dict[str, Any] = {"statement": statement}
        if params:
            payload["parameters"] = params
        with self._lock:
            _, body = self._http("POST", f"/db/{self.database_name}/query/v2", payload)
        return self._parse_envelope(body, statement, params, tag=tag, tx_state="AUTO_COMMIT")

    def whatif_rollback(
        self,
        statements: Sequence[Tuple[str, Optional[Dict[str, Any]]]],
        tag: str = "whatif",
    ) -> List[RelateQueryResult]:
        """Execute a multi-statement constructive simulation inside an ACID TX, then ROLLBACK cleanly."""
        if not statements:
            return []
        results: List[RelateQueryResult] = []
        tx_id: Optional[str] = None
        with self._lock:
            try:
                for idx, (stmt, raw_params) in enumerate(statements):
                    params = dict(raw_params or {})
                    payload: Dict[str, Any] = {"statement": stmt}
                    if params:
                        payload["parameters"] = params
                    if idx == 0:
                        _, body = self._http("POST", f"/db/{self.database_name}/query/v2/tx", payload)
                        tx_id = (body.get("transaction") or {}).get("id")
                        if not tx_id:
                            raise RuntimeError(f"Failed to obtain transaction id: {body}")
                    else:
                        _, body = self._http("POST", f"/db/{self.database_name}/query/v2/tx/{tx_id}", payload)
                    results.append(
                        self._parse_envelope(body, stmt, params, tag=f"{tag}[{idx + 1}]", tx_state="ROLLED_BACK")
                    )
            finally:
                if tx_id:
                    self._http("DELETE", f"/db/{self.database_name}/query/v2/tx/{tx_id}")
        return results

    def commit_transaction(
        self,
        statements: Sequence[Tuple[str, Optional[Dict[str, Any]]]],
        tag: str = "commit",
    ) -> List[RelateQueryResult]:
        """Execute one or more statements atomically inside an ACID TX and COMMIT permanently."""
        if not statements:
            return []
        results: List[RelateQueryResult] = []
        tx_id: Optional[str] = None
        with self._lock:
            try:
                if len(statements) == 1:
                    stmt, raw_params = statements[0]
                    params = dict(raw_params or {})
                    payload: Dict[str, Any] = {"statement": stmt}
                    if params:
                        payload["parameters"] = params
                    _, body = self._http("POST", f"/db/{self.database_name}/query/v2/tx", payload)
                    tx_id = (body.get("transaction") or {}).get("id")
                    if not tx_id:
                        raise RuntimeError(f"Failed to obtain transaction id: {body}")
                    self._http("POST", f"/db/{self.database_name}/query/v2/tx/{tx_id}/commit")
                    tx_id = None
                    results.append(self._parse_envelope(body, stmt, params, tag=tag, tx_state="COMMITTED"))
                    return results

                for idx, (stmt, raw_params) in enumerate(statements):
                    params = dict(raw_params or {})
                    payload = {"statement": stmt}
                    if params:
                        payload["parameters"] = params
                    if idx == 0:
                        _, body = self._http("POST", f"/db/{self.database_name}/query/v2/tx", payload)
                        tx_id = (body.get("transaction") or {}).get("id")
                        if not tx_id:
                            raise RuntimeError(f"Failed to obtain transaction id: {body}")
                    elif idx == len(statements) - 1:
                        _, body = self._http("POST", f"/db/{self.database_name}/query/v2/tx/{tx_id}/commit", payload)
                        tx_id = None
                    else:
                        _, body = self._http("POST", f"/db/{self.database_name}/query/v2/tx/{tx_id}", payload)
                    results.append(
                        self._parse_envelope(body, stmt, params, tag=f"{tag}[{idx + 1}]", tx_state="COMMITTED")
                    )
            except Exception:
                if tx_id:
                    try:
                        self._http("DELETE", f"/db/{self.database_name}/query/v2/tx/{tx_id}")
                    except Exception:
                        pass
                raise
        return results

    def recent_traces(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in list(self._trace)[-limit:]]

    def store_info(self) -> Dict[str, Any]:
        res = subprocess.run(
            ["relate", "info", "--database", str(self.db_path), "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(res.stdout)

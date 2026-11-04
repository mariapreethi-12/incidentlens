"""Real loopback HTTP requests and SQLite faults; no generated telemetry."""
import json
import math
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SCENARIOS = {
    "healthy": {"title": "Healthy baseline", "description": "Collect normal checkout traffic."},
    "database-lock": {"title": "Database contention", "description": "Hold a real SQLite write lock during checkout."},
    "payment-outage": {"title": "Payment dependency outage", "description": "Payment HTTP requests return 503."},
    "inventory-latency": {"title": "Slow inventory", "description": "Inventory requests acquire 180 ms of delay."},
    "bad-release": {"title": "Checkout regression", "description": "Deploy a checkout handler with a real missing-field error."},
    "retry-storm": {"title": "Retry amplification", "description": "Deploy an excessive retry budget during a payment outage."},
}


class Lab:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = self.directory / "orders.sqlite"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, created REAL)")
        self.lock = threading.RLock()
        self.events = []
        self.changes = []
        self.generation = uuid.uuid4().hex[:10]
        self.fault = "healthy"
        self.held_connection = None
        lab = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                service = self.path.split("?")[0].strip("/")
                trace = self.headers.get("X-Trace-Id", uuid.uuid4().hex[:12])
                start = time.perf_counter()
                status, message = 200, "ok"
                try:
                    if service == "inventory":
                        if lab.fault == "inventory-latency":
                            time.sleep(0.18)
                        message = "Inventory reservation completed"
                    elif service == "payments":
                        if lab.fault in ("payment-outage", "retry-storm"):
                            status, message = 503, "Payment gateway unavailable"
                        else:
                            message = "Payment authorized"
                    elif service == "checkout":
                        if lab.fault == "bad-release":
                            payload = {"total": 42}
                            payload["currency"]
                        lab.request("inventory", trace)
                        attempts = 4 if lab.fault == "retry-storm" else 1
                        for attempt in range(attempts):
                            try:
                                lab.request("payments", trace)
                                break
                            except HTTPError:
                                if attempt + 1 == attempts:
                                    raise
                        began = time.perf_counter()
                        db_status, db_message = 200, "Order committed"
                        try:
                            with closing(sqlite3.connect(lab.db, timeout=0.025)) as conn, conn:
                                conn.execute("INSERT INTO orders VALUES (?, ?)", (uuid.uuid4().hex, time.time()))
                        except sqlite3.OperationalError as exc:
                            db_status, db_message = 503, str(exc)
                            raise
                        finally:
                            lab.record("database", trace, db_status, db_message, began)
                        message = "Checkout completed"
                    else:
                        status, message = 404, "Unknown service"
                except KeyError as exc:
                    status, message = 500, f"KeyError: missing required field {exc} in release checkout-v2"
                except sqlite3.OperationalError as exc:
                    status, message = 503, f"Order write failed: {exc}"
                except HTTPError as exc:
                    status, message = 502, f"Downstream HTTP {exc.code} from payments"
                except Exception:
                    status, message = 500, "Unhandled service failure"
                lab.record(service, trace, status, message, start)
                body = json.dumps({"service": service, "message": message, "trace_id": trace}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def request(self, service, trace=None):
        req = Request(f"{self.url}/{service}", headers={"X-Trace-Id": trace or uuid.uuid4().hex[:12]})
        with urlopen(req, timeout=3) as response:
            return json.load(response)

    def record(self, service, trace, status, message, began):
        with self.lock:
            self.events.append({
                "id": f"e-{self.generation}-{len(self.events)+1}", "timestamp": time.time(),
                "service": service, "trace_id": trace, "status": status, "message": message,
                "duration_ms": round((time.perf_counter() - began) * 1000, 2),
            })

    def release_lock(self):
        if self.held_connection:
            self.held_connection.rollback()
            self.held_connection.close()
            self.held_connection = None

    def inject(self, scenario):
        if scenario not in SCENARIOS:
            raise ValueError("Unknown scenario")
        self.release_lock()
        with self.lock:
            self.events = []
            self.changes = []
            self.generation = uuid.uuid4().hex[:10]
            self.fault = scenario
            # A benign change is present in every run to discourage correlation-only diagnosis.
            self.changes.append({"id": f"c-{self.generation}-1", "timestamp": time.time(),
                                 "service": "inventory", "change": "Updated dashboard annotation; no runtime change"})
            if scenario in ("bad-release", "retry-storm"):
                self.changes.append({"id": f"c-{self.generation}-2", "timestamp": time.time(),
                                     "service": "checkout", "change": "Deployed checkout-v2: currency mapping changed" if scenario == "bad-release"
                                     else "Changed payment retry budget from 1 to 4 attempts"})
        if scenario == "database-lock":
            self.held_connection = sqlite3.connect(self.db, check_same_thread=False)
            self.held_connection.execute("BEGIN EXCLUSIVE")

    def probe(self, count=8):
        for _ in range(count):
            try:
                self.request("checkout")
            except HTTPError:
                pass

    def recover(self):
        self.release_lock()
        self.fault = "healthy"
        with self.lock:
            self.changes.append({"id": f"c-{self.generation}-{len(self.changes)+1}", "timestamp": time.time(),
                                 "service": "lab", "change": "Operator approved lab reset: restored healthy configuration"})
        cutoff = time.time()
        self.probe(5)
        recent = [e for e in self.events if e["timestamp"] >= cutoff and e["service"] == "checkout"]
        return {"healthy": len(recent) == 5 and all(e["status"] == 200 for e in recent), "probes": len(recent)}

    def snapshot(self):
        with self.lock:
            return {"generation": self.generation, "events": [dict(e) for e in self.events],
                    "changes": [dict(c) for c in self.changes]}

    def close(self):
        self.release_lock()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def metrics(snapshot):
    result = []
    for service in ("checkout", "inventory", "payments", "database"):
        events = [e for e in snapshot["events"] if e["service"] == service]
        durations = sorted(e["duration_ms"] for e in events)
        result.append({"id": f"m-{snapshot['generation']}-{service}", "service": service,
                       "requests": len(events), "errors": sum(e["status"] >= 500 for e in events),
                       "error_rate": round(sum(e["status"] >= 500 for e in events) / len(events), 3) if events else 0,
                       "p95_ms": durations[max(0, math.ceil(len(durations) * .95)-1)] if durations else 0})
    return result

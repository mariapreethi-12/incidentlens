import argparse
import json
import os
import sqlite3
import threading
import time
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .agent import investigate
from .config import load_local_env
from .lab import Lab, SCENARIOS, metrics

WEB = Path(__file__).parent / "web"


class App:
    def __init__(self, directory):
        self.lab = Lab(directory)
        self.operation = threading.Lock()
        self.state_lock = threading.RLock()
        self.report = None
        self.recovery = None
        self.active_scenario = "healthy"
        self.history = Path(directory) / "investigations.sqlite"
        with closing(sqlite3.connect(self.history)) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS investigations (id INTEGER PRIMARY KEY, created REAL, report TEXT)")
        self.lab.probe(6)

    def state(self):
        snapshot = self.lab.snapshot()
        with self.state_lock:
            return {"generation": snapshot["generation"], "scenario": self.active_scenario,
                    "scenarios": SCENARIOS, "busy": self.operation.locked(),
                    "metrics": metrics(snapshot), "events": snapshot["events"][-100:], "changes": snapshot["changes"],
                    "report": self.report, "recovery": self.recovery,
                    "model_configured": bool(os.environ.get("OPENAI_API_KEY") and os.environ.get("OPENAI_MODEL")),
                    "model": os.environ.get("OPENAI_MODEL")}

    def perform(self, path, body):
        if not self.operation.acquire(blocking=False):
            return 409, {"error": "Another lab operation is running. Please wait."}
        try:
            if path == "/api/scenario":
                scenario = body.get("scenario")
                if scenario not in SCENARIOS:
                    raise ValueError("Choose a known scenario")
                with self.state_lock:
                    self.report = self.recovery = None
                    self.active_scenario = scenario
                self.lab.inject(scenario)
                self.lab.probe(8)
            elif path == "/api/probe":
                # A report is a point-in-time snapshot; collect then invalidate it.
                self.lab.probe(8)
                with self.state_lock:
                    self.report = self.recovery = None
            elif path == "/api/investigate":
                mode = body.get("mode", "baseline")
                report = investigate(self.lab.snapshot(), mode)
                with closing(sqlite3.connect(self.history)) as conn, conn:
                    conn.execute("INSERT INTO investigations(created,report) VALUES (?,?)", (time.time(), json.dumps(report)))
                with self.state_lock:
                    self.report = report
                    self.recovery = None
            elif path == "/api/recover":
                with self.state_lock:
                    if not self.report or body.get("generation") != self.lab.generation or self.report["generation"] != self.lab.generation:
                        raise ValueError("Investigate the current run before approving recovery")
                    if self.recovery is not None:
                        raise ValueError("This recovery was already approved")
                    if self.report["diagnosis"]["category"] in ("healthy", "insufficient-evidence"):
                        raise ValueError("There is no actionable diagnosis")
                result = self.lab.recover()
                with self.state_lock:
                    self.recovery = result
            else:
                return 404, {"error": "Unknown operation"}
            return 200, self.state()
        except (ValueError, TypeError, KeyError) as exc:
            return 400, {"error": str(exc)}
        except Exception as exc:
            # Never reflect API headers, keys or provider response bodies to the browser.
            return 502, {"error": f"Operation failed ({type(exc).__name__}). No synthetic AI result was substituted."}
        finally:
            self.operation.release()


def create_server(app, port=8787):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, data, content_type="application/json"):
            body = json.dumps(data).encode() if content_type == "application/json" else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {"error": "Invalid host"})
            path = urlsplit(self.path).path
            if path == "/api/state":
                return self.send(200, app.state())
            if path == "/api/report":
                return self.send(200, app.report or {})
            files = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "application/javascript"), "/styles.css": ("styles.css", "text/css")}
            if path not in files:
                return self.send(404, {"error": "Not found"})
            filename, mime = files[path]
            self.send(200, (WEB / filename).read_bytes(), mime)

        def do_POST(self):
            if not self.valid_host():
                return self.send(403, {"error": "Invalid host"})
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"):
                return self.send(403, {"error": "Cross-origin operation rejected"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("Expected a small JSON body")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("Expected a JSON object")
            except (ValueError, json.JSONDecodeError):
                return self.send(400, {"error": "Invalid JSON request"})
            status, result = app.perform(urlsplit(self.path).path, body)
            self.send(status, result)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description="IncidentLens local investigation console")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--data", default="data")
    args = parser.parse_args()
    load_local_env()
    app = App(args.data)
    server = create_server(app, args.port)
    print(f"IncidentLens: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.lab.close()


if __name__ == "__main__":
    main()

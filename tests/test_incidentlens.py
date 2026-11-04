import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from incidentlens.agent import EvidenceTools, investigate, validate
from incidentlens.config import load_local_env
from incidentlens.lab import Lab, SCENARIOS, metrics
from incidentlens.server import App, create_server


class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.lab = Lab(self.temp.name)

    def tearDown(self):
        self.lab.close()
        self.temp.cleanup()

    def test_real_faults_are_detected_and_recovery_is_probed(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                self.lab.inject(scenario)
                self.lab.probe(4)
                snapshot = self.lab.snapshot()
                self.assertNotIn("fault", snapshot)
                self.assertNotIn("scenario", snapshot)
                report = investigate(snapshot)
                self.assertEqual(report["diagnosis"]["category"], scenario)
                self.assertTrue(report["diagnosis"]["evidence_ids"])
                self.assertTrue(self.lab.recover()["healthy"])

    def test_empty_evidence_abstains(self):
        self.assertEqual(investigate(self.lab.snapshot())["diagnosis"]["category"], "insufficient-evidence")

    def test_retry_fault_creates_four_actual_payment_spans(self):
        self.lab.inject("retry-storm")
        self.lab.probe(3)
        ms = {m["service"]: m for m in metrics(self.lab.snapshot())}
        self.assertEqual(ms["payments"]["requests"], 12)
        self.assertEqual(ms["checkout"]["requests"], 3)

    def test_fabricated_citation_is_rejected(self):
        tools = EvidenceTools(self.lab.snapshot())
        with self.assertRaises(ValueError):
            validate({"category":"bad-release", "summary":"A guess", "evidence_ids":["invented"], "next_steps":[]}, tools)

    def test_write_tool_and_arguments_are_rejected(self):
        tools = EvidenceTools(self.lab.snapshot())
        for name, args in [("run_shell", {}), ("read_logs", {"sql":"DROP TABLE orders"})]:
            with self.assertRaises(ValueError):
                tools.call(name, args)

    def test_tool_budget(self):
        tools = EvidenceTools(self.lab.snapshot())
        for _ in range(16):
            tools.call("read_metrics", {})
        with self.assertRaises(ValueError):
            tools.call("read_metrics", {})

    def test_model_loop_executes_calls_and_returns_outputs(self):
        self.lab.probe(3)
        snapshot = self.lab.snapshot()
        calls = []
        def transport(payload):
            calls.append(payload)
            if len(calls) == 1:
                return {"output":[{"type":"function_call", "name":name, "arguments":"{}", "call_id":name}
                                  for name in ("read_logs","read_metrics","read_traces","read_changes")],
                        "usage":{"input_tokens":10,"output_tokens":20}}
            self.assertEqual(sum(i.get("type")=="function_call_output" for i in payload["input"]),4)
            diagnosis = {"category":"healthy", "summary":"Observed success", "evidence_ids":[snapshot["events"][0]["id"]], "next_steps":[]}
            return {"output":[{"type":"message", "content":[{"type":"output_text", "text":json.dumps(diagnosis)}]}]}
        with patch.dict(os.environ, {"OPENAI_MODEL":"test-model"}):
            report = investigate(snapshot,"agent",transport)
        self.assertEqual(report["mode"], "agent")
        self.assertEqual(report["usage"]["input_tokens"],10)

    def test_model_failure_never_falls_back_to_baseline(self):
        def broken(_):
            raise RuntimeError("Provider unavailable")
        with patch.dict(os.environ, {"OPENAI_MODEL":"test-model"}):
            with self.assertRaises(RuntimeError):
                investigate(self.lab.snapshot(),"agent",broken)


class ConfigTests(unittest.TestCase):
    def test_local_settings_load_without_overriding_environment(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            file = __import__('pathlib').Path(directory) / '.env'
            file.write_text('OPENAI_API_KEY="test-secret"\nOPENAI_MODEL=test-model\nUNRELATED=ignored\n', encoding='utf-8')
            load_local_env(file)
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'test-secret')
            self.assertEqual(os.environ['OPENAI_MODEL'], 'test-model')
            self.assertNotIn('UNRELATED', os.environ)
            os.environ['OPENAI_MODEL'] = 'existing-model'
            load_local_env(file)
            self.assertEqual(os.environ['OPENAI_MODEL'], 'existing-model')

    def test_placeholder_is_not_loaded(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            file = __import__('pathlib').Path(directory) / '.env'
            file.write_text('OPENAI_API_KEY=PASTE_YOUR_KEY_HERE\n', encoding='utf-8')
            load_local_env(file)
            self.assertNotIn('OPENAI_API_KEY', os.environ)


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = App(self.temp.name)

    def tearDown(self):
        self.app.lab.close()
        self.temp.cleanup()

    def test_recovery_needs_current_report_and_is_not_repeatable(self):
        self.assertEqual(self.app.perform("/api/recover", {"generation":"old"})[0],400)
        self.app.perform("/api/scenario", {"scenario":"database-lock"})
        self.app.perform("/api/investigate", {"mode":"baseline"})
        generation=self.app.lab.generation
        self.assertEqual(self.app.perform("/api/recover", {"generation":"old"})[0],400)
        status, state=self.app.perform("/api/recover", {"generation":generation})
        self.assertEqual(status,200)
        self.assertTrue(state["recovery"]["healthy"])
        self.assertEqual(self.app.perform("/api/recover", {"generation":generation})[0],400)
        self.app.perform("/api/scenario", {"scenario":"bad-release"})
        self.assertIsNone(self.app.report)

    def test_concurrent_operations_are_rejected(self):
        self.app.operation.acquire()
        try:
            self.assertEqual(self.app.perform("/api/probe", {})[0],409)
        finally:
            self.app.operation.release()

    def test_http_app_assets_api_and_origin_guard(self):
        server=create_server(self.app,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        url=f"http://127.0.0.1:{server.server_port}"
        try:
            for path in ("/", "/app.js", "/styles.css", "/api/state"):
                with urlopen(url+path) as response:
                    self.assertEqual(response.status,200)
                    self.assertTrue(response.read())
            req=Request(url+"/api/probe",data=b"{}",headers={"Content-Type":"application/json","Origin":"https://example.com"})
            with self.assertRaises(HTTPError) as caught:
                urlopen(req)
            self.assertEqual(caught.exception.code,403)
            req=Request(url+"/api/scenario",data=b'{"scenario":"bad-release"}',headers={"Content-Type":"application/json"})
            with urlopen(req) as response:
                self.assertEqual(json.load(response)["scenario"],"bad-release")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("local_ci", Path(__file__).with_name("local_ci_windows.py"))
ci_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_module)
SHA = "a" * 40


class LocalCITest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "owned"
        (self.root / "workspace").mkdir(parents=True)
        (self.root / "workspace/.git").write_text("fixture")
        (self.root / "ownership.json").write_text(json.dumps({"repository": ci_module.REPOSITORY}))
        self.config = {"root": str(self.root), "source": str(self.base / "source"),
                       "refs": ["main"], "java_home": "jdk", "sdk": "sdk",
                       "gradle_home": "gradle-cache", "python": sys.executable,
                       "gh": "gh", "gradle": "gradle", "runtime": "runtime"}
        self.ci = ci_module.LocalCI(self.config)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reject_wrong_owner(self):
        (self.root / "ownership.json").write_text('{"repository":"someone/else"}')
        with self.assertRaises(ValueError):
            ci_module.LocalCI(self.config)

    def test_reject_source_workspace_alias(self):
        self.config["source"] = str(self.root / "workspace")
        with self.assertRaises(ValueError):
            ci_module.LocalCI(self.config)

    def test_ref_and_sha_guards(self):
        for bad in ["../main", "-main", "main; calc", "main&calc", "main:other", "main\nx", "a..b"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ci_module.valid_ref(bad)
        for bad in ["a" * 39, "a" * 41, "HEAD", "-f", "x" * 40]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ci_module.valid_sha(bad)
        self.assertEqual(ci_module.valid_ref("fix/checkpoint-20261107"), "fix/checkpoint-20261107")

    def test_atomic_json_and_single_instance(self):
        path = self.root / "x.json"
        ci_module.save_json(path, {"v": 1})
        ci_module.save_json(path, {"v": 2})
        self.assertEqual(json.loads(path.read_text()), {"v": 2})
        with ci_module.single_worker(self.root / "worker.lock"):
            with self.assertRaises(OSError):
                with ci_module.single_worker(self.root / "worker.lock"):
                    self.fail("second worker entered")

    def test_real_child_failure_is_not_pass(self):
        report = {"sha": SHA, "ref": "main", "steps": []}
        with self.assertRaisesRegex(RuntimeError, "exit 7"):
            self.ci.step(report, "failed", [sys.executable, "-c", "print('test error');raise SystemExit(7)"])
        self.assertEqual(report["steps"][0]["returncode"], 7)

    def test_timeout_does_not_kill_an_unrelated_process(self):
        sentinel = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
        try:
            report = {"sha": SHA, "ref": "main", "steps": []}
            with self.assertRaisesRegex(RuntimeError, "timeout"):
                self.ci.step(report, "slow", [sys.executable, "-c", "import time;time.sleep(5)"], timeout=0.05)
            self.assertIsNone(sentinel.poll())
        finally:
            sentinel.terminate()
            sentinel.wait(timeout=10)

    def test_failure_publishes_failure_and_never_success(self):
        states = []
        with patch.object(self.ci, "publish", side_effect=lambda sha, state, desc: states.append(state)), \
             patch.object(self.ci, "prepare"), \
             patch.object(self.ci, "checks", side_effect=RuntimeError("lint failed")):
            result = self.ci.run_one("main", SHA)
        self.assertEqual(states, ["pending", "failure"])
        self.assertEqual(result["state"], "failure")
        self.assertTrue(result["published"])

    def test_success_only_after_integrity_and_cache_skips_work(self):
        states = []
        def checks(report):
            report["core_groups"] = 17
        with patch.object(self.ci, "publish", side_effect=lambda sha, state, desc: states.append(state)), \
             patch.object(self.ci, "prepare") as prepare, \
             patch.object(self.ci, "checks", side_effect=checks) as check, \
             patch.object(self.ci, "integrity") as integrity:
            first = self.ci.run_one("main", SHA)
            second = self.ci.run_one("main", SHA)
        self.assertEqual(states, ["pending", "success"])
        self.assertEqual(first["state"], second["state"])
        self.assertEqual(prepare.call_count, 1)
        self.assertEqual(check.call_count, 1)
        self.assertEqual(integrity.call_count, 1)

    def test_changed_source_cannot_publish_green(self):
        states = []
        with patch.object(self.ci, "publish", side_effect=lambda sha, state, desc: states.append(state)), \
             patch.object(self.ci, "prepare"), patch.object(self.ci, "checks"), \
             patch.object(self.ci, "integrity", side_effect=RuntimeError("checkout changed")):
            result = self.ci.run_one("main", SHA)
        self.assertEqual(states, ["pending", "failure"])
        self.assertEqual(result["state"], "failure")

    def test_failed_publication_is_visible_and_retried_without_build(self):
        calls = []
        def publish(sha, state, desc):
            calls.append(state)
            if state == "success" and calls.count("success") == 1:
                raise RuntimeError("network down")
        def checks(report):
            report["core_groups"] = 17
        with patch.object(self.ci, "publish", side_effect=publish), \
             patch.object(self.ci, "prepare") as prepare, \
             patch.object(self.ci, "checks", side_effect=checks), \
             patch.object(self.ci, "integrity"):
            first = self.ci.run_one("main", SHA)
            self.assertFalse(first["published"])
            second = self.ci.run_one("main", SHA)
        self.assertTrue(second["published"])
        self.assertEqual(prepare.call_count, 1)


if __name__ == "__main__":
    unittest.main()

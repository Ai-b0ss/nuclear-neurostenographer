"""Scoped local CI for one private repository. No Actions runner or handset access."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

REPOSITORY = "Ai-b0ss/nuclear-neurostenographer"
CONTEXT = "local/windows-ci"
PYTHON_CHECKS = [
    ["tools/test_provision_asr.py"], ["tools/test_create_checkpoint.py"],
    ["tools/test_score_transcript.py"], ["tools/test_android_workflow.py"],
    ["tools/test_runtime_identity.py"], ["-O", "tools/test_runtime_identity.py"],
    ["tools/test_android_ui.py"], ["tools/test_app_failure_detector.py"],
    ["tools/test_phone_kit.py"], ["tools/test_score_live_run.py"],
    ["tools/test_android_evidence.py"], ["tools/runtime/test_dependencies.py"],
    ["-O", "tools/test_android_evidence.py"],
]
GRADLE_TASKS = [":core:runCoreTests", ":app:lintDebug", ":app:assembleDebug",
                ":app:assembleDebugAndroidTest"]


def valid_sha(value):
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("Expected a full commit SHA")
    return value


def valid_ref(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_.-]*", value) or ".." in value:
        raise ValueError("Unsafe branch name")
    return value


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = path.with_suffix(path.suffix + ".part")
    stage.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8", newline="\n")
    stage.replace(path)


@contextmanager
def single_worker(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if path.stat().st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class LocalCI:
    def __init__(self, config):
        self.config = config
        self.root = Path(config["root"]).resolve()
        self.source = Path(config["source"]).resolve()
        self.workspace = self.root / "workspace"
        marker = json.loads((self.root / "ownership.json").read_text(encoding="utf-8-sig"))
        if marker.get("repository") != REPOSITORY:
            raise ValueError("Wrong repository ownership marker")
        if self.workspace.resolve() != self.workspace or self.workspace == self.source:
            raise ValueError("Workspace must be an owned directory, not a link or source checkout")
        if not (self.workspace / ".git").exists():
            raise ValueError("Create the dedicated Git worktree first")
        self.refs = [valid_ref(ref) for ref in config["refs"]]
        if not self.refs:
            raise ValueError("Configure explicit trusted branches")
        self.reports = self.root / "reports"
        self.stop_file = self.root / "STOP"
        self.env = os.environ.copy()
        self.env.update(JAVA_HOME=config["java_home"], ANDROID_HOME=config["sdk"],
                        GRADLE_USER_HOME=config["gradle_home"], PYTHONUTF8="1",
                        PYTHONIOENCODING="utf-8", GIT_TERMINAL_PROMPT="0",
                        GH_PROMPT_DISABLED="1", CI="true")
        self.env["PATH"] = os.pathsep.join(config.get("path_prefix", [])) + os.pathsep + self.env["PATH"]
        self.spec = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def output(self, args, cwd=None):
        return subprocess.check_output(args, cwd=cwd or self.source, env=self.env,
                                       timeout=90, encoding="utf-8", errors="replace", stderr=subprocess.PIPE).strip()

    def state(self, **values):
        save_json(self.root / "current.json", {"pid": os.getpid(), "time": time.time(), **values})

    def heads(self):
        origin = self.output(["git", "remote", "get-url", "origin"])
        if origin.removesuffix(".git") != "https://github.com/" + REPOSITORY:
            raise ValueError("Unexpected source origin")
        self.output(["git", "fetch", "--no-tags", "origin"])
        return [(ref, valid_sha(self.output(["git", "rev-parse", "origin/" + ref])))
                for ref in self.refs]

    def publish(self, sha, state, description):
        valid_sha(sha)
        payload = self.root / "status-request.json"
        save_json(payload, {"state": state, "context": CONTEXT,
                           "description": description[:140], **({"target_url": self.config["details_url"]} if self.config.get("details_url") else {})})
        self.output([self.config["gh"], "api", "--method", "POST",
                     "repos/" + REPOSITORY + "/statuses/" + sha, "--input", str(payload)])
        statuses = json.loads(self.output([self.config["gh"], "api",
                              "repos/" + REPOSITORY + "/commits/" + sha + "/statuses?per_page=100"]))
        latest = next(item for item in statuses if item["context"] == CONTEXT)
        if latest["state"] != state:
            raise RuntimeError("GitHub did not confirm the published status")

    def prepare(self, sha):
        valid_sha(sha)
        if shutil.disk_usage(self.root).free < self.config.get("min_free_bytes", 1073741824):
            raise RuntimeError("Less than the configured free disk budget")
        files = self.output(["git", "ls-tree", "-r", "--name-only", sha]).splitlines()
        for name in files:
            if name == "local.properties" or name == ".local" or name.startswith(".local/") or name == "app/libs/sherpa-onnx-1.12.20.aar":
                raise ValueError("Commit attempts to replace host-provisioned paths")
        self.output(["git", "checkout", "--detach", "--force", sha], self.workspace)
        if self.output(["git", "rev-parse", "HEAD"], self.workspace) != sha:
            raise RuntimeError("Wrong checkout")
        pins = (self.workspace / "tools/runtime/runtime.properties").read_text(encoding="utf-8")
        expected = re.findall(r"^sha256\s*=\s*([0-9a-f]{64})\s*$", pins, re.M)
        runtime = Path(self.config["runtime"])
        with runtime.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if expected != [actual]:
            raise ValueError("Cached AAR does not match this commit's runtime pin")
        target = self.workspace / "app/libs/sherpa-onnx-1.12.20.aar"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_size != runtime.stat().st_size:
            shutil.copyfile(runtime, target)
        else:
            with target.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != actual:
                    shutil.copyfile(runtime, target)
        (self.workspace / "local.properties").write_text(
            "sdk.dir=" + Path(self.config["sdk"]).as_posix() + "\n", encoding="utf-8")

    @staticmethod
    def terminate_owned(process):
        if process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            import signal
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=30)

    def step(self, report, name, args, timeout=180):
        path = self.reports / report["sha"] / (str(len(report["steps"])).zfill(2) + "-" + name + ".log")
        path.parent.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        self.state(mode="running", sha=report["sha"], ref=report["ref"], step=name)
        flags = (subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name == "nt" else 0
        with path.open("wb") as log:
            process = subprocess.Popen(args, cwd=self.workspace, env=self.env, stdout=log,
                                       stderr=subprocess.STDOUT, creationflags=flags,
                                       start_new_session=os.name != "nt")
            reason = None
            while process.poll() is None:
                if self.stop_file.exists() or time.monotonic() - start > timeout:
                    reason = "cancelled" if self.stop_file.exists() else "timeout"
                    self.terminate_owned(process)
                    break
                time.sleep(0.25)
        result = {"name": name, "returncode": process.returncode,
                  "seconds": round(time.monotonic() - start, 2), "log": path.name}
        if reason:
            result["reason"] = reason
        report["steps"].append(result)
        if process.returncode != 0 or reason:
            raise RuntimeError(name + ": " + (reason or "exit " + str(process.returncode)))
        return path.read_text(encoding="utf-8", errors="replace")

    def checks(self, report):
        py = self.config["python"]
        for index, args in enumerate(PYTHON_CHECKS):
            self.step(report, "python-" + str(index), [py, *args])
        if (self.workspace / "tools/test_local_ci_windows.py").is_file():
            self.step(report, "local-ci-controller-tests", [py, "tools/test_local_ci_windows.py"])
        self.step(report, "stored-evidence", [py, "tools/verify_android_evidence.py",
                  "--ui-report", "docs/evidence/round11-ui-flow.json",
                  "--apk-report", "docs/evidence/round11-apk-inspection.json",
                  "--directory", "docs/evidence", "--prefix", "round11-provider-export"])
        # cmd is used only for the fixed, locally configured batch executable.
        gradle = self.config["gradle"]
        if os.name == "nt":
            if re.search(r'[\s&|<>^%"\r\n]', gradle):
                raise ValueError("Use a Gradle batch path without shell metacharacters or spaces")
            command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", gradle]
        else:
            command = [gradle]
        text = self.step(report, "gradle", command + ["--offline", "--no-daemon", "--console=plain",
                         "--max-workers=2", "-Dorg.gradle.priority=low", *GRADLE_TASKS], timeout=1800)
        groups = re.search(r"(\d+) CORE TEST GROUPS PASSED", text)
        if not groups:
            raise RuntimeError("Gradle did not report executed core tests")
        report["core_groups"] = int(groups.group(1))
        for kind in ["plain", "named", "edited"]:
            for script in ["verify_transcript_exports.py", "test_transcript_exports.py"]:
                self.step(report, kind + "-" + script.removesuffix(".py"),
                          [py, "tools/" + script, "core/build/export-samples/" + kind])
        self.step(report, "contest-json", [py, "tools/verify_contest_json.py",
                  "core/build/export-samples/contest/dialogue.json",
                  "core/build/export-samples/plain/dialogue.json"])
        self.step(report, "apk-inspection", [py, "tools/check_apk.py",
                  "app/build/outputs/apk/debug/app-debug.apk", "--aapt",
                  str(Path(self.config["sdk"]) / "build-tools/35.0.0/aapt.exe"),
                  "--runtime-aar", "app/libs/sherpa-onnx-1.12.20.aar",
                  "--output", str(self.reports / report["sha"] / "apk-inspection.json")])
        report["device_inference"] = "NOT_RUN"
        report["scope"] = "Windows counterpart of android.yml: no emulator, physical device or hosted artifacts"

    def integrity(self, sha):
        if self.output(["git", "rev-parse", "HEAD"], self.workspace) != sha:
            raise RuntimeError("Checkout changed during checks")
        if self.output(["git", "diff", "--name-only", "HEAD"], self.workspace):
            raise RuntimeError("Tracked source changed during checks")

    def run_one(self, ref, sha, force=False):
        valid_ref(ref)
        valid_sha(sha)
        summary = self.reports / sha / "summary.json"
        if summary.exists() and not force:
            cached = json.loads(summary.read_text(encoding="utf-8"))
            if cached.get("spec") == self.spec and cached.get("state") in ("success", "failure"):
                if not cached.get("published"):
                    self.publish(sha, cached["state"], cached["description"])
                    cached["published"] = True
                    save_json(summary, cached)
                return cached
        report = {"sha": sha, "ref": ref, "repository": REPOSITORY, "spec": self.spec,
                  "started": time.time(), "steps": [], "state": "pending", "published": False}
        self.publish(sha, "pending", "Windows PC: local CI running")
        save_json(summary, report)
        try:
            self.prepare(sha)
            self.checks(report)
            self.integrity(sha)
            report["state"] = "success"
            report["description"] = "PASS: Python checks, core " + str(report["core_groups"]) + ", lint, APKs, exports, runtime/ELF; no device inference"
        except Exception as error:
            report["state"] = "error" if self.stop_file.exists() else "failure"
            report["description"] = str(error)[:140]
        report["finished"] = time.time()
        save_json(summary, report)
        try:
            self.publish(sha, report["state"], report["description"])
            report["published"] = True
        except Exception as error:
            report["publication_error"] = type(error).__name__
        save_json(summary, report)
        self.state(mode="idle", sha=sha, ref=ref, result=report["state"], published=report["published"])
        return report

    def watch(self):
        while not self.stop_file.exists():
            try:
                heads = self.heads()
                for ref, sha in heads:
                    if self.stop_file.exists():
                        break
                    self.run_one(ref, sha)
                if not self.stop_file.exists():
                    self.state(mode="watching", heads=dict(heads))
            except Exception as error:
                self.state(mode="retrying", error=str(error)[:200])
            for _ in range(max(10, self.config.get("poll_seconds", 60))):
                if self.stop_file.exists():
                    break
                time.sleep(1)
        self.state(mode="stopped")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("command", choices=["run", "watch", "status", "stop"])
    parser.add_argument("--ref")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    ci = LocalCI(json.loads(args.config.read_text(encoding="utf-8-sig")))
    if args.command == "status":
        print((ci.root / "current.json").read_text(encoding="utf-8"))
        return 0
    if args.command == "stop":
        (ci.root / "DISABLED").touch()
        ci.stop_file.touch()
        return 0
    with single_worker(ci.root / "worker.lock"):
        if args.command == "watch":
            if args.resume:
                (ci.root / "DISABLED").unlink(missing_ok=True)
            if (ci.root / "DISABLED").exists():
                return 0
        ci.stop_file.unlink(missing_ok=True)
        if args.command == "watch":
            ci.watch()
            return 0
        ref = valid_ref(args.ref or ci.refs[0])
        if ref not in ci.refs:
            raise ValueError("Branch is outside the configured allowlist")
        heads = dict(ci.heads())
        report = ci.run_one(ref, heads[ref], args.force)
        print(json.dumps(report, ensure_ascii=True))
        return 0 if report["state"] == "success" and report["published"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

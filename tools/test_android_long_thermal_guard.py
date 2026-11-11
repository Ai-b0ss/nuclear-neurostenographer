import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import run_android_long_thermal_guard as watchdog
from run_android_long_thermal_guard import (parse_battery, remaining_qa_processes,
    QA_PACKAGE, TEST_PACKAGE)


class ThermalWatchdogTests(unittest.TestCase):
    def test_normal_battery(self):
        self.assertEqual(parse_battery("  level: 83\n  temperature: 368\n"),(368,83))
        self.assertEqual(parse_battery("temperature: 420\nlevel: 40"),(420,40))

    def test_qa_processes_only_exact_names(self):
        sample=("USER PID PPID VSZ RSS WCHAN ADDR S NAME\n"
                "u0_a1 100 1 0 0 0 0 ru.neurostenographer.app.speakerbookqa\n"
                "u0_a1 101 1 0 0 0 0 ru.neurostenographer.app.speakerbookqa:diarization\n"
                "u0_a2 102 1 0 0 0 0 ru.neurostenographer.app.speakerbookqa.test\n"
                "u0_a3 103 1 0 0 0 0 ru.neurostenographer.app\n"
                "u0_a4 104 1 0 0 0 0 ru.neurostenographer.app.speakerbookqa_fake\n")
        self.assertEqual(remaining_qa_processes(sample),
                         sorted([QA_PACKAGE,QA_PACKAGE+":diarization",TEST_PACKAGE]))
        self.assertEqual(remaining_qa_processes("other 10 /system/bin/sh"),[])

    def test_unexpected_adb_exit_still_stops_qa(self):
        class EarlyExited:
            returncode=0
            def poll(self):return 0
            def wait(self,timeout=None):return 0
        def fake_popen(cmd,stdout,stderr):
            stdout.write("ADB client exited unexpectedly\\n")
            stdout.flush()
            return EarlyExited()
        with TemporaryDirectory() as directory:
            log=Path(directory)/"qa-run.log"
            cfg=SimpleNamespace(adb=Path("adb"),serial="FAKE",log=log,
                start_max_tenths=390,cutoff_tenths=420,poll_s=1,limit_s=20)
            with (patch.object(watchdog,"temperature",return_value=(350,85)),
                  patch.object(watchdog.subprocess,"Popen",side_effect=fake_popen),
                  patch.object(watchdog,"stop_qa",return_value=[
                      {"package":QA_PACKAGE,"success":True},
                      {"package":TEST_PACKAGE,"success":True}]) as stopped,
                  patch.object(watchdog,"verify_qa_stopped",return_value={
                      "verified":True,"stopped":True,"remaining":[]}) as verified):
                self.assertEqual(watchdog.run(cfg),1)
                stopped.assert_called_once_with(cfg.adb,cfg.serial)
                verified.assert_called_once_with(cfg.adb,cfg.serial)
                saved=json.loads(log.with_suffix(".status.json").read_text())
                self.assertEqual(saved["status"],"FAIL")
                self.assertTrue(saved["cleanup_verified"]["stopped"])

    def test_a_passing_runner_requires_confirmed_cleanup(self):
        class EarlyExited:
            returncode=0
            def poll(self):return 0
            def wait(self,timeout=None):return 0
        def fake_popen(cmd,stdout,stderr):
            stdout.write("OK (1 test)\\n")
            stdout.flush()
            return EarlyExited()
        with TemporaryDirectory() as directory:
            log=Path(directory)/"qa-run.log"
            cfg=SimpleNamespace(adb=Path("adb"),serial="FAKE",log=log,
                start_max_tenths=390,cutoff_tenths=420,poll_s=1,limit_s=20)
            with (patch.object(watchdog,"temperature",return_value=(350,85)),
                  patch.object(watchdog.subprocess,"Popen",side_effect=fake_popen),
                  patch.object(watchdog,"stop_qa",return_value=[
                      {"package":QA_PACKAGE,"success":False},
                      {"package":TEST_PACKAGE,"success":True}]),
                  patch.object(watchdog,"verify_qa_stopped",return_value={
                      "verified":False,"stopped":False,"remaining":[QA_PACKAGE]})):
                self.assertEqual(watchdog.run(cfg),1)
                saved=json.loads(log.with_suffix(".status.json").read_text())
                self.assertEqual(saved["status"],"CLEANUP_NOT_CONFIRMED")

    def test_allowed_cross_test_modes_and_no_other_package(self):
        for mode in ("repeat","differentSources","withoutModel"):
            cmd,name=watchdog.instrumentation_command(Path("adb"),"HONOR",
                                                         "cross",mode)
            self.assertEqual(cmd[-4:-1],["-e","qaMode",mode])
            self.assertEqual(cmd[-1],watchdog.RUNNER)
            self.assertEqual(name,
                "ru.neurostenographer.app.CrossWindowSpeakerBookDeviceTest")
            self.assertIn("-s",cmd)
        cmd,name=watchdog.instrumentation_command(Path("adb"),"HONOR")
        self.assertEqual(name,watchdog.TEST_CLASS)
        self.assertNotIn("qaMode",cmd)
        for case,mode in (("long","repeat"),("unknown",None),("cross","evil")):
            with self.assertRaises(ValueError):
                watchdog.instrumentation_command(Path("adb"),"HONOR",case,mode)

    def test_unavailable_or_corrupt(self):
        for text in ("level: 90", "temperature: 420", "temperature: 999\nlevel: 85",
                     "temperature: -1\nlevel: 90", "temperature: 440\nlevel: 120"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):parse_battery(text)


if __name__=="__main__":
    unittest.main()

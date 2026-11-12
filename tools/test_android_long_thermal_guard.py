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
    def test_short_power_route_is_only_solhigh_and_is_opt_in(self):
        command,name=watchdog.instrumentation_command(Path("adb"),"HONOR","power")
        self.assertEqual(name,"ru.neurostenographer.app.BatchPowerDeviceTest")
        self.assertEqual(command[-1],"ru.neurostenographer.app.solhigh.test/androidx.test.runner.AndroidJUnitRunner")
        self.assertEqual(command[-4:-1],["-e","batchPowerQa","honor_short"])
        with self.assertRaises(ValueError):
            watchdog.instrumentation_command(Path("adb"),"HONOR","power","repeat")
        with patch.object(watchdog,"adb_call",return_value=SimpleNamespace(returncode=0)) as adb:
            watchdog.stop_qa("adb","HONOR",power=True)
            self.assertEqual([c.args[-1] for c in adb.call_args_list],
                ["ru.neurostenographer.app.solhigh","ru.neurostenographer.app.solhigh.test"])
        self.assertEqual(watchdog.remaining_qa_processes(
            "x ru.neurostenographer.app\nx ru.neurostenographer.app.solhigh_fake\n"
            "x ru.neurostenographer.app.solhigh:diarization",power=True),
            ["ru.neurostenographer.app.solhigh:diarization"])

    def test_long_power_route_keeps_the_ordinary_qa_package(self):
        command,name=watchdog.instrumentation_command(Path("adb"),"HONOR","powerLong")
        self.assertEqual(name,"ru.neurostenographer.app.BatchLongPowerDeviceTest")
        self.assertEqual(command[-4:-1],["-e","batchPowerQa","honor_long"])
        self.assertEqual(command[-1],"ru.neurostenographer.app.solhigh.test/androidx.test.runner.AndroidJUnitRunner")
        with self.assertRaises(ValueError):
            watchdog.instrumentation_command(Path("adb"),"HONOR","powerLong","repeat")

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
                  patch.object(watchdog,"cpu_temperature",return_value={
                      "sensors_c":{"cluster0":35.0,"cluster1":37.0},
                      "max_c":37.0,"android_status":0}),
                  patch.object(watchdog.subprocess,"Popen",side_effect=fake_popen),
                  patch.object(watchdog,"stop_qa",return_value=[
                      {"package":QA_PACKAGE,"success":True},
                      {"package":TEST_PACKAGE,"success":True}]) as stopped,
                  patch.object(watchdog,"verify_qa_stopped",return_value={
                      "verified":True,"stopped":True,"remaining":[]}) as verified):
                self.assertEqual(watchdog.run(cfg),1)
                stopped.assert_called_once_with(cfg.adb,cfg.serial,power=False)
                verified.assert_called_once_with(cfg.adb,cfg.serial,power=False)
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
                  patch.object(watchdog,"cpu_temperature",return_value={
                      "sensors_c":{"cluster0":35.0,"cluster1":37.0},
                      "max_c":37.0,"android_status":0}),
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

    def test_parse_actual_honor_live_cpu_sensors_not_cached(self):
        source="""Thermal Status: 0
Cached temperatures:
    Temperature{mValue=90.0, mType=0, mName=cluster0, mStatus=0}
Current temperatures from HAL:
    Temperature{mValue=37.2, mType=1, mName=gpu, mStatus=0}
    Temperature{mValue=36.0, mType=0, mName=cluster0, mStatus=0}
    Temperature{mValue=41.4, mType=0, mName=cluster1, mStatus=0}
    Temperature{mValue=35.0, mType=2, mName=Battery, mStatus=0}
Current cooling devices from HAL:
"""
        t=watchdog.parse_cpu_thermal(source)
        self.assertEqual(t["sensors_c"],{"cluster0":36.0,"cluster1":41.4})
        self.assertEqual(t["max_c"],41.4)
        self.assertEqual(t["android_status"],0)

    def test_missing_unreliable_hal_fails_closed(self):
        basic="""Thermal Status: 0
Cached temperatures:
    Temperature{mValue=30.0, mType=0, mName=cluster0, mStatus=0}
"""
        for bad in (basic,
                    "Current temperatures from HAL:\\nThermal Status: 0",
                    "Thermal Status: 0\\nCurrent temperatures from HAL:\\n"
                    "Temperature{mValue=nan, mType=0, mName=cluster0, mStatus=0}",
                    "Thermal Status: 0\\nCurrent temperatures from HAL:\\n"
                    "Temperature{mValue=45.0, mType=1, mName=gpu, mStatus=0}",
                    "Thermal Status: 9\\nCurrent temperatures from HAL:\\n"
                    "Temperature{mValue=45.0, mType=0, mName=cluster0, mStatus=0}"):
            with self.subTest(bad=bad[:70]):
                with self.assertRaises(ValueError):
                    watchdog.parse_cpu_thermal(bad.replace(chr(92)+"n","\n"))

    def test_cpu_or_battery_or_android_severe_aborts(self):
        class Running:
            returncode=None
            def poll(self):return self.returncode
            def wait(self,timeout=None):
                self.returncode=0
                return 0
            def terminate(self):self.returncode=-15
            def kill(self):self.returncode=-9
        def fake_popen(cmd,stdout,stderr):
            stdout.write("INSTRUMENTATION_STATUS_CODE: 1\n")
            stdout.flush()
            return Running()
        healthy={"sensors_c":{"cluster0":35.0,"cluster1":39.0},
                 "max_c":39.0,"android_status":0}
        cases=[
            ("CPU",[(350,80),(360,80)],[healthy,
             {"sensors_c":{"cluster0":76.5,"cluster1":78.0},
              "max_c":78.0,"android_status":0}]),
            ("BATTERY",[(350,80),(450,80)],[healthy,healthy]),
            ("ANDROID_SEVERE",[(350,80),(370,80)],[healthy,
             {"sensors_c":{"cluster0":50.0,"cluster1":51.0},
              "max_c":51.0,"android_status":3}]),
        ]
        for cause,batteries,cpus in cases:
            with self.subTest(cause=cause),TemporaryDirectory() as directory:
                cfg=SimpleNamespace(adb=Path("adb"),serial="FAKE",
                    log=Path(directory)/"test.log",start_max_tenths=390,
                    cutoff_tenths=450,poll_s=1,limit_s=300)
                with (patch.object(watchdog,"temperature",side_effect=batteries),
                      patch.object(watchdog,"cpu_temperature",side_effect=cpus),
                      patch.object(watchdog.subprocess,"Popen",side_effect=fake_popen),
                      patch.object(watchdog.time,"sleep",return_value=None),
                      patch.object(watchdog,"stop_qa",return_value=[
                        {"package":QA_PACKAGE,"success":True},
                        {"package":TEST_PACKAGE,"success":True}]),
                      patch.object(watchdog,"verify_qa_stopped",return_value={
                        "verified":True,"remaining":[],"stopped":True})):
                    self.assertEqual(watchdog.run(cfg),1)
                report=json.loads(cfg.log.with_suffix(".status.json").read_text())
                self.assertEqual(report["status"],"THERMAL_ABORT")
                self.assertEqual(report["watchdog_cutoff_c"],45.0)
                self.assertEqual(report["cpu_cutoff_c"],78.0)
                self.assertTrue(report["cleanup_verified"]["stopped"])
                if cause=="CPU":self.assertEqual(report["trigger"]["cpu_max_c"],78.0)
                if cause=="BATTERY":self.assertEqual(report["trigger"]["battery_c"],45.0)
                if cause=="ANDROID_SEVERE":
                    self.assertEqual(report["trigger"]["android_thermal_status"],3)

    def test_cpu_sensor_severe_status_not_ignored(self):
        block="""Thermal Status: 0
Current temperatures from HAL:
 Temperature{mValue=55.0, mType=0, mName=cluster1, mStatus=3}
Current cooling devices from HAL:
"""
        out=watchdog.parse_cpu_thermal(block)
        self.assertEqual(out["max_c"],55.0)
        self.assertEqual(out["max_sensor_status"],3)

    def test_warning_does_not_abort_or_get_mislabeled_pass(self):
        class OnePoll:
            returncode=None
            polls=0
            def poll(self):
                self.polls+=1
                return None if self.polls==1 else 0
            def wait(self,timeout=None):
                self.returncode=0
                return 0
            def terminate(self):self.returncode=-15
            def kill(self):self.returncode=-9
        def fake_popen(cmd,stdout,stderr):
            stdout.write("No assertion result yet\\n")
            stdout.flush()
            return OnePoll()
        with TemporaryDirectory() as directory:
            config=SimpleNamespace(adb=Path("adb"),serial="FAKE",
                log=Path(directory)/"test.log",start_max_tenths=390,
                cutoff_tenths=450,poll_s=1,limit_s=300)
            cool={"sensors_c":{"cluster0":40.0,"cluster1":45.0},
                  "max_c":45.0,"android_status":0}
            hot={"sensors_c":{"cluster0":74.0,"cluster1":75.0},
                 "max_c":75.0,"android_status":0}
            with (patch.object(watchdog,"temperature",side_effect=[(350,85),(430,85)]),
                  patch.object(watchdog,"cpu_temperature",side_effect=[cool,hot]),
                  patch.object(watchdog.subprocess,"Popen",side_effect=fake_popen),
                  patch.object(watchdog.time,"sleep",return_value=None),
                  patch.object(watchdog,"stop_qa",return_value=[
                      {"package":QA_PACKAGE,"success":True},
                      {"package":TEST_PACKAGE,"success":True}]),
                  patch.object(watchdog,"verify_qa_stopped",return_value={
                      "verified":True,"stopped":True,"remaining":[]})):
                self.assertEqual(watchdog.run(config),1)
            evidence=json.loads(config.log.with_suffix(".status.json").read_text())
            self.assertEqual(evidence["status"],"FAIL")
            self.assertEqual(len(evidence["warnings"]),1)
            self.assertEqual(evidence["warnings"][0]["battery_c"],43.0)
            self.assertEqual(evidence["warnings"][0]["cpu_max_c"],75.0)
            self.assertEqual(evidence["max_cpu_temperature_c"],75.0)

    def test_lost_cpu_sensor_during_processing_aborts(self):
        class Active:
            returncode=None
            def poll(self):return self.returncode
            def wait(self,timeout=None):
                self.returncode=0
                return 0
            def terminate(self):self.returncode=-15
            def kill(self):self.returncode=-9
        with TemporaryDirectory() as directory:
            config=SimpleNamespace(adb=Path("adb"),serial="FAKE",
                log=Path(directory)/"test.log",start_max_tenths=390,
                cutoff_tenths=450,poll_s=1,limit_s=300)
            with (patch.object(watchdog,"temperature",side_effect=[(350,85),(360,85)]),
                  patch.object(watchdog,"cpu_temperature",side_effect=[
                      {"sensors_c":{"cluster0":35.0},"max_c":35.0,"android_status":0},
                      ValueError("HAL current CPU readings disappeared")]),
                  patch.object(watchdog.subprocess,"Popen",return_value=Active()),
                  patch.object(watchdog.time,"sleep",return_value=None),
                  patch.object(watchdog,"stop_qa",return_value=[
                      {"package":QA_PACKAGE,"success":True},
                      {"package":TEST_PACKAGE,"success":True}]),
                  patch.object(watchdog,"verify_qa_stopped",return_value={
                      "verified":True,"stopped":True,"remaining":[]})):
                self.assertEqual(watchdog.run(config),1)
            report=json.loads(config.log.with_suffix(".status.json").read_text())
            self.assertEqual(report["status"],"THERMAL_TELEMETRY_LOST_ABORT")
            self.assertTrue(report["cleanup_verified"]["stopped"])

    def test_unavailable_or_corrupt(self):
        for text in ("level: 90", "temperature: 420", "temperature: 999\nlevel: 85",
                     "temperature: -1\nlevel: 90", "temperature: 440\nlevel: 120"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):parse_battery(text)


if __name__=="__main__":
    unittest.main()

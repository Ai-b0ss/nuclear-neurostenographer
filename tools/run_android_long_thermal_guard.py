#!/usr/bin/env python3
"""Guarded ADB host runner for an optional 20+ minute HONOR QA test.

This script does NOT run as part of CI and must not be started when hot.
It supervises its own QA-only instrumentation and forcibly stops only its
two experimental packages if the phone reaches the thermal cutoff.
The instrumentation itself also checks battery temperature on device.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

QA_PACKAGE="ru.neurostenographer.app.speakerbookqa"
TEST_PACKAGE=QA_PACKAGE+".test"
RUNNER=TEST_PACKAGE+"/androidx.test.runner.AndroidJUnitRunner"
TEST_CLASS="ru.neurostenographer.app.LongContinuousSpeakerBookDeviceTest"


def parse_battery(text):
    temp=re.search(r"(?m)^\s*temperature:\s*(\d+)\s*$",text)
    level=re.search(r"(?m)^\s*level:\s*(\d+)\s*$",text)
    if not temp or not level:
        raise ValueError("ADB battery temperature/level unavailable")
    t=int(temp.group(1));battery=int(level.group(1))
    if not (100<=t<=650 and 0<=battery<=100):
        raise ValueError("ADB battery reading out of plausible range")
    return t,battery


def adb_call(adb,serial,*args,timeout=12):
    return subprocess.run([str(adb),"-s",serial,*args],
        capture_output=True,text=True,errors="replace",timeout=timeout)


def temperature(adb,serial):
    p=adb_call(adb,serial,"shell","dumpsys","battery")
    if p.returncode:raise RuntimeError("ADB battery query failed: "+p.stderr[-180:])
    return parse_battery(p.stdout)


def parse_cpu_thermal(text):
    """Read CURRENT Android Thermal HAL CPU sensors (type 0), never cached values.

    This works on stock HONOR via dumpsys thermalservice, unlike
    /sys/class/thermal which is inaccessible without root on this phone.
    """
    current=re.search(
        r"Current temperatures from HAL:\s*\n(?P<body>.*?)(?:Current cooling devices from HAL:|\Z)",
        text,re.IGNORECASE | re.DOTALL)
    if current is None:
        raise ValueError("Thermal HAL current sensor block unavailable")
    values={}
    per_sensor_status={}
    for match in re.finditer(r"Temperature\{([^}]+)\}",current.group("body")):
        fields=dict(re.findall(r"\b(mValue|mType|mName|mStatus)=([^,}]+)",match.group(1)))
        if fields.get("mType")!="0":
            continue
        try:
            name=fields["mName"].strip()
            c=float(fields["mValue"])
            status=int(fields["mStatus"])
        except (KeyError,ValueError,OverflowError) as exc:
            raise ValueError("Invalid CPU HAL reading") from exc
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,48}",name) or not (0<=c<=125) or not 0<=status<=6:
            raise ValueError("Out-of-range CPU HAL reading")
        if name in values:
            raise ValueError("Duplicate live CPU sensor: "+name)
        values[name]=c
        per_sensor_status[name]=status
    if not values:
        raise ValueError("No current CPU sensors in Thermal HAL")
    match=re.search(r"(?m)^Thermal Status:\s*(\d+)\s*$",text)
    if match is None or not 0<=int(match.group(1))<=6:
        raise ValueError("Android thermal status missing/invalid")
    return {"sensors_c":values,"max_c":max(values.values()),
            "sensor_status":per_sensor_status,
            "max_sensor_status":max(per_sensor_status.values()),
            "android_status":int(match.group(1))}


def cpu_temperature(adb,serial):
    p=adb_call(adb,serial,"shell","dumpsys","thermalservice")
    if p.returncode:
        raise RuntimeError("ADB Thermal HAL query failed: "+p.stderr[-180:])
    return parse_cpu_thermal(p.stdout)


def stop_qa(adb,serial,*,power=False):
    results=[]
    packages=("ru.neurostenographer.app.solhigh", "ru.neurostenographer.app.solhigh.test") if power else (QA_PACKAGE,TEST_PACKAGE)
    for pkg in packages:
        try:
            p=adb_call(adb,serial,"shell","am","force-stop",pkg,timeout=8)
            results.append({"package":pkg,"success":p.returncode==0})
        except Exception as e:
            results.append({"package":pkg,"success":False,"error":str(e)[:150]})
    return results


def remaining_qa_processes(ps_text,*,power=False):
    """Return only exact QA package names or their secondary processes."""
    found=[]
    package="ru.neurostenographer.app.solhigh" if power else QA_PACKAGE
    test_package=package+".test"
    for line in ps_text.splitlines():
        parts=line.split()
        if not parts:
            continue
        name=parts[-1]
        if (name in (package, test_package) or
                name.startswith(package+":") or
                name.startswith(test_package+":")):
            found.append(name)
    return sorted(set(found))


def verify_qa_stopped(adb,serial,*,power=False):
    p=adb_call(adb,serial,"shell","ps","-A")
    if p.returncode:
        return {"verified":False,"error":"Cannot inspect device process table"}
    running=remaining_qa_processes(p.stdout,power=power)
    return {"verified":True,"remaining":running,"stopped":not running}


def instrumentation_command(adb, serial, test_case="long", qa_mode=None):
    # Restricted to explicit QA-only JUnit classes in the isolated application.
    cases={
        "long":TEST_CLASS,
        "power":"ru.neurostenographer.app.BatchPowerDeviceTest",
        "cross":"ru.neurostenographer.app.CrossWindowSpeakerBookDeviceTest",
    }
    if test_case not in cases:
        raise ValueError("Invalid QA test class")
    if qa_mode is not None and (
        test_case!="cross" or qa_mode not in ("repeat","differentSources","withoutModel")):
        raise ValueError("Invalid QA test mode")
    command=[str(adb),"-s",serial,"shell","am","instrument",
             "-w","-r","-e","class",cases[test_case]]
    if qa_mode is not None:
        command.extend(["-e","qaMode",qa_mode])
    if test_case=="power":
        command.extend(["-e","batchPowerQa","honor_short"])
        command.append("ru.neurostenographer.app.solhigh.test/androidx.test.runner.AndroidJUnitRunner")
    else:
        command.append(RUNNER)
    return command,cases[test_case]


def run(a):
    power=getattr(a,"test_case","long")=="power"
    battery_cutoff=int(getattr(a,"cutoff_tenths",450))
    battery_start=int(getattr(a,"start_max_tenths",390))
    battery_warning=int(getattr(a,"battery_warning_tenths",min(430,battery_cutoff-10)))
    cpu_cutoff=float(getattr(a,"cpu_cutoff_c",78.0))
    cpu_warning=float(getattr(a,"cpu_warning_c",75.0))
    cpu_start=float(getattr(a,"cpu_start_max_c",65.0))
    if not (100<=battery_start<battery_warning<battery_cutoff<=500):
        raise ValueError("invalid battery starting/warning/cutoff temperatures")
    if not (30<=cpu_start<cpu_warning<cpu_cutoff<=85):
        raise ValueError("invalid CPU starting/warning/cutoff temperatures")
    if a.poll_s<1 or a.poll_s>10 or not 20<=a.limit_s<=2400:
        raise ValueError("invalid watchdog interval/duration")
    first,level=temperature(a.adb,a.serial)
    thermal=cpu_temperature(a.adb,a.serial)
    if first>=battery_start:
        raise RuntimeError("Refusing sustained device load: battery "+str(first/10)+" C")
    if level<40:
        raise RuntimeError("Refusing device load: battery "+str(level)+"%")
    if thermal["max_c"]>=cpu_start:
        raise RuntimeError("Refusing sustained device load: CPU "+str(thermal["max_c"])+" C")
    if thermal["android_status"]>=3 or thermal.get("max_sensor_status",0)>=3:
        raise RuntimeError("Refusing load: Android reports severe thermal status")
    log=Path(a.log).resolve()
    log.parent.mkdir(parents=True,exist_ok=True)
    if log.exists():raise FileExistsError("Log already exists: "+str(log))
    command,test_name=instrumentation_command(a.adb,a.serial,
        getattr(a,"test_case","long"),getattr(a,"qa_mode",None))
    report={"test":test_name,"qa_only":True,
        "qa_mode":getattr(a,"qa_mode",None),
        "initial_temperature_c":first/10,
        "initial_battery_percent":level,"max_temperature_c":first/10,
        "watchdog_cutoff_c":battery_cutoff/10,
        "battery_warning_c":battery_warning/10,
        "initial_cpu_temperatures_c":thermal["sensors_c"],
        "max_cpu_temperature_c":thermal["max_c"],
        "max_cpu_temperatures_by_sensor_c":dict(thermal["sensors_c"]),
        "cpu_warning_c":cpu_warning,"cpu_cutoff_c":cpu_cutoff,
        "initial_android_thermal_status":thermal["android_status"],
        "max_android_thermal_status":thermal["android_status"],
        "max_cpu_sensor_status":thermal.get("max_sensor_status",0),
        "status":"RUNNING","warnings":[]}
    started=time.monotonic()
    proc=None
    try:
        with log.open("w",encoding="utf8") as handle:
            proc=subprocess.Popen(command,stdout=handle,stderr=subprocess.STDOUT)
            while proc.poll() is None:
                time.sleep(a.poll_s)
                if time.monotonic()-started>a.limit_s:
                    report["status"]="HOST_TIMEOUT_ABORT"
                    report["forced_stop"]=stop_qa(a.adb,a.serial,power=power)
                    break
                try:
                    t,level=temperature(a.adb,a.serial)
                    thermal=cpu_temperature(a.adb,a.serial)
                except Exception as e:
                    report["status"]="THERMAL_TELEMETRY_LOST_ABORT"
                    report["error"]=type(e).__name__+": "+str(e)[:180]
                    report["forced_stop"]=stop_qa(a.adb,a.serial,power=power)
                    break
                report["max_temperature_c"]=max(report["max_temperature_c"],t/10)
                report["max_cpu_temperature_c"]=max(report["max_cpu_temperature_c"],thermal["max_c"])
                report["max_android_thermal_status"]=max(
                    report["max_android_thermal_status"],thermal["android_status"])
                report["max_cpu_sensor_status"]=max(
                    report["max_cpu_sensor_status"],thermal.get("max_sensor_status",0))
                for name,c in thermal["sensors_c"].items():
                    report["max_cpu_temperatures_by_sensor_c"][name]=max(
                        report["max_cpu_temperatures_by_sensor_c"].get(name,c),c)
                if (t>=battery_cutoff or thermal["max_c"]>=cpu_cutoff or
                    thermal["android_status"]>=3 or thermal.get("max_sensor_status",0)>=3):
                    report["status"]="THERMAL_ABORT"
                    report["trigger"]={
                        "battery_c":t/10,"cpu_max_c":thermal["max_c"],
                        "cpu_sensors_c":thermal["sensors_c"],
                        "android_thermal_status":thermal["android_status"],
                        "max_cpu_sensor_status":thermal.get("max_sensor_status",0)}
                    report["forced_stop"]=stop_qa(a.adb,a.serial,power=power)
                    break
                if (t>=battery_warning or thermal["max_c"]>=cpu_warning or
                    thermal["android_status"]>=2 or thermal.get("max_sensor_status",0)>=2):
                    warning={
                        "elapsed_s":round(time.monotonic()-started,1),
                        "battery_c":t/10,"cpu_max_c":thermal["max_c"],
                        "android_status":thermal["android_status"]}
                    report["warnings"].append(warning)
                    print("THERMAL_WARNING "+json.dumps(warning),flush=True)
            try:proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                report["forced_stop"]=stop_qa(a.adb,a.serial,power=power)
                proc.terminate()
                try:proc.wait(timeout=4)
                except subprocess.TimeoutExpired:proc.kill()
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=4)
            except subprocess.TimeoutExpired:proc.kill()
        report["wall_seconds"]=round(time.monotonic()-started,2)
        report["instrumentation_exit_code"]=proc.returncode if proc else None
        if report["status"]=="RUNNING":
            tail=log.read_text(encoding="utf8",errors="replace")[-4000:]
            report["status"]="PASS" if ("OK (1 test)" in tail and
                 "FAILURES!!!" not in tail and proc.returncode==0) else "FAIL"
        # Always force-stop our isolated QA packages, including when adb's
        # local client exits prematurely while native Android workers remain.
        # Never force-stop the ordinary product application.
        report["forced_stop"]=stop_qa(a.adb,a.serial,power=power)
        try:
            report["cleanup_verified"]=verify_qa_stopped(a.adb,a.serial,power=power)
        except Exception as cleanup_error:
            report["cleanup_verified"]={
                "verified":False,"error":type(cleanup_error).__name__+
                ": "+str(cleanup_error)[:160]}
        if report["status"]=="PASS" and (
            not all(x["success"] for x in report["forced_stop"]) or
            not report["cleanup_verified"].get("stopped",False)):
            report["status"]="CLEANUP_NOT_CONFIRMED"
        summary=log.with_suffix(".status.json")
        summary.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf8")
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return 0 if report["status"]=="PASS" else 1


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb",required=True,type=Path)
    parser.add_argument("--serial",required=True)
    parser.add_argument("--log",required=True,type=Path)
    parser.add_argument("--cutoff-tenths",type=int,default=450)
    parser.add_argument("--start-max-tenths",type=int,default=390)
    parser.add_argument("--battery-warning-tenths",type=int,default=430)
    parser.add_argument("--cpu-cutoff-c",type=float,default=78.0)
    parser.add_argument("--cpu-warning-c",type=float,default=75.0)
    parser.add_argument("--cpu-start-max-c",type=float,default=65.0)
    parser.add_argument("--poll-s",type=float,default=2)
    parser.add_argument("--limit-s",type=int,default=900)
    parser.add_argument("--test-case",choices=("long","cross","power"),default="long")
    parser.add_argument("--qa-mode",choices=("repeat","differentSources","withoutModel"),
                        default=None)
    args=parser.parse_args()
    try:sys.exit(run(args))
    except Exception as e:
        print("QA TEST NOT STARTED OR FAILED: "+str(e),file=sys.stderr)
        sys.exit(2)

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


def stop_qa(adb,serial):
    results=[]
    for pkg in (QA_PACKAGE,TEST_PACKAGE):
        try:
            p=adb_call(adb,serial,"shell","am","force-stop",pkg,timeout=8)
            results.append({"package":pkg,"success":p.returncode==0})
        except Exception as e:
            results.append({"package":pkg,"success":False,"error":str(e)[:150]})
    return results


def run(a):
    if not (100<=a.start_max_tenths<a.cutoff_tenths<=450):
        raise ValueError("start temperature must be below cutoff")
    if a.poll_s<1 or a.poll_s>10 or not 20<=a.limit_s<=2400:
        raise ValueError("invalid watchdog interval/duration")
    first,level=temperature(a.adb,a.serial)
    if first>=a.start_max_tenths:
        raise RuntimeError("Refusing sustained device load: battery "+str(first/10)+" C")
    if level<40:
        raise RuntimeError("Refusing device load: battery "+str(level)+"%")
    log=Path(a.log).resolve()
    log.parent.mkdir(parents=True,exist_ok=True)
    if log.exists():raise FileExistsError("Log already exists: "+str(log))
    command=[str(a.adb),"-s",a.serial,"shell","am","instrument",
        "-w","-r","-e","class",TEST_CLASS,RUNNER]
    report={"test":TEST_CLASS,"qa_only":True,"initial_temperature_c":first/10,
        "initial_battery_percent":level,"max_temperature_c":first/10,
        "watchdog_cutoff_c":a.cutoff_tenths/10,"status":"RUNNING"}
    started=time.monotonic()
    proc=None
    try:
        with log.open("w",encoding="utf8") as handle:
            proc=subprocess.Popen(command,stdout=handle,stderr=subprocess.STDOUT)
            while proc.poll() is None:
                time.sleep(a.poll_s)
                if time.monotonic()-started>a.limit_s:
                    report["status"]="HOST_TIMEOUT_ABORT"
                    report["forced_stop"]=stop_qa(a.adb,a.serial)
                    break
                try:t,level=temperature(a.adb,a.serial)
                except Exception as e:
                    report["status"]="ADB_LOST_ABORT"
                    report["error"]=str(e)[:180]
                    report["forced_stop"]=stop_qa(a.adb,a.serial)
                    break
                report["max_temperature_c"]=max(report["max_temperature_c"],t/10)
                if t>=a.cutoff_tenths:
                    report["status"]="THERMAL_ABORT"
                    report["forced_stop"]=stop_qa(a.adb,a.serial)
                    break
            try:proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                report["forced_stop"]=stop_qa(a.adb,a.serial)
                proc.terminate()
                try:proc.wait(timeout=4)
                except subprocess.TimeoutExpired:proc.kill()
    finally:
        if proc is not None and proc.poll() is None:
            stop_qa(a.adb,a.serial)
            proc.terminate()
        report["wall_seconds"]=round(time.monotonic()-started,2)
        report["instrumentation_exit_code"]=proc.returncode if proc else None
        if report["status"]=="RUNNING":
            tail=log.read_text(encoding="utf8",errors="replace")[-4000:]
            report["status"]="PASS" if ("OK (1 test)" in tail and
                 "FAILURES!!!" not in tail and proc.returncode==0) else "FAIL"
        summary=log.with_suffix(".status.json")
        summary.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf8")
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return 0 if report["status"]=="PASS" else 1


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb",required=True,type=Path)
    parser.add_argument("--serial",required=True)
    parser.add_argument("--log",required=True,type=Path)
    parser.add_argument("--cutoff-tenths",type=int,default=420)
    parser.add_argument("--start-max-tenths",type=int,default=390)
    parser.add_argument("--poll-s",type=float,default=2)
    parser.add_argument("--limit-s",type=int,default=900)
    args=parser.parse_args()
    try:sys.exit(run(args))
    except Exception as e:
        print("QA TEST NOT STARTED OR FAILED: "+str(e),file=sys.stderr)
        sys.exit(2)

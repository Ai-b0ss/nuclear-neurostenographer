"""Render authored processing UI states only on an isolated x86_64 cloud emulator."""
import argparse,json,math,re,subprocess,tarfile,time,uuid
from pathlib import Path
from run_speakerbook_emulator_qa import verify_emulator

ROOT=Path(__file__).resolve().parents[1]
PACKAGE="ru.neurostenographer.app.layoutqa"
TEST=PACKAGE+".test"

def accepted_result(output,record,run_id):
    if not re.search(r"OK\s*\(1 test\)",output) or record.get("status")!="PASS" or record.get("run_id")!=run_id:
        return False
    if record.get("execution_environment")!="ANDROID_X86_64_EMULATOR_NOT_PHONE" or record.get("scope")!="RENDERED_PROCESSING_UI_STATES_NO_INFERENCE":
        return False
    rows=record.get("rows",[])
    try:
        keys=[(round(float(x["font_scale"]),1),x["state_index"]) for x in rows]
        if len(keys)!=21 or set(keys)!={(scale,i) for scale in (1.0,1.3,2.0) for i in range(7)}:
            return False
        if any(x["overflow_count"]!=0 or not math.isfinite(float(x["progress_top_px"])) for x in rows):
            return False
        for scale in (1.0,1.3,2.0):
            tops=[float(row["progress_top_px"]) for row in rows if round(float(row["font_scale"]),1)==scale]
            if max(tops)-min(tops)>2.0:return False
    except (KeyError,ValueError,TypeError):return False
    return True


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adb",default="adb")
    p.add_argument("--aapt",required=True)
    p.add_argument("--output",type=Path,default=ROOT/".local/qa-processing-layout-current")
    a=p.parse_args()
    listing=subprocess.check_output([a.adb,"devices"],text=True)
    targets=[line.split()[0] for line in listing.splitlines()[1:]
             if len(line.split())==2 and line.split()[1]=="device" and re.fullmatch(r"emulator-\d+",line.split()[0])]
    if len(targets)!=1:p.error("Exactly one emulator is required; physical targets are never selected")
    serial=targets[0]
    def adb(*parts,timeout=30,check=True):
        return subprocess.run([a.adb,"-s",serial,*map(str,parts)],capture_output=True,
                              encoding="utf8",errors="replace",check=check,timeout=timeout)
    verify_emulator(serial,adb("shell","getprop","ro.kernel.qemu").stdout,
                    adb("shell","getprop","ro.product.cpu.abi").stdout)
    if not a.output.resolve().is_relative_to((ROOT/".local").resolve()):p.error("Output must stay in .local")
    a.output.mkdir(parents=True,exist_ok=True)
    state={"status":"RUNNING","run_id":uuid.uuid4().hex,"execution_environment":"ANDROID_X86_64_EMULATOR_NOT_PHONE",
           "physical_device_accessed":False,"scope":"RENDERED_UI_STATES_NO_INFERENCE"}
    def save():(a.output/"summary.json").write_text(json.dumps(state,indent=2)+"\n",encoding="utf8")
    save();began=time.monotonic()
    try:
        for apk,name in [(ROOT/"app/build/outputs/apk/debug/app-debug.apk",PACKAGE),
                         (ROOT/"app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk",TEST)]:
            info=subprocess.check_output([a.aapt,"dump","badging",str(apk)],text=True)
            if not info.startswith("package: name='"+name+"'"):raise ValueError("Unexpected QA APK package")
            adb("install","-r",apk,timeout=120)
        adb("shell","run-as",PACKAGE,"rm","-rf","files/layout-qa")
        test=adb("shell","am","instrument","-w","-r","-e","class",
                 "ru.neurostenographer.app.ProcessingLayoutTest","-e","layoutRunId",state["run_id"],
                 TEST+"/androidx.test.runner.AndroidJUnitRunner",timeout=240,check=False)
        (a.output/"instrumentation.txt").write_text(test.stdout+test.stderr,encoding="utf8")
        record=json.loads(adb("shell","run-as",PACKAGE,"cat","files/layout-qa/result.json").stdout)
        state["record"]=record
        if not accepted_result(test.stdout,record,state["run_id"]):
            raise AssertionError("Current layout test did not pass: "+record.get("message",test.stdout[-1200:]))
        state["status"]="PASS"
    except BaseException as error:
        state.update(status="FAIL",error=type(error).__name__,message=str(error)[:1800]);raise
    finally:
        try:
            archive=a.output/"screenshots.tar"
            with archive.open("wb") as stream:
                pulled=subprocess.run([a.adb,"-s",serial,"exec-out","run-as",PACKAGE,"tar","-C","files","-cf","-","layout-qa"],
                                      stdout=stream,stderr=subprocess.PIPE,timeout=20)
            if pulled.returncode==0:
                with tarfile.open(archive) as tar:
                    for item in tar:
                        parts=Path(item.name).parts
                        if item.isfile() and len(parts)==2 and parts[0]=="layout-qa" and Path(parts[1]).suffix in (".png",".json"):
                            data=tar.extractfile(item)
                            if data is not None:(a.output/parts[1]).write_bytes(data.read())
            archive.unlink(missing_ok=True)
        except Exception as error:state["artifact_error"]=type(error).__name__
        errors=[]
        for name in (PACKAGE,TEST):
            try:
                if adb("shell","am","force-stop",name,check=False).returncode:errors.append(name)
            except Exception:errors.append(name)
        try:
            names=adb("shell","ps","-A","-o","NAME").stdout.splitlines()
            if any(n.strip() in (PACKAGE,TEST) or n.strip().startswith(PACKAGE+":") for n in names):errors.append("Remaining QA process")
        except Exception:errors.append("Cleanup verification unavailable")
        state["cleanup_verified"]=not errors
        state["wall_seconds"]=round(time.monotonic()-began,3)
        if errors:state.update(status="FAIL",cleanup_errors=errors)
        save();print(json.dumps(state,indent=2))
    if state["status"]!="PASS":raise RuntimeError("Layout QA cleanup failed")

if __name__=="__main__":main()

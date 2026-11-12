"""Measure product C2 CPU time with fixed ORT1.17.1, no phone access."""
import argparse,json,os,statistics,subprocess
from pathlib import Path
from run_host import ROOT,HARNESS,JAVA,MODEL,ORT_SHA,PINS,sha
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wav",type=Path,required=True)
    ap.add_argument("--output",type=Path,default=ROOT/".local/batch-runtime-current")
    ap.add_argument("--java",default=str(JAVA))
    ap.add_argument("--harness",type=Path,default=HARNESS)
    ap.add_argument("--model",type=Path,default=MODEL)
    a=ap.parse_args()
    if not a.output.resolve().is_relative_to((ROOT/".local").resolve()):ap.error("Output must stay in .local")
    a.output.mkdir(parents=True,exist_ok=True)
    summary=a.output/"summary.json"
    state={"schema":"batch-runtime-host-v1","status":"RUNNING","phone_accessed":False}
    summary.write_text(json.dumps(state),"utf8")
    ort=a.harness/"onnxruntime-1.17.1.jar"
    if sha(ort)!=ORT_SHA:raise ValueError("ORT pin mismatch")
    for name,wanted in PINS.items():
        if sha(a.model/name)!=wanted:raise ValueError("Model pin mismatch")
    sources=sorted((ROOT/"core/src/main/kotlin/ru/neurostenographer/core").glob("*.kt"))
    sources+=sorted((ROOT/"app/src/nemotron/java/ru/neurostenographer/core").glob("*.kt"))
    sources+=[ROOT/"tools/c2pp/MeasureRuntime.kt"]
    cp=os.pathsep.join([str(a.harness/"kotlin/kotlin-stdlib.jar"),str(ort)])
    classes=a.output/"classes";classes.mkdir(exist_ok=True)
    subprocess.run([a.java,"-cp",str(a.harness/"kotlin/*"),"org.jetbrains.kotlin.cli.jvm.K2JVMCompiler",
        "-no-stdlib","-no-reflect","-jvm-target","17","-classpath",cp,"-d",str(classes),*map(str,sources)],check=True)
    subprocess.run([a.java,"-Xmx2g","-cp",os.pathsep.join([str(classes),cp]),
        "ru.neurostenographer.tools.MeasureRuntimeKt",str(a.model),str(a.wav),str(a.output)],check=True)
    raw=json.loads((a.output/"measurements.json").read_text("utf8"))
    modes={}
    for mode in ["four_spin","four_sleep","two_sleep"]:
        rows=[r for r in raw["rows"] if r["mode"]==mode]
        if len(rows)!=3 or any(r["cpu_ms"]<0 or r["wall_ms"]<=0 for r in rows):raise ValueError("Invalid measurements")
        if not all(r["equal_ms_turns"] for r in rows):raise ValueError("Diarization changed")
        modes[mode]={"median_wall_ms":statistics.median(r["wall_ms"] for r in rows),
            "median_cpu_ms":statistics.median(r["cpu_ms"] for r in rows),
            "median_idle200_cpu_ms":statistics.median(r["idle200_cpu_ms"] for r in rows),
            "all_ms_turns_equal":all(r["equal_ms_turns"] for r in rows)}
    state.update(status="COMPLETED",audio_ms=raw["audio_ms"],modes=modes,rows=raw["rows"],
        input_wav_sha256=sha(a.wav),model_pins=PINS,ort_sha256=ORT_SHA,
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources},
        limitations=["Windows CPU process time is not phone battery energy or temperature.",
        "One fixed public clip, three rotated measured rounds after warmup; no statistical population claim.",
        "Model weights, two-pass product logic and postprocessing unchanged."])
    summary.write_text(json.dumps(state,indent=2)+"\n","utf8")
    print("SUMMARY",json.dumps(modes),flush=True)
if __name__=="__main__":main()

"""Build a task-only app_process DEX probe; never creates or installs a contest APK."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from common import REPO,LOCAL,owned,fetch,sha,write_json
from build_host import build

ORT_URL='https://repo1.maven.org/maven2/com/microsoft/onnxruntime/onnxruntime-android/1.17.1/onnxruntime-android-1.17.1.aar'
ORT_SHA='35fc867b4d50942da3058f196d74c5669b4b34228794702cf15a05a4bd0b77c4'
SHERPA_SHA='771fda6a4abf845a6f84f48e05e887fdf159671beb88cbc9aae327806511c1c8'

def prepare(jdk,sdk,sherpa,out=None):
    out=owned(out or LOCAL/'phone');h=LOCAL/'harness'
    fetch(ORT_URL,out/'ort-android.aar',ORT_SHA)
    if sha(sherpa)!=SHERPA_SHA:raise ValueError('Contest AAR pin mismatch')
    native=out/'native';native.mkdir(exist_ok=True)
    with zipfile.ZipFile(out/'ort-android.aar') as z:
        (out/'ort-classes.jar').write_bytes(z.read('classes.jar'))
        (native/'libonnxruntime4j_jni.so').write_bytes(z.read('jni/arm64-v8a/libonnxruntime4j_jni.so'))
    with zipfile.ZipFile(sherpa) as z:
        (out/'sherpa-classes.jar').write_bytes(z.read('classes.jar'))
        for name in ('libonnxruntime.so','libsherpa-onnx-jni.so'):(native/name).write_bytes(z.read('jni/arm64-v8a/'+name))
    classes=out/'classes';classes.mkdir(exist_ok=True)
    subprocess.run([str(jdk/'bin/javac.exe'),'--release','8','-cp',str(out/'ort-classes.jar'),'-d',str(classes),str(REPO/'tools/overlap_research/VoxLockProbe.java')],check=True)
    with zipfile.ZipFile(out/'probe-classes.jar','w') as z:
        for p in classes.rglob('*.class'):z.write(p,p.relative_to(classes).as_posix())
    dex=out/'dex';dex.mkdir(exist_ok=True)
    command=[str(jdk/'bin/java.exe'),'-Djava.io.tmpdir='+str(owned(out/'tmp')),'-cp',str(sdk/'build-tools/35.0.0/lib/d8.jar'),
             'com.android.tools.r8.D8','--release','--min-api','26','--lib',str(sdk/'platforms/android-35/android.jar'),'--output',str(dex)]
    jars=[out/'probe-classes.jar',h/'overlap-host.jar',out/'ort-classes.jar',out/'sherpa-classes.jar',h/'kotlin/kotlin-stdlib.jar']
    subprocess.run(command+list(map(str,jars)),check=True)
    with zipfile.ZipFile(out/'probe-dex.jar','w') as z:
        for p in dex.glob('*.dex'):z.write(p,p.name)
    write_json(out/'build.json',dict(scope='Task-only DEX app_process, no APK replacement',dex_sha256=sha(out/'probe-dex.jar'),dex_bytes=(out/'probe-dex.jar').stat().st_size,
        ort_aar_sha256=ORT_SHA,sherpa_aar_sha256=SHERPA_SHA,native={p.name:sha(p) for p in native.glob('*.so')},
        java_source_sha256=sha(REPO/'tools/overlap_research/VoxLockProbe.java'),kotlin_source_sha256=sha(REPO/'tools/overlap_research/OverlapHost.kt'),
        apk_delta='NOT_BUILT',models_bytes=77584388))
    print('PHONE PROBE BUILT',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--jdk',type=Path,required=True);p.add_argument('--sdk',type=Path,required=True);p.add_argument('--sherpa',type=Path,required=True);p.add_argument('--out',type=Path);a=p.parse_args();prepare(a.jdk,a.sdk,a.sherpa,a.out)

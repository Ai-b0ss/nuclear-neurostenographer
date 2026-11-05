"""Compile production app A3/C2 plus an isolated research entry point and core tests."""
import argparse
import os
from pathlib import Path
import subprocess
from common import REPO, LOCAL, owned, sha, write_json

def build(java):
    h=owned(LOCAL/'harness'); tmp=owned(LOCAL/'tmp')
    stub=h/'Stubs.kt'
    stub.write_text('package ru.neurostenographer.app\nobject BuildConfig { val ASR_A3 = true }\n',encoding='utf-8')
    asset=h/'AssetManager.kt'; asset.write_text('package android.content.res\nclass AssetManager\n',encoding='utf-8')
    compiler=[str(java),'-Djava.io.tmpdir='+str(tmp),'-cp',str(h/'kotlin/*'),'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-no-stdlib','-no-reflect','-nowarn','-jvm-target','17']
    core=sorted((REPO/'core/src/main/kotlin/ru/neurostenographer/core').glob('*.kt'))
    app=REPO/'app/src/main/java/ru/neurostenographer/app'
    sources=core+[app/(n+'.kt') for n in ('OfflineAsr','OfflineDiarization','AsrModelSpec','InferenceThreads')]
    sources += list((REPO/'app/src/nemotron/java').rglob('*.kt'))+[stub,REPO/'tools/overlap_research/OverlapHost.kt']
    cp=os.pathsep.join(str(h/p) for p in ['kotlin/kotlin-stdlib.jar','classes.jar','onnxruntime-1.17.1.jar'])
    subprocess.run(compiler+['-classpath',cp,'-d',str(h/'placeholder.jar'),str(asset)],check=True)
    cp += os.pathsep+str(h/'placeholder.jar')
    subprocess.run(compiler+['-classpath',cp,'-d',str(h/'overlap-host.jar')]+list(map(str,sources)),check=True)
    tests=sorted((REPO/'core/src/test/kotlin').rglob('*.kt'))
    subprocess.run(compiler+['-classpath',cp,'-d',str(h/'core-tests.jar')]+list(map(str,core+tests)),check=True)
    subprocess.run([str(java),'-Djava.io.tmpdir='+str(tmp),'-cp',str(h/'core-tests.jar')+os.pathsep+cp,'ru.neurostenographer.core.TranscriptCoreTestKt'],check=True)
    report=dict(java=str(java),host_jar_sha256=sha(h/'overlap-host.jar'),sources={str(p.relative_to(REPO)):sha(p) for p in sources if p.is_relative_to(REPO) and not p.is_relative_to(LOCAL)},core_tests='PASS')
    write_json(LOCAL/'build.json',report)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--java',type=Path,required=True);a=p.parse_args();build(a.java)

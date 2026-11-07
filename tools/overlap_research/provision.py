"""Stage audited VoxLock v2 source/weights; copy only verified compiler/JNI inputs.

No pip install, app runtime upgrade, or shared cache mutation. Existing Python
NumPy/ORT packages are used read-only and their actual versions recorded.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from common import REPO, LOCAL, owned, fetch, sha, write_json

SOURCE_REV = '48b9a71e9b6ce853670c9a4dbc64ddb532638d53'
MODEL_REV = '2413b292bc2c337bfc19a9802aaf3e011e68e9c4'
PINS = {
    'core.py': ('https://raw.githubusercontent.com/arbazsiddiqui/voxlock/' + SOURCE_REV + '/voxlock/core.py', '0a8e21ae8c74b169a279ced36e9cec8a14cb180c8b46bb6b21632ced9a70df98'),
    'LICENSE': ('https://raw.githubusercontent.com/arbazsiddiqui/voxlock/' + SOURCE_REV + '/LICENSE', 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30'),
    'NOTICE': ('https://raw.githubusercontent.com/arbazsiddiqui/voxlock/' + SOURCE_REV + '/NOTICE', '245ce5d9925659adae2f664a2f4886f11dceabc1c9a99d151a9140afecb0d457'),
    'enroll.onnx': ('https://huggingface.co/arbazsiddiqui/voxlock/resolve/' + MODEL_REV + '/onnx/v2/enroll.onnx', '81f305c9b7a32f13d1401f53bb4c6301826a607c9e807e60912f36ef1b9fae29'),
    'chunk_int8.onnx': ('https://huggingface.co/arbazsiddiqui/voxlock/resolve/' + MODEL_REV + '/onnx/v2/chunk_int8.onnx', 'c50ffdc8d723fd4f91cb08889f3d0143491f95967b705f35c444a0b4afe88172'),
}

def stage_harness(existing=None):
    sys.path.insert(0, str(REPO / 'tools'))
    from run_host_inference import COMPILER, NATIVE, MAVEN
    from provision_asr import LOCK
    h = owned(LOCAL / 'harness')
    def input_file(relative,url,digest):
        p=existing/relative if existing else h/relative
        if not existing:fetch(url,p,digest)
        return p
    for name, (url, digest) in COMPILER.items():
        p = input_file(Path('kotlin')/(name+'.jar'),MAVEN+url,digest)
        if sha(p) != digest:
            raise ValueError('Compiler pin mismatch: ' + name)
        (h / 'kotlin').mkdir(exist_ok=True)
        if p.resolve()!=(h/'kotlin'/p.name).resolve():shutil.copyfile(p,h/'kotlin'/p.name)
    native_name,native_sha=NATIVE['Windows']
    native_jar=input_file(Path('native/native.jar'),'https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.12.20/sherpa-onnx-native-lib-'+native_name+'-v1.12.20.jar',native_sha)
    if sha(native_jar) != native_sha:
        raise ValueError('Native release jar mismatch')
    import zipfile
    (h / 'native').mkdir(exist_ok=True)
    with zipfile.ZipFile(native_jar) as z:
        for name in z.namelist():
            if name.endswith('.dll'):
                (h / 'native' / Path(name).name).write_bytes(z.read(name))
    aar=input_file(Path('sherpa-onnx-1.12.20.aar'),'https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.12.20/sherpa-onnx-1.12.20.aar',LOCK['upstream_sha256'])
    if sha(aar) != LOCK['upstream_sha256']:
        raise ValueError('Sherpa upstream API AAR mismatch')
    with zipfile.ZipFile(aar) as z:
        (h / 'classes.jar').write_bytes(z.read('classes.jar'))
    ort_sha='a4e57e18a04b6c1b5b0e2885af1d8557873d4ca04bfcebf79743966c4c8eb20f'
    ort=input_file(Path('onnxruntime-1.17.1.jar'),'https://repo1.maven.org/maven2/com/microsoft/onnxruntime/onnxruntime/1.17.1/onnxruntime-1.17.1.jar',ort_sha)
    if sha(ort) != ort_sha:
        raise ValueError('ORT Java pin mismatch')
    if ort.resolve()!=(h/ort.name).resolve():shutil.copyfile(ort,h/ort.name)
    # Dependency pins only: generated jars/sources cannot become trusted dependencies on a rerun.
    return {str(p.relative_to(h)):sha(p) for p in [*list((h/'kotlin').glob('*.jar')),h/'classes.jar',h/'onnxruntime-1.17.1.jar',*list((h/'native').glob('*.dll'))]}

if __name__ == '__main__':
    from pathlib import Path
    ap = argparse.ArgumentParser()
    ap.add_argument('--harness', type=Path, help='Verified existing harness; omit to download exact pinned dependencies')
    args = ap.parse_args()
    owned(LOCAL)
    pins = {}
    for name, (url, digest) in PINS.items():
        print('FETCH', name, flush=True)
        fetch(url, LOCAL / 'voxlock' / name, digest)
        pins[name] = dict(url=url, sha256=digest, bytes=(LOCAL / 'voxlock' / name).stat().st_size)
    import numpy, onnxruntime
    report = dict(source_revision=SOURCE_REV, model_revision=MODEL_REV,
                  license='Apache-2.0; preserve upstream NOTICE', files=pins,
                  numpy=numpy.__version__, ort_python=onnxruntime.__version__, python=sys.version,
                  harness=stage_harness(args.harness),
                  parity='Host JNI release 1.12.20; not identical signed APK native build; C2 ORT Java 1.17.1')
    write_json(LOCAL / 'provenance.json', report)
    print('PROVISIONED', flush=True)

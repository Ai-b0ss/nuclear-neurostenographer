"""Actual ONNX session lifetime and bad-enrollment probes on host, not Android tests."""
import gc
import importlib.util
import json
import time
import numpy as np
import psutil
from common import LOCAL,sha,write_json
from make_dev import read_wav
from provision import PINS

if __name__=='__main__':
    for name,(_,digest) in PINS.items():
        if sha(LOCAL/'voxlock'/name)!=digest:raise ValueError('Untrusted candidate file')
    spec=importlib.util.spec_from_file_location('voxlock_audited',LOCAL/'voxlock/core.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    sample=read_wav(LOCAL/'host-provided-v2/two-person-overlap.enroll-0.wav')
    rows=[]
    for i in range(5):
        start=time.perf_counter();vl=core.VoxLock(model_dir=LOCAL/'voxlock',precision='int8',threads=1)
        short_rejected=False
        try:vl.isolate(np.zeros(1600,np.float32),sample=sample[:-1])
        except ValueError:short_rejected=True
        y=vl.isolate(np.zeros(1600,np.float32),sample=sample)
        if len(y)!=1600 or not np.isfinite(y).all() or not short_rejected:raise ValueError('Negative gate failed')
        rows.append(dict(attempt=i,short_enrollment_rejected=short_rejected,samples=len(y),peak=float(abs(y).max()),wall_s=time.perf_counter()-start,
                         rss_before_release=psutil.Process().memory_info().rss))
        del vl;gc.collect();rows[-1]['rss_after_release']=psutil.Process().memory_info().rss
    write_json(LOCAL/'runtime-negatives.json',dict(scope='Host Python ORT1.31.1; five session create/infer/delete/GC cycles; allocator RSS retention is not a leak proof; not Android lifecycle',rows=rows,status='PASS'))
    print('PASS5 host init/free+short enrollment+silence cycles')

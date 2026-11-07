"""Offline diagnostic ONLY: compare encoder-state cosine distances with coarse TTS labels.
Labels are never fed to the runtime. Encoder states are not a calibrated speaker verifier.
"""
import argparse
import json
from pathlib import Path
import numpy as np

p = argparse.ArgumentParser()
p.add_argument('folder', type=Path); p.add_argument('reference', type=Path)
a = p.parse_args()
r = json.loads(a.reference.read_text(encoding='utf-8'))
x = np.fromfile(a.folder/'encoder-embeddings.bin', dtype='<f4').reshape(-1, 512)
selected=[]; labels=[]
for i in range(len(x)):
    at=i*80+40
    matches=[s['speaker_id'] for s in r['diarization'] if s['start_ms']+300 <= at < s['end_ms']-300]
    if len(matches)==1 and np.linalg.norm(x[i])>1e-8:
        selected.append(x[i]/np.linalg.norm(x[i])); labels.append(matches[0])
x=np.array(selected); labels=np.array(labels)
cos=x@x.T
pair=np.triu(np.ones(cos.shape,dtype=bool),1)
same=cos[pair & (labels[:,None]==labels[None,:])]
different=cos[pair & (labels[:,None]!=labels[None,:])]
def stats(v):
    return dict(count=len(v), mean=float(np.mean(v)), p05=float(np.quantile(v,.05)),p50=float(np.median(v)),p95=float(np.quantile(v,.95)))
report=dict(scope='POSTHOC_COARSE_TTS_ENCODER_DIAGNOSTIC_NOT_INFERENCE_NOT_SPEAKER_EMBEDDING_MODEL',
    same_speaker=stats(same), different_speaker=stats(different),
    conclusion='No validated global identity threshold: overlapping within/between-speaker cosine distributions require a separate calibrated speaker embedding model and independent evaluation.')
(a.folder/'embedding-diagnostic.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))

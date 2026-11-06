"""Reference-blind speaker timeline fusion experiment.

Each C2 source is a list of half-open (start_ms, end_ms, slot) turns.
Align OFFLINE slots to revisable FAST using maximum temporal agreement,
then compare three explicit policies without looking at RTTM labels.
This is an optional candidate, NOT active in the Android product.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from score_transcript import assignment

N=8

def load(path:Path):
    turns=[]
    for line,raw in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if not raw.strip():continue
        parts=raw.split('\t')
        if len(parts)!=3:raise ValueError(f'{path}:{line}: invalid TSV')
        a,b,s=(int(x) for x in parts)
        if not(0<=a<b<=3600000 and 0<=s<N):
            raise ValueError(f'{path}:{line}: invalid turn')
        turns.append((a,b,s))
    return sorted(turns)

def alignment(final,preview):
    # 8! enumeration is avoided by the bounded scorer's DP assignment.
    weights=[[0 for _ in range(N)] for _ in range(N)]
    for a,b,s in final:
        for x,y,t in preview:
            if b>x and y>a:
                weights[s][t]+=max(0,min(b,y)-max(a,x))
    # Identity tie preference keeps stable unused slots rather than arbitrary swaps.
    _,path=assignment([[-(weights[i][j]+(1e-6 if i==j else 0.)) for j in range(N)] for i in range(N)])
    return {i:path[i] for i in range(N)}, weights

def fuse(final,preview,policy):
    if policy not in ('preview-first','final-first','union'):
        raise ValueError('Unknown policy')
    mapping, weights=alignment(final,preview)
    boundaries=sorted({x for a,b,_ in final+preview for x in (a,b)})
    turns=[]
    if not boundaries:return turns,dict(mapping=mapping, disagreement_ms=0)
    start={}; disagreement=0
    for a,b in zip(boundaries,boundaries[1:]):
        p={s for x,y,s in preview if x<=a<y}
        f={mapping[s] for x,y,s in final if x<=a<y}
        if p!=f:disagreement+=b-a
        chosen=p or f if policy=='preview-first' else f or p if policy=='final-first' else p|f
        # Close/open per slot so split output remains monotonic, exhaustive.
        for who in list(start):
            if who not in chosen:
                turns.append((start.pop(who),a,who))
        for who in chosen:
            if who not in start:start[who]=a
    stop=boundaries[-1]
    for who,beg in start.items():turns.append((beg,stop,who))
    return sorted(turns),dict(mapping=mapping,disagreement_ms=disagreement,
        preview_speakers=len({s for _,_,s in preview}),
        final_speakers=len({s for _,_,s in final}),
        source_weights_ms=weights)

def dump(turns,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(f'{a}\t{b}\t{s}\n' for a,b,s in turns if a<b),encoding='utf-8')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--preview',type=Path,required=True)
    p.add_argument('--final',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    f=load(a.final);p=load(a.preview)
    a.out.mkdir(parents=True,exist_ok=True)
    for name in ('preview-first','final-first','union'):
        turns,metrics=fuse(f,p,name)
        dump(turns,a.out/(name+'.tsv'))
        (a.out/(name+'.json')).write_text(json.dumps(metrics,indent=2)+'\n',encoding='utf-8')
        print(name,len(turns),'turns',metrics['disagreement_ms'],'ms disagreement',flush=True)

if __name__=='__main__':main()

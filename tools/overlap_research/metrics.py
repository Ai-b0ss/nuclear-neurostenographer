"""Honest companion metrics; missing independent word/turn annotation is unavailable."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from score_transcript import evaluate, words

def unknown(s):
    return s['speaker_id'] is None or not s.get('attribution_reliable',True)

def score(reference,hypothesis):
    result=evaluate(reference,hypothesis,0,False)
    known=dict(hypothesis,segments=[s for s in hypothesis['segments'] if not unknown(s)])
    result['cpwer_u']=evaluate(reference,known)['cpwer']
    result['cpwer_u']['definition']='Project-specific cpWER after dropping unknown/unreliable words; can hide insertions, not an upper bound'
    result['unknown_words']=sum(len(words(s['text'])) for s in hypothesis['segments'] if unknown(s))
    result['hypothesis_words']=sum(len(words(s['text'])) for s in hypothesis['segments'])
    result['der_collar250']=evaluate(reference,hypothesis,250,False)['der']
    result['overlap_words']=dict(status='NOT_SCORED',reason='No independently annotated word times/speaker activity supplied')
    return result

def overlap_spans(turns):
    points=sorted({t[k] for t in turns for k in ('start_ms','end_ms')})
    out=[]
    for a,b in zip(points,points[1:]):
        speakers={t['speaker_id'] for t in turns if t['start_ms']<=a<t['end_ms'] and t['speaker_id'] is not None}
        if len(speakers)<2:continue
        ids=sorted(speakers)
        if out and out[-1]['end_ms']==a and out[-1]['speakers']==ids:out[-1]['end_ms']=b
        else:out.append(dict(start_ms=a,end_ms=b,speakers=ids))
    return out

def in_overlap(s,spans):
    at=(s['start_ms']+s['end_ms'])/2
    return any(t['start_ms']<=at<t['end_ms'] for t in spans)

def temporal_recall(reference_words,hypothesis_words,tolerance_ms=250):
    """Max cardinality one-to-one word matching, literal supplied IDs, emission midpoint tolerance.
    Only caller-provided independent single-word annotations are accepted.
    """
    if type(tolerance_ms) is not int or tolerance_ms<0:
        raise ValueError('Nonnegative integer tolerance required')
    if any(len(words(s['text']))!=1 for s in reference_words+hypothesis_words):
        raise ValueError('Temporal recall requires one normalized word per interval')
    edges=[]
    for r in reference_words:
        edges.append([j for j,h in enumerate(hypothesis_words) if not unknown(h) and
                      r['speaker_id']==h['speaker_id'] and words(r['text'])==words(h['text']) and
                      abs((r['start_ms']+r['end_ms']-h['start_ms']-h['end_ms'])/2)<=tolerance_ms])
    matched={}
    def assign(i,seen):
        for j in edges[i]:
            if j in seen:continue
            seen.add(j)
            if j not in matched or assign(matched[j],seen): matched[j]=i;return True
        return False
    count=sum(assign(i,set()) for i in range(len(edges)))
    return dict(matched=count,reference_words=len(reference_words),hypothesis_words=len(hypothesis_words),
                recall=count/len(reference_words) if reference_words else None,added_unmatched_words=len(hypothesis_words)-count,
                tolerance_ms=tolerance_ms)

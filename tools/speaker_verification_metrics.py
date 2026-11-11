"""Pure Python, deterministic speaker-verification evaluation helpers.

Speaker-level disjoint calibration/evaluation is mandatory. All pairs sharing a
recording or voice are correlated; pair counts are not independent observations.
"""
from itertools import combinations
import math


def cosine(a, b):
    if len(a) != len(b) or len(a) < 2:
        raise ValueError("incompatible embeddings")
    if not all(math.isfinite(float(x)) for x in (*a, *b)):
        raise ValueError("nonfinite embedding")
    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    an = math.sqrt(sum(float(x) ** 2 for x in a))
    bn = math.sqrt(sum(float(x) ** 2 for x in b))
    if an <= 1e-8 or bn <= 1e-8:
        raise ValueError("zero-norm embedding")
    return max(-1., min(1., dot / (an * bn)))


def make_pairs(rows):
    """Each row {speaker_id, id, vector}; pairs only within supplied partition."""
    pairs = []
    for a, b in combinations(rows, 2):
        if a["id"] == b["id"]:
            raise ValueError("duplicate utterance id")
        pairs.append({"same": a["speaker_id"] == b["speaker_id"],
                      "score": cosine(a["vector"], b["vector"])})
    return pairs


def rates(pairs, threshold):
    if not -1. <= threshold <= 1.:
        raise ValueError("invalid cosine threshold")
    positives = sum(bool(p["same"]) for p in pairs)
    negatives = len(pairs) - positives
    if not positives or not negatives:
        raise ValueError("need positive and negative pairs")
    fp = sum(not p["same"] and p["score"] >= threshold for p in pairs)
    fn = sum(p["same"] and p["score"] < threshold for p in pairs)
    return {"threshold": threshold, "positive_pairs": positives,
            "negative_pairs": negatives, "false_accepts": fp, "false_rejects": fn,
            "false_accept_rate": fp / negatives,
            "false_reject_rate": fn / positives,
            "true_accept_rate": 1 - fn / positives,
            "accuracy": (len(pairs) - fp - fn) / len(pairs)}


def equal_error_rate(pairs):
    vals = sorted({p["score"] for p in pairs})
    candidates = [-1., *(min(1., v + 1e-10) for v in vals), 1.]
    best = min((rates(pairs, t) for t in candidates),
               key=lambda x: (abs(x["false_accept_rate"]-x["false_reject_rate"]),
                              x["false_accept_rate"]+x["false_reject_rate"]))
    return {"approx_eer": (best["false_accept_rate"]+best["false_reject_rate"])/2,
            "threshold": best["threshold"]}


def auc(pairs):
    pos = [p["score"] for p in pairs if p["same"]]
    neg = [p["score"] for p in pairs if not p["same"]]
    if not pos or not neg:
        raise ValueError("need both classes")
    wins = sum((p > n) + 0.5*(p == n) for p in pos for n in neg)
    return wins/(len(pos)*len(neg))


def calibrate(pairs, max_dev_far=0.01):
    """Choose threshold only from development speakers, with FAR <= target.

    Maximize recall among eligible thresholds; tie-break for lower FAR then
    largest threshold. The resulting FAR bound is NOT guaranteed on held-out.
    """
    if not 0 <= max_dev_far <= 1:
        raise ValueError("invalid FAR objective")
    vals = sorted({float(p["score"]) for p in pairs})
    candidates = sorted({-1., 1., *[min(1., v+1e-9) for v in vals]})
    options = [rates(pairs, t) for t in candidates]
    eligible = [x for x in options if x["false_accept_rate"] <= max_dev_far]
    if not eligible:
        raise RuntimeError("no threshold satisfies dev FAR target")
    return min(eligible, key=lambda x: (x["false_reject_rate"],
                                       x["false_accept_rate"],-x["threshold"]))


def score_summary(pairs):
    pos = sorted(p["score"] for p in pairs if p["same"])
    neg = sorted(p["score"] for p in pairs if not p["same"])
    if not pos or not neg:
        raise ValueError("missing class")
    def quantile(seq, q):
        i = (len(seq)-1)*q
        lo = math.floor(i);hi = math.ceil(i)
        return seq[lo]*(hi-i) + seq[hi]*(i-lo) if lo!=hi else seq[lo]
    return {"same": {"min":pos[0], "p05":quantile(pos,.05),
                     "median":quantile(pos,.5), "p95":quantile(pos,.95),
                     "max":pos[-1]},
            "different":{"min":neg[0], "p05":quantile(neg,.05),
                         "median":quantile(neg,.5),"p95":quantile(neg,.95),
                         "max":neg[-1]}}


def open_set_probe(rows, threshold, margin=.07):
    """Per-partition speaker enrolment: first utterance/speaker is enrolled;
    remaining utterances probe independently. Unknown speakers are separately
    handled by the caller; this summary is known-speaker only.
    """
    if not 0 <= margin <= 1: raise ValueError("invalid margin")
    by={}
    for row in rows:by.setdefault(row["speaker_id"],[]).append(row)
    if min(len(v) for v in by.values()) < 2:raise ValueError("need two utterances per speaker")
    enroll={s:sorted(v,key=lambda x:x["id"])[0] for s,v in by.items()}
    probes=[x for s,v in by.items() for x in sorted(v,key=lambda x:x["id"])[1:]]
    matched=wrong=rejected=0
    for p in probes:
        rank=sorted(((s,cosine(p["vector"],e["vector"])) for s,e in enroll.items()),
                    key=lambda x:-x[1])
        ok=rank[0][1]>=threshold and (len(rank)<2 or rank[0][1]-rank[1][1]>=margin)
        if not ok:rejected+=1
        elif rank[0][0]==p["speaker_id"]:matched+=1
        else:wrong+=1
    return {"enrolled_speakers":len(enroll),"probes":len(probes),
            "correct_links":matched, "false_links":wrong, "rejections":rejected,
            "threshold":threshold,"margin":margin}


def open_set_known_unknown(rows, threshold, margin=.07):
    """Simulate arrivals of known and new voices with speaker-disjoint enrolment.

    Sort speakers, enrol first half by one utterance each and test known probes
    from remaining utterances plus ALL utterances of withheld unknown speakers.
    Repeat with halves reversed. A false link can occur even if pairwise FAR
    looks small, because each unknown probe is compared to many enrolments.
    """
    if not -1 <= threshold <= 1 or not 0 <= margin <= 1:
        raise ValueError("invalid acceptance policy")
    by={}
    for x in rows:by.setdefault(x["speaker_id"],[]).append(x)
    names=sorted(by)
    if len(names)<4 or any(len(v)<2 for v in by.values()):
        raise ValueError("need >=4 speakers and >=2 utterances each")
    reports=[]
    half=len(names)//2
    for enrolled in (set(names[:half]),set(names[half:])):
        withheld=set(names)-enrolled
        templates={k:sorted(by[k],key=lambda x:x["id"])[0] for k in enrolled}
        known=[x for k in enrolled for x in sorted(by[k],key=lambda z:z["id"])[1:]]
        unknown=[x for k in withheld for x in by[k]]
        false_unknown_speakers=set()
        rejected_known_speakers=set()
        stats={"enrolled_speakers":len(enrolled),
               "unknown_speakers":len(withheld),
               "known_probes":len(known),"unknown_probes":len(unknown),
               "correct_known_links":0,"wrong_known_links":0,
               "rejected_known":0,"false_accepted_unknown":0,
               "correct_rejected_unknown":0}
        for row in known+unknown:
            ranked=sorted(((sid,cosine(row["vector"],e["vector"])) for sid,e in templates.items()),
                         key=lambda pair:-pair[1])
            accepted=ranked[0][1]>=threshold and (len(ranked)<2 or ranked[0][1]-ranked[1][1]>=margin)
            known_speaker=row["speaker_id"] in enrolled
            if known_speaker:
                if not accepted:
                    stats["rejected_known"]+=1
                    rejected_known_speakers.add(row["speaker_id"])
                elif ranked[0][0]==row["speaker_id"]:stats["correct_known_links"]+=1
                else:stats["wrong_known_links"]+=1
            elif accepted:
                stats["false_accepted_unknown"]+=1
                false_unknown_speakers.add(row["speaker_id"])
            else:stats["correct_rejected_unknown"]+=1
        stats["unknown_speakers_with_false_accept"] = len(false_unknown_speakers)
        stats["known_speakers_with_rejections"] = len(rejected_known_speakers)
        reports.append(stats)
    total={k:sum(r[k] for r in reports) for k in reports[0]}
    total["threshold"]=threshold
    total["margin"]=margin
    total["unknown_false_accept_rate"]=(total["false_accepted_unknown"]/
                                        total["unknown_probes"])
    total["known_reject_rate"]=total["rejected_known"]/total["known_probes"]
    total["known_wrong_link_rate"]=total["wrong_known_links"]/total["known_probes"]
    total["rounds"]=2
    return total

def dual_profile_proxy(rows, consistency=.84, link_threshold=.84, margin=.07):
    """Proxy for two separated voiceprints from one local speaker.

    VCTK's first two DISTINCT utterances replace early/late audio portions;
    third utterance probes how often the merged ID can recognize the voice.
    This is not real long-recording diarization or same-block verification.
    """
    if any(x not in (x,) or not 0<=x<=1 for x in (consistency,link_threshold,margin)):
        raise ValueError("invalid policy")
    groups={}
    for row in rows:groups.setdefault(row["speaker_id"],[]).append(row)
    if any(len(v)!=3 for v in groups.values()):
        raise ValueError("Need exactly three utterances per speaker")
    templates={}
    for sid,items in groups.items():
        first,second,_=sorted(items,key=lambda x:x["id"])
        if cosine(first["vector"],second["vector"])<consistency:
            continue
        va=first["vector"];vb=second["vector"]
        length_a=math.sqrt(sum(float(x)**2 for x in va))
        length_b=math.sqrt(sum(float(x)**2 for x in vb))
        avg=[a/length_a+b/length_b for a,b in zip(va,vb)]
        length_avg=math.sqrt(sum(x*x for x in avg))
        templates[sid]=[x/length_avg for x in avg]
    correct=wrong=rejected=missing=0
    for sid,items in groups.items():
        third=sorted(items,key=lambda x:x["id"])[2]
        if sid not in templates:missing+=1;continue
        ranked=sorted(((k,cosine(third["vector"],v)) for k,v in templates.items()),
                      key=lambda x:-x[1])
        accepted=ranked[0][1]>=link_threshold and (len(ranked)<2 or
                 ranked[0][1]-ranked[1][1]>=margin)
        if not accepted:rejected+=1
        elif ranked[0][0]==sid:correct+=1
        else:wrong+=1
    return {"people":len(groups),"verified_two_part_profiles":len(templates),
            "rejected_inconsistent_profiles":len(groups)-len(templates),
            "third_utterance_correct_links":correct,
            "third_utterance_wrong_links":wrong,
            "third_utterance_link_rejections":rejected,
            "third_utterance_no_profile":missing,
            "consistency_threshold":consistency,
            "link_threshold":link_threshold,"margin":margin}

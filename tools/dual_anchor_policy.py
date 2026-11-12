"""Dual-anchor return-only replay, verified against the Kotlin book. No new inconsistent enrollment."""
from evaluate_russian_bookmix_voice_link import normalized
def simulate(clips,np):
    entries=[];truth_ids={};next_id=1
    metrics=dict(profiles_seen=0,assigned=0,consistent_enrollments=0,rescued_assignments=0,
        correct_returning_links=0,returning_valid_probes=0,returning_false_splits=0,
        wrong_returning_links=0,new_speaker_false_links=0,unassigned=0,collisions=0)
    events=[]
    def match(vector):
        ranked=sorted(((i,float(np.dot(vector,e["centroid"]))) for i,e in enumerate(entries)),key=lambda x:-x[1])
        if not ranked:return None
        idx,top=ranked[0];runner=ranked[1][1] if len(ranked)>1 else -1
        anchor=float(np.dot(vector,entries[idx]["anchor"]))
        other=max((float(np.dot(vector,e["anchor"])) for i,e in enumerate(entries) if i!=idx),default=-1)
        return idx if top>=.84 and top-runner>=.07 and anchor>=.84 and anchor-other>=.07 else None
    for clip in clips:
        candidates=[]
        for p in clip["profiles"]:
            metrics["profiles_seen"]+=1
            consistent=p["valid"]=="PASS"
            target=None;rescue=False
            if consistent:target=match(p["v"])
            elif p["valid"]=="AGREEMENT_REJECT" and "early" in p and "late" in p:
                first=match(p["early"]);second=match(p["late"])
                if first is not None and first==second:target=first;rescue=True
            candidates.append((p,consistent,target,rescue))
        collisions={}
        for p,consistent,target,rescue in candidates:
            if target is not None:collisions[target]=collisions.get(target,0)+1
        updates=[];fresh=[]
        for p,consistent,target,rescue in candidates:
            if target is not None and collisions[target]>1:metrics["collisions"]+=1
            if target is not None and collisions[target]==1:
                gid=entries[target]["id"]
                if rescue:metrics["rescued_assignments"]+=1
                else:updates.append((target,p["v"]))
            elif consistent:
                fresh.append(p);continue
            else:
                metrics["unassigned"]+=1
                events.append({"clip":clip["id"],"local":p["local"],"truth":p["truth"],"id":None,"rescued":False})
                continue
            old=truth_ids.setdefault(p["truth"],set())
            if old:
                metrics["returning_valid_probes"]+=1
                if gid in old:metrics["correct_returning_links"]+=1
                elif any(gid in ids for truth,ids in truth_ids.items() if truth!=p["truth"]):metrics["wrong_returning_links"]+=1
                else:metrics["returning_false_splits"]+=1
            elif any(gid in ids for truth,ids in truth_ids.items() if truth!=p["truth"]):metrics["new_speaker_false_links"]+=1
            old.add(gid);metrics["assigned"]+=1
            events.append({"clip":clip["id"],"local":p["local"],"truth":p["truth"],"id":gid,"rescued":rescue})
        for idx,v in updates:entries[idx]["centroid"]=normalized(.85*entries[idx]["centroid"]+.15*v,np)
        for p in fresh:
            if len(entries)==256:metrics["unassigned"]+=1;continue
            gid="Speaker "+str(next_id);next_id+=1
            entries.append({"id":gid,"anchor":p["v"].copy(),"centroid":p["v"].copy()})
            old=truth_ids.setdefault(p["truth"],set())
            if old:metrics["returning_valid_probes"]+=1;metrics["returning_false_splits"]+=1
            old.add(gid);metrics["assigned"]+=1;metrics["consistent_enrollments"]+=1
            events.append({"clip":clip["id"],"local":p["local"],"truth":p["truth"],"id":gid,"rescued":False})
    metrics["global_ids"]=len(entries)
    metrics["speaker_mixes"]=sum(len({truth for truth,ids in truth_ids.items() if e["id"] in ids})>1 for e in entries)
    return metrics,events

"""Current dual-anchor policy metrics; historical admission-only replay stays separate."""

def replay(clips, np):
    from dual_anchor_policy import simulate
    checked=[]
    for clip in clips:
        profiles=[]
        for original in clip["profiles"]:
            p=dict(original)
            if p["valid"] in ("PASS", "AGREEMENT_REJECT"):
                if "early" not in p or "late" not in p:
                    raise ValueError("Current policy requires both temporal embeddings")
                from evaluate_russian_bookmix_voice_link import normalized
                early=normalized(p["early"],np)
                late=normalized(p["late"],np)
                if early.shape != late.shape:
                    raise ValueError("Temporal embedding dimensions differ")
                p.update(early=early,late=late,v=normalized(early+late,np),
                         valid="PASS" if float(np.dot(early,late))>=.84 else "AGREEMENT_REJECT")
            profiles.append(p)
        checked.append({"id":clip["id"],"profiles":profiles})
    raw,events=simulate(checked,np)
    rejected=0; insufficient=0; consistent=0; expected_returns=0
    seen=set()
    for clip in checked:
        prior=seen.copy()
        for p in clip["profiles"]:
            if p["truth"] in prior:expected_returns+=1
            if p["valid"]=="PASS":consistent+=1
            elif p["valid"]!="AGREEMENT_REJECT":insufficient+=1
        seen.update(p["truth"] for p in clip["profiles"])
    by_key={(c["id"],p["local"]):p for c in checked for p in c["profiles"]}
    for event in events:
        if event["id"] is None and by_key[event["clip"],event["local"]]["valid"]=="AGREEMENT_REJECT":
            rejected+=1
    metrics={
        "policy":"dual_anchor_return_only_v1",
        "total_expected_profiles":raw["profiles_seen"],
        "profiles_consistent":consistent,
        "profiles_assigned":raw["assigned"],
        "profiles_unassigned":raw["profiles_seen"]-raw["assigned"],
        "profiles_rejected_early_late":rejected,
        "profiles_rejected_insufficient_evidence":insufficient,
        "profiles_rescued_against_existing_anchor":raw["rescued_assignments"],
        "first_valid_enrollments":raw["assigned"]-raw["returning_valid_probes"],
        "returning_valid_probes":raw["returning_valid_probes"],
        "returning_expected_probes":expected_returns,
        "correct_returning_links":raw["correct_returning_links"],
        "returning_false_splits":raw["returning_false_splits"],
        "new_speaker_false_links":raw["new_speaker_false_links"],
        "wrong_returning_links":raw["wrong_returning_links"],
        "speaker_mixes":raw["speaker_mixes"],
        "in_block_collisions":raw["collisions"],
        "distinct_true_voices_admitted":len({e["truth"] for e in events if e["id"] is not None}),
        "total_global_ids_created":raw["global_ids"],
        "returning_recall_accepted":raw["correct_returning_links"]/raw["returning_valid_probes"] if raw["returning_valid_probes"] else None,
        "returning_appearance_recall":raw["correct_returning_links"]/expected_returns if expected_returns else None,
    }
    return metrics,events

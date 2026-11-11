#!/usr/bin/env python3
"""Offline speaker-disjoint evaluation of TitaNet Small ONNX on VCTK FLAC files.

Inputs: public VCTK excerpts from the user-reviewed manifest, no user/private audio.
TitaNet trained on English data; results MUST NOT be represented as Russian DER,
diarization accuracy, FPR on population, or validation for production deployment.

Use the existing sherpa-onnx 1.12.40 install via --site-packages (isolated).
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

from speaker_verification_metrics import (make_pairs, rates, calibrate,
    auc, equal_error_rate, score_summary, open_set_probe, open_set_known_unknown,
    dual_profile_proxy)


def sha256_file(filename):
    h=hashlib.sha256()
    with open(filename,"rb") as f:
        for buf in iter(lambda:f.read(1<<20),b""):h.update(buf)
    return h.hexdigest()


def decode_to_16k(filename, executable):
    """Native ffmpeg SWR 48k->16k, mono float32; never mutate source."""
    command=[str(executable),"-nostdin","-hide_banner","-loglevel","error",
             "-i",str(filename),"-ar","16000","-ac","1","-f","f32le","pipe:1"]
    p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
    if p.returncode or not p.stdout or len(p.stdout)%4:
        raise ValueError("Audio decode failed: "+p.stderr.decode("utf8","replace")[:250])
    return p.stdout


def evaluate(a):
    import numpy as np
    import sherpa_onnx
    path=Path(a.manifest).resolve()
    root=path.parent
    model=Path(a.model).resolve()
    expected="ad4a1802485d8b34c722d2a9d04249662f2ece5d28a7a039063ca22f515a789e"
    actual=sha256_file(model)
    if actual!=expected:
        raise ValueError("Wrong model SHA256; refusing to benchmark")
    manifest=json.loads(path.read_text(encoding="utf8"))
    if manifest.get("split")!="train" or manifest.get("original_corpus")!="CSTR VCTK 0.92":
        raise ValueError("Unexpected VCTK manifest")
    files=manifest["files"]
    allids=[item["id"] for item in files]
    if len(set(allids))!=len(allids):raise ValueError("duplicate utterance")
    speakers=sorted(set(f["speaker_id"] for f in files))
    if len(speakers)<10 or any(sum(f["speaker_id"]==s for f in files)!=3 for s in speakers):
        raise ValueError("Expected >=10 speaker IDs with exactly 3 clips each")
    if any(x["mic_id"]!="mic2" for x in files):
        raise ValueError("Unexpected microphone; test design requires mic2")
    middle=len(speakers)//2
    dev_speakers=set(speakers[:middle])
    eval_speakers=set(speakers[middle:])
    assert not dev_speakers.intersection(eval_speakers)
    extractor=sherpa_onnx.SpeakerEmbeddingExtractor(
        sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=str(model),num_threads=2,debug=False,provider="cpu"))
    if extractor.dim!=192:raise ValueError("TitaNet dimension is not 192")
    rows=[]
    start=time.monotonic()
    for count,item in enumerate(sorted(files,key=lambda z:(z["speaker_id"],z["id"])),1):
        clip=(root/"audio"/item["path"]).resolve()
        if clip.parent!=(root/"audio").resolve() or not clip.is_file():
            raise ValueError("Invalid audio path")
        if sha256_file(clip)!=item["sha256"]:
            raise ValueError("FLAC manifest SHA256 mismatch")
        raw=decode_to_16k(clip,a.ffmpeg)
        audio=np.frombuffer(raw,dtype="<f4").copy()
        if not np.all(np.isfinite(audio)) or max(abs(audio))>1.2 or len(audio)<48000:
            raise ValueError("Unexpected decoded audio")
        stream=extractor.create_stream()
        stream.accept_waveform(16000,audio)
        stream.input_finished()
        if not extractor.is_ready(stream):
            raise ValueError("Not enough signal for TitaNet")
        vec=extractor.compute(stream)
        if len(vec)!=192 or not all(math.isfinite(x) for x in vec):
            raise ValueError("Non-finite voice embedding")
        rows.append({"speaker_id":item["speaker_id"],"id":item["id"],"vector":vec})
        print(f"EMBED {count}/{len(files)} {item['id']} "
              f"duration_s={len(audio)/16000:.2f} "
              f"elapsed_s={time.monotonic()-start:.1f}",flush=True)
    drows=[x for x in rows if x["speaker_id"] in dev_speakers]
    erows=[x for x in rows if x["speaker_id"] in eval_speakers]
    dpairs=make_pairs(drows)
    epairs=make_pairs(erows)
    selected=calibrate(dpairs,max_dev_far=.01)
    selected_threshold=selected["threshold"]

    def summary(rows,pairs):
        return {"speakers":len(set(x["speaker_id"] for x in rows)),
                "utterances":len(rows),
                "pairs":len(pairs),
                "pairwise_cosine":score_summary(pairs),
                "auc":auc(pairs),
                "approx_eer":equal_error_rate(pairs),
                "fixed_0_84":rates(pairs,.84),
                "development_calibrated":rates(pairs,selected_threshold),
                "enrollment_fixed_0_84_margin_0_07":
                    open_set_probe(rows,threshold=.84,margin=.07),
                "enrollment_calibrated_margin_0_07":
                    open_set_probe(rows,threshold=selected_threshold,margin=.07),
                "open_set_fixed_0_84_margin_0_07":
                    open_set_known_unknown(rows,.84,margin=.07),
                "open_set_calibrated_margin_0_07":
                    open_set_known_unknown(rows,selected_threshold,margin=.07)}
    outcome={
        "schema":"speaker-verification-vctk-speaker-disjoint-v1",
        "date":"2026-11-11",
        "experiment":"TitaNet Small same-mic English VCTK speaker classification",
        "source":"https://huggingface.co/datasets/thelarryproject/vctk",
        "speaker_labels":"VCTK corpus speaker_id labels; cross-utterance, not manual transcript diarization",
        "model_sha256":actual,
        "model_embedding_dimension":extractor.dim,
        "sherpa_onnx_version":getattr(sherpa_onnx,"__version__","unknown"),
        "original_audio_sr":48000,"inference_audio_sr":16000,
        "preprocessing":"ffmpeg resample to 16k mono float32",
        "split_method":"sort corpus speaker IDs, first half development, second half held-out; no shared speaker",
        "selected_threshold_only_on_dev":selected,
        "heldout_threshold_was_frozen":True,
        "development":summary(drows,dpairs),
        "heldout":summary(erows,epairs),
        "inference_wall_seconds":round(time.monotonic()-start,2),
        "caveats":["Only 12 independent speaker identities; confidence interval for false matches is wide.",
                   "Pairs are statistically correlated, not 135 independent trials.",
                   "Threshold selected on 6 dev speakers; never tune on 6 held-out speakers.",
                   "English close-talk VCTK does not represent Russian overlapping speech or background noise.",
                   "This evaluates speaker embeddings only, not C2 diarization, word attribution or DER.",
                   "No user audio, raw voice embeddings or transcripts are published."]}
    if a.frozen_threshold is not None:
        # Strict external holdout: threshold frozen by an earlier 12-speaker
        # experiment, BEFORE these fresh 24 speakers were ever evaluated.
        allpairs=make_pairs(rows)
        outcome["separate_prior_experiment_frozen_threshold"]=a.frozen_threshold
        outcome["external_new_speakers_at_frozen_threshold"]={
            "speakers":len(speakers),"utterances":len(rows),
            "pairs":len(allpairs),
            "pairwise_cosine":score_summary(allpairs),
            "auc":auc(allpairs),
            "fixed_0_84":rates(allpairs,.84),
            "prior_calibrated_threshold":rates(allpairs,a.frozen_threshold),
            "open_set_fixed_0_84":open_set_known_unknown(rows,.84,margin=.07),
            "open_set_prior_calibrated":
                open_set_known_unknown(rows,a.frozen_threshold,margin=.07),
            "dual_fingerprint_qa_proxy_fixed_0_84":
                dual_profile_proxy(rows,consistency=.84,link_threshold=.84,margin=.07)}
    out=Path(a.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(outcome,ensure_ascii=False,indent=2),encoding="utf8")
    print("RESULT_JSON",str(out),flush=True)
    print("CALIBRATED",json.dumps(selected,ensure_ascii=False),flush=True)
    print("HELDOUT_FIXED",json.dumps(outcome["heldout"]["fixed_0_84"],ensure_ascii=False),flush=True)
    print("HELDOUT_SELECTED",json.dumps(outcome["heldout"]["development_calibrated"],ensure_ascii=False),flush=True)
    print("HELDOUT_ENROLLMENT",json.dumps(outcome["heldout"]["enrollment_fixed_0_84_margin_0_07"],ensure_ascii=False),flush=True)
    if "external_new_speakers_at_frozen_threshold" in outcome:
        print("EXTERNAL_HOLDOUT",json.dumps(outcome["external_new_speakers_at_frozen_threshold"],ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","model","output","ffmpeg","site-packages"):
        p.add_argument("--"+name,required=True)
    p.add_argument("--frozen-threshold",type=float,default=None,
                   help="Threshold fixed by a PRIOR independent cohort; never fit on these voices")
    a=p.parse_args()
    if a.frozen_threshold is not None and not(-1<=a.frozen_threshold<=1):
        p.error("invalid frozen threshold")
    sys.path.insert(0,str(Path(a.site_packages).resolve()))
    evaluate(a)


if __name__=="__main__":
    main()

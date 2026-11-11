#!/usr/bin/env python3
"""Independent VCTK cross-condition QA for a FROZEN voice-link policy.

Each speaker's first utterance is enrolled CLEAN; their other two utterances
are acoustically perturbed. Unknown speakers are those not enrolled in each
of two deterministic rotations. No model fitting or threshold selection occurs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from evaluate_titanet_vctk import sha256_file, decode_to_16k
from speaker_verification_metrics import open_set_known_unknown, make_pairs, rates


def synthetic_condition(wave, condition, ident, np):
    if condition == "clean":
        return wave
    signal=wave.astype(np.float64)
    if condition in ("noise15db","echo_plus_noise15db"):
        seed=int.from_bytes(hashlib.sha256((ident+condition).encode()).digest()[:8],"little")
        rng=np.random.default_rng(seed)
        noise=rng.standard_normal(signal.size)
        noise_rms=np.sqrt(np.mean(noise*noise))
        speech_rms=np.sqrt(np.mean(signal*signal))
        if speech_rms<1e-5:raise ValueError("Silent source cannot be a speaker probe")
        if condition=="echo_plus_noise15db":
            delay=2240
            echo=np.zeros_like(signal)
            echo[delay:]=signal[:-delay]
            signal=signal + 0.24*echo
        signal += noise*(speech_rms/(10**(15/20)*noise_rms))
    elif condition=="telephone_bandpass":
        freq=np.fft.rfftfreq(signal.size,d=1/16000)
        fft=np.fft.rfft(signal)
        high=np.clip((freq-230)/150,0,1)
        low=np.clip((3600-freq)/350,0,1)
        signal=np.fft.irfft(fft*high*low,n=signal.size)
    else:raise ValueError(condition)
    return np.ascontiguousarray(signal.astype(np.float32))


def evaluate(args):
    import numpy as np
    import sherpa_onnx
    manifest_path=Path(args.manifest).resolve()
    manifest=json.loads(manifest_path.read_text(encoding="utf8"))
    clips=sorted(manifest["files"],key=lambda x:(x["speaker_id"],x["id"]))
    if len({x["speaker_id"] for x in clips})<20:raise ValueError("expect independent 20+ speakers")
    if len(clips)!=len({x["id"] for x in clips}):raise ValueError("duplicate audio")
    model=Path(args.model)
    if sha256_file(model)!="ad4a1802485d8b34c722d2a9d04249662f2ece5d28a7a039063ca22f515a789e":
        raise ValueError("wrong pinned TitaNet model")
    extractor=sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(
        model=str(model),num_threads=2,debug=False,provider="cpu"))
    if extractor.dim!=192:raise ValueError("unexpected model")
    conditions=["clean","noise15db","telephone_bandpass","echo_plus_noise15db"]
    rows={condition:[] for condition in conditions}
    started=time.monotonic()
    for i,item in enumerate(clips,1):
        file=(manifest_path.parent/"audio"/item["path"]).resolve()
        if file.parent!=(manifest_path.parent/"audio").resolve() or sha256_file(file)!=item["sha256"]:
            raise ValueError("FLAC hash/path invalid")
        pcm=np.frombuffer(decode_to_16k(file,args.ffmpeg),dtype="<f4").copy()
        is_enrollment=sorted(x["id"] for x in clips if x["speaker_id"]==item["speaker_id"])[0]==item["id"]
        for condition in conditions:
            # In each scenario only the enrollment utterance is clean.
            wav=pcm if is_enrollment else synthetic_condition(pcm,condition,item["id"],np)
            st=extractor.create_stream()
            st.accept_waveform(16000,wav)
            st.input_finished()
            if not extractor.is_ready(st):raise ValueError("encoder not ready")
            vector=extractor.compute(st)
            if len(vector)!=192:raise ValueError("unexpected vector")
            rows[condition].append({"id":item["id"],
                                    "speaker_id":item["speaker_id"],
                                    "vector":vector})
        if i%12==0:print("ENCODED",i,"/",len(clips),"seconds",round(time.monotonic()-started,1),flush=True)
    outcomes={}
    for condition in conditions:
        x=rows[condition]
        outcomes[condition]={
          "open_set_0_84":open_set_known_unknown(x,.84,.07),
          "open_set_prior_0_632":open_set_known_unknown(x,args.frozen_threshold,.07),
          "pair_0_84":rates(make_pairs(x),.84),
          "pair_prior_0_632":rates(make_pairs(x),args.frozen_threshold)}
    result={
        "schema":"titanet-vctk-acoustic-stress-v1",
        "date":"2026-11-11",
        "source":"VCTK mic2, 24 fresh speakers, 3 distinct utterances per speaker",
        "frozen_policy_threshold":args.frozen_threshold,
        "never_tuned_on_current_speakers":True,
        "conditions":{"clean":"No perturbation",
          "noise15db":"Deterministic independent Gaussian noise, 15 dB speech-to-noise ratio",
          "telephone_bandpass":"FFT bandpass transition 230-380, 3250-3600 Hz",
          "echo_plus_noise15db":"140 ms 0.24 echo plus deterministic Gaussian noise at 15 dB"},
        "enrollment":"one clean utterance per speaker, two clean/degraded distinct utterances as probes",
        "model_sha256":sha256_file(model),
        "results":outcomes,
        "inference_wall_seconds":round(time.monotonic()-started,2),
        "limitations":[
          "VCTK English close-talk recording; no actual Russian acoustics or multi-speaker overlaps",
          "Synthetic noise, reverb and bandlimiting are not representative field recordings",
          "Unknown speaker false accepts counted per probe; probes from same speakers are correlated",
          "Single-speaker embeddings, not full C2 diarization or DER."]}
    target=Path(args.output)
    target.write_text(json.dumps(result,indent=2),encoding="utf8")
    print("RESULT",target,flush=True)
    for cond,x in outcomes.items():
        print("COND",cond,"fixed",x["open_set_0_84"],
              "calibrated",x["open_set_prior_0_632"],flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for field in ["manifest","model","output","ffmpeg","site-packages"]:
        p.add_argument("--"+field,required=True)
    p.add_argument("--frozen-threshold",type=float,default=0.632003402136209)
    a=p.parse_args()
    if not 0 < a.frozen_threshold < 1:p.error("invalid prior threshold")
    sys.path.insert(0,str(Path(a.site_packages).resolve()))
    evaluate(a)

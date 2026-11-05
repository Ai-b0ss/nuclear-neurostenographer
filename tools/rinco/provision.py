"""Provision six frozen Russian ELAN/WAV clips from Zenodo RINCO for Android WER.

RINCO's Voice tier is a gender label, not a verified speaker identity. This
fixture deliberately supplies only transcript WER, never cpWER or DER truth.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import wave
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".local/rinco-source/RINCO_Russian_Intonation_Corpus-v01.zip"
DEST = ROOT / ".local/androidTestAssets/rinco"
REFS = ROOT / ".local/rinco-refs"
URL = "https://zenodo.org/records/8119302/files/RINCO_Russian_Intonation_Corpus-v01.zip?download=1"
SOURCE_SHA256 = "243688e816bfdf9adbfd65ef5c6104acccd0742ec9bb78b00edb2a299a7148f1"
CASES = {
    "rinco-q144": ("INTON-EAF/1-Questions/q-144", "56164d61c921431cffeaa8ef9e4e2414b72f6a43163f708169b5a875b3baadc1", "f8de42310b1debacef6fc8007a437feb00e1305b5dbd639e66a136ec4a12bc6c"),
    "rinco-q211": ("INTON-EAF/1-Questions/q-211", "9f2348b40fb69750475e0ffd79e3a016fe81b79dc76f26c4674a461ec8447a5b", "13d718f69a3c2c4e5bdb513eacc8cf6f3dcbdb89fcee046143c77c58347c6b4f"),
    "rinco-i1321": ("INTON-EAF/2-Imperatives/i-1321", "fea9c7988bc1aadc28e42cb5a96cd02320e2dd5d40a1a44069dab959c15679d5", "e95f9210c5b815efa06621f51729f3ad626c2c1014eb12d2dc0c517a9debb095"),
    "rinco-i1112": ("INTON-EAF/2-Imperatives/i-1112", "320a2ae906853f3bdac29422ccf80ac356be4d00c5f57915343247fff20b4c09", "e327344de9d0490d901cc12a21e05628723ee4e4aa9294b9781482d1c667350a"),
    "rinco-s5": ("INTON-EAF/3-Statements/s-5", "04c4517a9d677282a0f2fae76361ca3bacd0588b34fdfd02e3e3577512eacb59", "5d2a723eb33cc4bd1c03b1f453d6954da19cd50d35f8d944c309efe01f3ba45c"),
    "rinco-s215": ("INTON-EAF/3-Statements/s-215", "edb9d2479212b326ab996f05b00f37aa63d28cbd4759abd1a67a4a07ff56e4c0", "abd0daa95037581d6a91122ba82e25eeb21a6caeb2db90279e65b47aeb66aeb3"),
}
OUTPUT_SHA256 = {
    "rinco-q144": "d580e7a02a8decd6ba0a9cb498248d28fdd3b2a310297244bf183f11f82770c0",
    "rinco-q211": "c9ccb6892a13271b5bbec38af2bf6c59cc534cc378019993be5ec164ba2c5d8f",
    "rinco-i1321": "49a91f080e1efc70d0f7b2b443713745cab0d3fd02252131f3054d6b614a134f",
    "rinco-i1112": "2951b5740c368e9685c78e75dfd58257eb499f26dd941524eef99f1345318562",
    "rinco-s5": "5eaf44d0bfce0b609b634803e19e5bd1e677297f4ae6255444c4624016dff398",
    "rinco-s215": "dc9952ef0619d2bbaf47241685c0a2134a356ba60bcadf5010db7f953d1b146d",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transcript(eaf: bytes) -> list[dict]:
    root = ET.fromstring(eaf)
    slots = {x.attrib["TIME_SLOT_ID"]: int(x.attrib["TIME_VALUE"])
             for x in root.find("TIME_ORDER")}
    tier = next(t for t in root.findall("TIER") if t.attrib.get("TIER_ID") == "Text")
    out = []
    for annotation in tier.findall("ANNOTATION"):
        aligned = annotation.find("ALIGNABLE_ANNOTATION")
        if aligned is None:
            continue
        start = slots[aligned.attrib["TIME_SLOT_REF1"]]
        end = slots[aligned.attrib["TIME_SLOT_REF2"]]
        value = (aligned.findtext("ANNOTATION_VALUE") or "").strip()
        # The Text tier embeds editorial (a)/(b) interlocutor markers in a
        # few turns; they are labels, not acoustically spoken words.
        value = re.sub(r"\([ab]\)", "", value, flags=re.IGNORECASE).strip()
        if end > start and value:
            out.append({"start_ms": start, "end_ms": end, "text": value})
    return sorted(out, key=lambda x: (x["start_ms"], x["end_ms"]))


def main() -> None:
    import urllib.request

    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    DEST.mkdir(parents=True, exist_ok=True)
    REFS.mkdir(parents=True, exist_ok=True)
    if not SOURCE.exists():
        urllib.request.urlretrieve(URL, SOURCE)
    if sha(SOURCE.read_bytes()) != SOURCE_SHA256:
        raise ValueError("Unexpected RINCO archive SHA-256")
    plan = []
    with zipfile.ZipFile(SOURCE) as archive:
        for case, (stem, wav_sha, eaf_sha) in CASES.items():
            raw = archive.read(stem + ".wav")
            eaf = archive.read(stem + ".eaf")
            if sha(raw) != wav_sha or sha(eaf) != eaf_sha:
                raise ValueError(f"Unexpected RINCO member hash: {stem}")
            original = SOURCE.parent / (case + "-source.wav")
            original.write_bytes(raw)
            output = DEST / (case + ".wav")
            subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error",
                            "-i", str(original), "-ar", "16000", "-ac", "1",
                            "-c:a", "pcm_s16le", str(output)], check=True)
            output_hash = sha(output.read_bytes())
            if output_hash != OUTPUT_SHA256[case]:
                raise ValueError(f"Unexpected converted WAV hash: {case}")
            with wave.open(str(output), "rb") as wav:
                if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
                    raise ValueError("Unexpected converted WAV format")
                duration = wav.getnframes() * 1000 // 16000
            segments = transcript(eaf)
            if not segments or segments[-1]["end_ms"] > duration:
                raise ValueError("Transcript outside WAV")
            ref = {"id": case, "source": URL + "#" + stem,
                   "source_archive_sha256": SOURCE_SHA256,
                   "source_wav_sha256": wav_sha, "source_eaf_sha256": eaf_sha,
                   "audio_sha256": output_hash, "audio_duration_ms": duration,
                   "text_segments": segments,
                   "reference_limits": "Manual ELAN Text tier; gender labels are not speaker identities. WER only."}
            (REFS / (case + ".json")).write_text(json.dumps(ref, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            plan.append(case)
            print(case, duration, len(segments), ref["audio_sha256"])
    (DEST / "plan.tsv").write_text("\n".join(plan) + "\n")


if __name__ == "__main__":
    main()

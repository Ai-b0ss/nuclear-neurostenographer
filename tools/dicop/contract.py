"""Pinned DiCoP research contract; imports no model or audio dependencies."""

UPSTREAM_REPOSITORY = "https://github.com/BUTSpeechFIT/DiCoP"
UPSTREAM_COMMIT = "b9ccee411877f5e8da42e56ed27e693829f80ce1"
CHECKPOINT_ID = "BUT-FIT/DiCoP_v0.1"
BASE_MODEL = "nvidia/parakeet-tdt-0.6b-v2"
PARAMETER_COUNT = 618_000_000
CHECKPOINT_LANGUAGE = "en"
MISSING_RUSSIAN_CHECKPOINT = "missing Russian-proven checkpoint"
COMMON_FRAGMENTS_MISSING = "общие C2 turns/reference fragments ещё не подготовлены"

UPSTREAM_URLS = {
    "readme": f"{UPSTREAM_REPOSITORY}/blob/{UPSTREAM_COMMIT}/README.md",
    "infer": f"{UPSTREAM_REPOSITORY}/blob/{UPSTREAM_COMMIT}/infer.py",
    "audio": f"{UPSTREAM_REPOSITORY}/blob/{UPSTREAM_COMMIT}/utils/audio.py",
    "rttm": f"{UPSTREAM_REPOSITORY}/blob/{UPSTREAM_COMMIT}/utils/rttm.py",
    "checkpoint": f"https://huggingface.co/{CHECKPOINT_ID}",
}


def upstream_contract():
    return {
        "repository": UPSTREAM_REPOSITORY,
        "commit": UPSTREAM_COMMIT,
        "sources": UPSTREAM_URLS,
        "inference": {
            "input": "RTTM + audio directory",
            "output": "STM",
            "audio_layout": "audio/{session}.wav",
            "rttm_layout": "rttm/{session}.rttm",
            "session_rule": "RTTM field 2 must equal the audio filename stem",
            "rttm_time_unit": "seconds; start and duration",
        },
    }


def checkpoint_contract():
    return {
        "id": CHECKPOINT_ID,
        "base_model": BASE_MODEL,
        "parameters": PARAMETER_COUNT,
        "language": CHECKPOINT_LANGUAGE,
        "russian_proven": False,
        "downloaded": False,
        "inference_run": False,
        "reason": MISSING_RUSSIAN_CHECKPOINT,
    }

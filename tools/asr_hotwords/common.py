"""Shared helpers: A3 recognizer factory (greedy / modified beam / beam + hotwords) and bpe.vocab generation.
GigaAM v3 e2e RNN-T tokens.txt is a SentencePiece piece list without scores; sherpa-onnx (>= PR #3077, Feb 2026) needs
`bpe.vocab` ("piece<TAB>score") to split hotwords into model tokens. All scores are 0, so the split is the one with the
fewest pieces (ties broken by the tokenizer) — an approximation of the real SentencePiece segmentation, recorded as such."""
from pathlib import Path
import sherpa_onnx as so

N = "e2e_rnnt"

def bpe_vocab(model_dir: Path) -> Path:
    out = model_dir / "bpe.vocab.generated"
    if not out.exists():
        lines = []
        for line in (model_dir / f"gigaam_v3_{N}_tokens.txt").read_text(encoding="utf8").splitlines():
            piece = line.rsplit(" ", 1)[0]
            lines.append(f"{piece}\t0")
        out.write_text("\n".join(lines) + "\n", encoding="utf8")
    return out

def recognizer(model_dir: Path, method: str, paths: int = 4, score: float = 1.5, threads: int = 4):
    d = model_dir
    kw = dict(num_threads=threads, decoding_method=method, model_type="nemo_transducer")
    if method == "modified_beam_search":
        kw.update(max_active_paths=paths, hotwords_score=score, modeling_unit="bpe", bpe_vocab=str(bpe_vocab(d)))
    return so.OfflineRecognizer.from_transducer(str(d/f"gigaam_v3_{N}_encoder_int8.onnx"), str(d/f"gigaam_v3_{N}_decoder.onnx"),
        str(d/f"gigaam_v3_{N}_joint.onnx"), str(d/f"gigaam_v3_{N}_tokens.txt"), **kw)

def decode(rec, samples, sr, hotwords=None):
    s = rec.create_stream(hotwords=hotwords) if hotwords else rec.create_stream()
    s.accept_waveform(sr, samples); rec.decode_stream(s)
    return s.result.text.strip()

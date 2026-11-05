"""Reference "terms" for the hotwords experiment: Latin-script words and capitalised words that are not sentence-initial
(names, brands, products, tech terms), taken verbatim from the human reference. Per-clip lists are an ORACLE (upper bound:
the user knows exactly which words will be said, in the spoken form). Distractor lists come from a clip of another
episode, minus anything said in this clip: they measure false insertion of terms that were NOT spoken."""
import re, unicodedata

WORD = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*")

def norm(w): return unicodedata.normalize("NFKC", w).lower().replace("ё", "е")

def terms(ref: str):
    out = []
    for sent in re.split(r"(?<=[.!?…])\s+|[«»\"]", unicodedata.normalize("NFKC", ref)):
        ws = WORD.findall(sent)
        for i, w in enumerate(ws):
            latin = bool(re.search(r"[A-Za-z]", w))
            cap = w[0].isupper() and i > 0 and w not in ("Я",)
            if latin or cap:
                out.append(w)
    return out

def hotword_string(words): return "/".join(dict.fromkeys(words))

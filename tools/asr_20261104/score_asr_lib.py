"""Shared helpers (words/align/norm2) split from score_asr.py head for run_stress.py."""
import csv, json, re, sys, unicodedata
from pathlib import Path

def words(t): return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", t).lower().replace("ё", "е"))
from num2words import num2words
FILL = re.compile(r"^(э+|м+|эм+|мм+|ы+|хм+|а+|ну)$")
def norm2(t):
    """SUPPLEMENTARY normalization (NORM2): glue '300 000', digits->Russian words (num2words, nominative, no agreement),
    then drop pure-filler tokens (э, ээ, м, мм, эм, ы, хм) from BOTH sides. 'а' and 'ну' are real words and are kept."""
    t = re.sub(r"(?<=\d)[  ](?=\d{3})", "", unicodedata.normalize("NFKC", t))
    t = re.sub(r"\d+", lambda m: " " + num2words(int(m.group()), lang="ru") + " ", t)
    return [w for w in words(t) if not re.match(r"^(э+|м+|эм+|мм+|ы+|хм+)$", w)]
def chars(w): return list(" ".join(w))
def align(r, h):
    n, m = len(r), len(h); D = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1): D[i][0] = i
    for j in range(m+1): D[0][j] = j
    for i in range(1, n+1):
        for j in range(1, m+1):
            D[i][j] = min(D[i-1][j-1] + (r[i-1] != h[j-1]), D[i-1][j] + 1, D[i][j-1] + 1)
    i, j, S, De, I, pairs = n, m, 0, 0, 0, []
    while i or j:
        if i and j and D[i][j] == D[i-1][j-1] + (r[i-1] != h[j-1]):
            if r[i-1] != h[j-1]: S += 1
            else: pairs.append((i-1, j-1))
            i, j = i-1, j-1
        elif i and D[i][j] == D[i-1][j] + 1: De += 1; i -= 1
        else: I += 1; j -= 1
    return S, De, I, pairs[::-1]
def ptoks(t):
    """[(word, punct_class)] punct_class: '' / ',' / '.'(terminal . ! ? …)"""
    out = []
    for m in re.finditer(r"([^\W_]+(?:[-'][^\W_]+)*)([^\w\s]*)", unicodedata.normalize("NFKC", t)):
        p = m.group(2)
        c = "." if re.search(r"[.!?…]", p) else ("," if re.search(r"[,;:—–-]", p) else "")
        for w in words(m.group(1)): out.append((w, c))
    return out

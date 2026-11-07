"""Word recovery inside independently annotated overlap, without identity assumptions."""
from metrics import in_overlap, overlap_spans
from score_transcript import words


def _matches(reference_words, hypothesis_words, tolerance_ms):
    edges = []
    for reference in reference_words:
        reference_midpoint = (reference["start_ms"] + reference["end_ms"]) / 2
        edges.append([
            index for index, hypothesis in enumerate(hypothesis_words)
            if words(reference["text"]) == words(hypothesis["text"])
            and abs(reference_midpoint - (hypothesis["start_ms"] + hypothesis["end_ms"]) / 2) <= tolerance_ms
        ])
    assigned = {}

    def assign(index, seen):
        for candidate in edges[index]:
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate not in assigned or assign(assigned[candidate], seen):
                assigned[candidate] = index
                return True
        return False

    return sum(assign(index, set()) for index in range(len(edges)))


def word_recovery(reference, baseline_words, candidate_words, tolerance_ms=250):
    if type(tolerance_ms) is not int or tolerance_ms < 0:
        raise ValueError("Nonnegative integer tolerance required")
    spans = overlap_spans(reference["diarization"])
    overlap_reference = [segment for segment in reference["text_segments"] if in_overlap(segment, spans)]
    for group in (overlap_reference, baseline_words, candidate_words):
        if any(len(words(segment["text"])) != 1 for segment in group):
            raise ValueError("Word recovery requires one normalized word per interval")
    baseline = _matches(overlap_reference, baseline_words, tolerance_ms)
    candidate = _matches(overlap_reference, candidate_words, tolerance_ms)
    return dict(status="SCORED", tolerance_ms=tolerance_ms, reference_overlap_words=len(overlap_reference),
                baseline_correct_words=baseline, candidate_correct_words=candidate,
                recovered_correct_words=candidate - baseline,
                definition="Net change in maximum-cardinality one-to-one lexical matches inside manual reference overlap; speaker identity is not assumed")

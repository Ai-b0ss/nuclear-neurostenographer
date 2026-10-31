// Copyright 2026 Nuclear Neurostenographer contributors
// SPDX-License-Identifier: Apache-2.0
#ifndef NEUROSTENOGRAPHER_SAFE_DIARIZATION_LABELS_H_
#define NEUROSTENOGRAPHER_SAFE_DIARIZATION_LABELS_H_
#include <cstdint>
#include <vector>
#include "sherpa-onnx/csrc/math.h"

namespace sherpa_onnx {
// -1 means speech exists but global identity is not supported by cluster votes.
// Never select a zero-vote cluster to satisfy a segmentation speaker count.
inline std::vector<int32_t> SafeDiarizationFrameLabels(
    const int32_t *votes, int32_t size, int32_t requested) {
  if (requested <= 0) return {};
  int32_t supported = 0;
  for (int32_t i = 0; i < size; ++i) supported += votes[i] > 0;
  if (requested > supported) return {-1};
  return TopkIndex(votes, size, requested);
}
}  // namespace sherpa_onnx
#endif

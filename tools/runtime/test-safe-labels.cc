// Authored numeric tests of actual patched helpers, not diarization accuracy.
#include <cassert>
#include <cstdint>
#include <vector>
#include "sherpa-onnx/csrc/safe-diarization-labels.h"
int main() {
  using sherpa_onnx::SafeDiarizationFrameLabels;
  using sherpa_onnx::TopkIndex;
  const int32_t one[] = {4};
  const int32_t votes[] = {0, 3, 1};
  assert((TopkIndex(one, 1, 2) == std::vector<int32_t>{0}));
  assert(TopkIndex(one, 1, -1).empty());
  assert(TopkIndex<int32_t>(nullptr, 0, 2).empty());
  assert((SafeDiarizationFrameLabels(one, 1, 2) == std::vector<int32_t>{-1}));
  assert((SafeDiarizationFrameLabels(votes, 3, 3) == std::vector<int32_t>{-1}));
  assert((SafeDiarizationFrameLabels(votes, 3, 2) == std::vector<int32_t>{1, 2}));
  assert((SafeDiarizationFrameLabels(votes, 3, 1) == std::vector<int32_t>{1}));
  assert(SafeDiarizationFrameLabels(votes, 3, 0).empty());
  assert((SafeDiarizationFrameLabels(nullptr, 0, 1) == std::vector<int32_t>{-1}));
}

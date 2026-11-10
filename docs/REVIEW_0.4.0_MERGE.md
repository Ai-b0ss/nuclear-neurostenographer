# Post-hackathon integration review

Date: 2026-11-10. Base: main e5eae26f. Original PR head: dcbe9804.

## Findings and resolution
1. Main already contained new audio playback and ETA. Reapplied the post-hackathon ASR/VAD and long-file changes to main rather than replacing the file.
2. Speech-window union could output a 1-99 ms interval after a 20s cut. This violates OfflineAsr's >=100 ms invariant and can abort an entire recording. Rebalanced last windows and added explicit boundary tests.
3. Changed experimental offline-first diarization but left a stale preview-first provenance label. Corrected it.
4. Global identity across five-minute long-file blocks is NOT implemented; IDs remain scoped and are not treated as globally stable.

## Evidence and outstanding checks
- Pre-integration 0.4.0 branch: 20 groups of core tests, signed Android Debug/Release builds and lint passed on Windows.
- Integrated branch: not rebuilt on Windows at the time of this review because the Windows Bridge disconnected. CI for the integration commit must be checked before marking this code stable.
- Signed 0.4.0 APK in the original branch does not include later main commits. Do not distribute it as an integrated binary.
- No Moodle Bridge changes and no physical-device validation in this review.

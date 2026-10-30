# Model candidates and references (30 Oct 2026)

Current ASR experiment: GigaAM v3 CTC INT8, HF revision `32a4c7cc81809bd132e2d935ab99e9e6ab47fbec`, model SHA-256 `f86ebfa0429ced91be6054fc344827e9c6c2572f3c318416cd974b06f66437ec`, 224,721,476 bytes. 16 kHz / 64 features, CPU greedy decoding through sherpa-onnx 1.12.20. Both tokens and MIT LICENSE are pinned in `tools/provision_asr.py`. Windows JNI smoke passed; Android/device evidence remains separate. **Full upstream runtime AAR contains GPL TTS dependencies; APK distribution is blocked pending ASR-only runtime verification.** See [runtime license review](RUNTIME_LICENSES.md) and [progress](PROGRESS.md).

| Capability | Candidate | Implementation reference | Important notes |
|---|---|---|---|
| Russian ASR | GigaAM v3 CTC INT8 | https://github.com/k2-fsa/sherpa-onnx/issues/2852 | sherpa-onnx model bundle exists. Check exact weight license. Non-streaming model. |
| Russian ASR alternative | T-one Russian ONNX | https://k2-fsa.github.io/sherpa/onnx/pretrained_models/online-ctc/t-one-ctc-models.html | Expects 8 kHz audio according to converter docs. Verify accuracy and license. |
| Compact backup | Small Russian Zipformer | https://k2-fsa.github.io/sherpa/onnx/pretrained_models/ | Faster/smaller candidate; performance needs device tests. |
| VAD | Silero VAD ONNX | https://github.com/snakers4/silero-vad | Offline speech-region detector; not diarization. |
| Speaker segmentation | pyannote segmentation 3.0 | https://huggingface.co/pyannote/segmentation-3.0 | Handles 10 s windows, up to 3 local speakers and overlaps; requires additional global speaker embeddings/clustering. |
| Speaker embeddings | 3D-Speaker ERes2Net or CAM++ | https://github.com/modelscope/3D-Speaker | Compare accuracy and CPU latency. |
| Android runtime | sherpa-onnx | https://github.com/k2-fsa/sherpa-onnx/tree/master/android/SherpaOnnxSpeakerDiarization | Android/Kotlin example is available. |
| Research only | Nemotron 3 Diarization ONNX | https://huggingface.co/joosthel/Nemotron-3-Diarization-ONNX | Third-party conversion not yet demonstrated inside this Android app. |

Important licensing distinction: sherpa-onnx's Apache-2.0 license does not automatically license each third-party model weight. **RevAI reverb-diarization-v1 has a non-production license**, so exclude it from a distributable production package unless legal conditions are satisfied. Source model owners determine redistribution rights. Test dataset rights separately.

**No model files or user audio belong in the public Git repository.**

Round 2 selected diarization: pinned pyannote segmentation FP32 + ERes2Net base (45.6 MB), threshold 0.9, unknown speaker count. Actual host recurrence passed; native known-mixture overlap crashed. Android implementation is process-isolated but containment/device execution remains NOT_RUN. Exact hashes, model-weight licenses and limitations: [DIARIZATION.md](DIARIZATION.md).

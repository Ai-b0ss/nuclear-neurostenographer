# Model candidates and references (30 Oct 2026)

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

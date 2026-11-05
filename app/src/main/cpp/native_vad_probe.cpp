// SPDX-License-Identifier: Apache-2.0
// Diagnostic Silero VAD pass. The pinned model is supplied by instrumentation,
// not bundled with the product APK.
#include <jni.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>
#include "c-api.h"

namespace {
void fail(JNIEnv* env, const char* message) {
    jclass type = env->FindClass("java/lang/IllegalArgumentException");
    if (type) env->ThrowNew(type, message);
}
using Detector = std::unique_ptr<const SherpaOnnxVoiceActivityDetector,
    decltype(&SherpaOnnxDestroyVoiceActivityDetector)>;
using Segment = std::unique_ptr<const SherpaOnnxSpeechSegment,
    decltype(&SherpaOnnxDestroySpeechSegment)>;
}

extern "C" JNIEXPORT jlongArray JNICALL
Java_ru_neurostenographer_app_NativeVadProbe_detect(
    JNIEnv* env, jobject, jfloatArray wave, jstring model_path, jfloat threshold) {
    if (!wave || !model_path || env->GetArrayLength(wave) < 1600 ||
        !std::isfinite(threshold) || threshold <= 0 || threshold >= 1) {
        fail(env, "Invalid VAD probe input");
        return nullptr;
    }
    const char* utf = env->GetStringUTFChars(model_path, nullptr);
    if (!utf) return nullptr;
    const std::string path(utf);
    env->ReleaseStringUTFChars(model_path, utf);
    SherpaOnnxVadModelConfig config{};
    config.silero_vad.model = path.c_str();
    config.silero_vad.threshold = threshold;
    config.silero_vad.min_silence_duration = 0.2f;
    config.silero_vad.min_speech_duration = 0.25f;
    config.silero_vad.window_size = 512;
    config.silero_vad.max_speech_duration = 20.0f;
    config.sample_rate = 16000;
    config.num_threads = 1;
    config.provider = "cpu";
    Detector detector(SherpaOnnxCreateVoiceActivityDetector(&config, 30.0f),
                      SherpaOnnxDestroyVoiceActivityDetector);
    if (!detector) {
        fail(env, "VAD probe initialization failed");
        return nullptr;
    }
    std::vector<jlong> bounds;
    const jsize size = env->GetArrayLength(wave);
    std::vector<float> chunk(8192);
    auto drain = [&]() {
        while (!SherpaOnnxVoiceActivityDetectorEmpty(detector.get())) {
            Segment segment(SherpaOnnxVoiceActivityDetectorFront(detector.get()),
                            SherpaOnnxDestroySpeechSegment);
            if (segment && segment->start >= 0 && segment->n > 0) {
                bounds.push_back(static_cast<jlong>(segment->start) * 1000 / 16000);
                bounds.push_back(static_cast<jlong>(segment->start + segment->n) * 1000 / 16000);
            }
            SherpaOnnxVoiceActivityDetectorPop(detector.get());
        }
    };
    for (jsize first = 0; first < size; first += static_cast<jsize>(chunk.size())) {
        const jsize count = std::min<jsize>(static_cast<jsize>(chunk.size()), size - first);
        env->GetFloatArrayRegion(wave, first, count, chunk.data());
        if (env->ExceptionCheck()) return nullptr;
        SherpaOnnxVoiceActivityDetectorAcceptWaveform(detector.get(), chunk.data(), count);
        drain();
    }
    SherpaOnnxVoiceActivityDetectorFlush(detector.get());
    drain();
    jlongArray output = env->NewLongArray(static_cast<jsize>(bounds.size()));
    if (output && !bounds.empty())
        env->SetLongArrayRegion(output, 0, static_cast<jsize>(bounds.size()), bounds.data());
    return output;
}

// SPDX-License-Identifier: Apache-2.0
// Opt-in C++ sherpa-onnx ASR candidate; the Kotlin side retains window/fusion policy.
#include <jni.h>
#include <algorithm>
#include <memory>
#include <string>
#include <vector>
#include "c-api.h"

namespace {
void fail(JNIEnv* env, const char* message) {
    jclass type = env->FindClass("java/lang/IllegalStateException");
    if (type) env->ThrowNew(type, message);
}
using Stream = std::unique_ptr<const SherpaOnnxOfflineStream,
    decltype(&SherpaOnnxDestroyOfflineStream)>;
using Result = std::unique_ptr<const SherpaOnnxOfflineRecognizerResult,
    decltype(&SherpaOnnxDestroyOfflineRecognizerResult)>;
}

extern "C" JNIEXPORT jlong JNICALL
Java_ru_neurostenographer_app_NativeAsrBridge_create(
    JNIEnv* env, jobject, jstring model_dir, jint threads) {
    if (!model_dir || threads < 1 || threads > 4) {
        fail(env, "Invalid native ASR configuration");
        return 0;
    }
    const char* utf = env->GetStringUTFChars(model_dir, nullptr);
    if (!utf) return 0;
    const std::string base(utf);
    env->ReleaseStringUTFChars(model_dir, utf);
    const std::string model = base + "/model.int8.onnx";
    const std::string tokens = base + "/tokens.txt";
    SherpaOnnxOfflineRecognizerConfig config{};
    config.feat_config.sample_rate = 16000;
    config.feat_config.feature_dim = 64;
    config.model_config.nemo_ctc.model = model.c_str();
    config.model_config.tokens = tokens.c_str();
    config.model_config.num_threads = threads;
    config.model_config.provider = "cpu";
    config.decoding_method = "greedy_search";
    const auto* recognizer = SherpaOnnxCreateOfflineRecognizer(&config);
    if (!recognizer) {
        fail(env, "Native ASR recognizer creation failed");
        return 0;
    }
    return reinterpret_cast<jlong>(recognizer);
}

extern "C" JNIEXPORT jstring JNICALL
Java_ru_neurostenographer_app_NativeAsrBridge_decode(
    JNIEnv* env, jobject, jlong handle, jfloatArray wave) {
    if (!handle || !wave || env->GetArrayLength(wave) < 1600 ||
        env->GetArrayLength(wave) > 20 * 16000) {
        fail(env, "Invalid native ASR window");
        return nullptr;
    }
    const auto* recognizer = reinterpret_cast<const SherpaOnnxOfflineRecognizer*>(handle);
    Stream stream(SherpaOnnxCreateOfflineStream(recognizer), SherpaOnnxDestroyOfflineStream);
    if (!stream) {
        fail(env, "Native ASR stream creation failed");
        return nullptr;
    }
    const jsize length = env->GetArrayLength(wave);
    std::vector<float> samples(std::max<jsize>(16000, length));
    env->GetFloatArrayRegion(wave, 0, length, samples.data());
    if (env->ExceptionCheck()) return nullptr;
    SherpaOnnxAcceptWaveformOffline(stream.get(), 16000, samples.data(),
        static_cast<int32_t>(samples.size()));
    SherpaOnnxDecodeOfflineStream(recognizer, stream.get());
    Result result(SherpaOnnxGetOfflineStreamResult(stream.get()),
        SherpaOnnxDestroyOfflineRecognizerResult);
    if (!result || !result->text) {
        fail(env, "Native ASR result unavailable");
        return nullptr;
    }
    return env->NewStringUTF(result->text);
}

extern "C" JNIEXPORT void JNICALL
Java_ru_neurostenographer_app_NativeAsrBridge_destroy(
    JNIEnv*, jobject, jlong handle) {
    if (handle) SherpaOnnxDestroyOfflineRecognizer(
        reinterpret_cast<const SherpaOnnxOfflineRecognizer*>(handle));
}

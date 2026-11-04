// SPDX-License-Identifier: Apache-2.0
// Isolated parity probe for the pinned sherpa-onnx C API, not a product path.
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
}

extern "C" JNIEXPORT jstring JNICALL
Java_ru_neurostenographer_app_NativeAsrProbe_recognize(
    JNIEnv* env, jobject, jfloatArray wave, jstring model_dir, jint threads) {
    if (!wave || !model_dir || env->GetArrayLength(wave) < 1600 ||
        env->GetArrayLength(wave) > 20 * 16000 || threads < 1 || threads > 4) {
        fail(env, "Invalid native ASR probe input");
        return nullptr;
    }
    const char* utf = env->GetStringUTFChars(model_dir, nullptr);
    if (!utf) return nullptr;
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
    using Recognizer = std::unique_ptr<const SherpaOnnxOfflineRecognizer,
        decltype(&SherpaOnnxDestroyOfflineRecognizer)>;
    Recognizer recognizer(SherpaOnnxCreateOfflineRecognizer(&config),
        SherpaOnnxDestroyOfflineRecognizer);
    if (!recognizer) {
        fail(env, "Native ASR recognizer creation failed");
        return nullptr;
    }
    using Stream = std::unique_ptr<const SherpaOnnxOfflineStream,
        decltype(&SherpaOnnxDestroyOfflineStream)>;
    Stream stream(SherpaOnnxCreateOfflineStream(recognizer.get()),
        SherpaOnnxDestroyOfflineStream);
    if (!stream) {
        fail(env, "Native ASR stream creation failed");
        return nullptr;
    }
    std::vector<float> samples(std::max<jsize>(16000, env->GetArrayLength(wave)));
    env->GetFloatArrayRegion(wave, 0, env->GetArrayLength(wave), samples.data());
    if (env->ExceptionCheck()) return nullptr;
    SherpaOnnxAcceptWaveformOffline(stream.get(), 16000, samples.data(),
        static_cast<int32_t>(samples.size()));
    SherpaOnnxDecodeOfflineStream(recognizer.get(), stream.get());
    using Result = std::unique_ptr<const SherpaOnnxOfflineRecognizerResult,
        decltype(&SherpaOnnxDestroyOfflineRecognizerResult)>;
    Result result(SherpaOnnxGetOfflineStreamResult(stream.get()),
        SherpaOnnxDestroyOfflineRecognizerResult);
    if (!result || !result->text) {
        fail(env, "Native ASR result unavailable");
        return nullptr;
    }
    return env->NewStringUTF(result->text);
}

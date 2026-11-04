// SPDX-License-Identifier: Apache-2.0
// Opt-in C++ sherpa-onnx ASR candidate; the Kotlin side retains window/fusion policy.
#include <jni.h>
#include <algorithm>
#include <chrono>
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
using Recognizer = std::unique_ptr<const SherpaOnnxOfflineRecognizer,
    decltype(&SherpaOnnxDestroyOfflineRecognizer)>;
using Clock = std::chrono::steady_clock;
long elapsed(Clock::time_point start, Clock::time_point end) {
    return std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
}
bool invoke(JNIEnv* env, jobject callback, jmethodID method) {
    jobject result = env->CallObjectMethod(callback, method);
    if (result) env->DeleteLocalRef(result);
    return !env->ExceptionCheck();
}
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

extern "C" JNIEXPORT jobjectArray JNICALL
Java_ru_neurostenographer_app_NativeAsrBridge_run(
    JNIEnv* env, jobject, jfloatArray wave, jstring model_dir, jint threads,
    jlongArray windows, jobject check_cancelled, jobject progress, jlongArray timing) {
    if (!wave || !model_dir || !windows || !check_cancelled || !progress || !timing ||
        threads < 1 || threads > 4 || env->GetArrayLength(windows) % 2 != 0 ||
        env->GetArrayLength(windows) > 20000 || env->GetArrayLength(timing) < 2) {
        fail(env, "Invalid native ASR pipeline input");
        return nullptr;
    }
    const jsize count = env->GetArrayLength(windows) / 2;
    const jsize wave_size = env->GetArrayLength(wave);
    std::vector<jlong> bounds(count * 2);
    env->GetLongArrayRegion(windows, 0, count * 2, bounds.data());
    if (env->ExceptionCheck()) return nullptr;
    for (jsize i = 0; i < count; ++i) {
        const jlong start = bounds[i * 2], end = bounds[i * 2 + 1];
        if (start < 0 || end - start < 100 || end - start > 20000 ||
            end * 16 > wave_size + 15 || (i && bounds[i * 2 - 1] > start)) {
            fail(env, "Invalid native ASR window bounds");
            return nullptr;
        }
    }
    jclass zero = env->FindClass("kotlin/jvm/functions/Function0");
    jclass two = env->FindClass("kotlin/jvm/functions/Function2");
    jclass integer = env->FindClass("java/lang/Integer");
    jclass string = env->FindClass("java/lang/String");
    if (!zero || !two || !integer || !string) return nullptr;
    jmethodID check = env->GetMethodID(zero, "invoke", "()Ljava/lang/Object;");
    jmethodID update = env->GetMethodID(two, "invoke", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;");
    jmethodID box = env->GetStaticMethodID(integer, "valueOf", "(I)Ljava/lang/Integer;");
    if (!check || !update || !box) return nullptr;
    if (!invoke(env, check_cancelled, check)) return nullptr;

    const auto started = Clock::now();
    const jlong handle = Java_ru_neurostenographer_app_NativeAsrBridge_create(
        env, nullptr, model_dir, threads);
    if (env->ExceptionCheck() || !handle) return nullptr;
    Recognizer recognizer(reinterpret_cast<const SherpaOnnxOfflineRecognizer*>(handle),
        SherpaOnnxDestroyOfflineRecognizer);
    const auto loaded = Clock::now();
    jobjectArray texts = env->NewObjectArray(count, string, nullptr);
    if (!texts) return nullptr;
    for (jsize i = 0; i < count; ++i) {
        if (!invoke(env, check_cancelled, check)) return nullptr;
        jobject current = env->CallStaticObjectMethod(integer, box, i + 1);
        jobject total = env->CallStaticObjectMethod(integer, box, count);
        if (env->ExceptionCheck()) return nullptr;
        jobject reported = env->CallObjectMethod(progress, update, current, total);
        env->DeleteLocalRef(current);
        env->DeleteLocalRef(total);
        if (reported) env->DeleteLocalRef(reported);
        if (env->ExceptionCheck()) return nullptr;

        const jsize first = static_cast<jsize>(bounds[i * 2] * 16);
        const jsize last = std::min<jsize>(static_cast<jsize>(bounds[i * 2 + 1] * 16), wave_size);
        std::vector<float> samples(std::max<jsize>(16000, last - first));
        env->GetFloatArrayRegion(wave, first, last - first, samples.data());
        if (env->ExceptionCheck()) return nullptr;
        Stream stream(SherpaOnnxCreateOfflineStream(recognizer.get()),
            SherpaOnnxDestroyOfflineStream);
        if (!stream) {
            fail(env, "Native ASR stream creation failed");
            return nullptr;
        }
        SherpaOnnxAcceptWaveformOffline(stream.get(), 16000, samples.data(),
            static_cast<int32_t>(samples.size()));
        SherpaOnnxDecodeOfflineStream(recognizer.get(), stream.get());
        if (!invoke(env, check_cancelled, check)) return nullptr;
        Result result(SherpaOnnxGetOfflineStreamResult(stream.get()),
            SherpaOnnxDestroyOfflineRecognizerResult);
        if (!result || !result->text) {
            fail(env, "Native ASR result unavailable");
            return nullptr;
        }
        jstring text = env->NewStringUTF(result->text);
        if (!text) return nullptr;
        env->SetObjectArrayElement(texts, i, text);
        env->DeleteLocalRef(text);
        if (env->ExceptionCheck()) return nullptr;
    }
    const jlong durations[2] = {elapsed(started, loaded), elapsed(loaded, Clock::now())};
    env->SetLongArrayRegion(timing, 0, 2, durations);
    return env->ExceptionCheck() ? nullptr : texts;
}

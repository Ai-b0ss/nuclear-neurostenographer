// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
// C++ owner of the pinned Nemotron chunk loop. Existing native kernels remain
// callable through their JNI entry points until their interfaces are unified.
#include <jni.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <vector>

extern "C" jlong Java_ru_neurostenographer_core_NativeNemotronSession_create(
    JNIEnv*, jobject, jstring, jint);
extern "C" void Java_ru_neurostenographer_core_NativeNemotronSession_destroy(
    JNIEnv*, jobject, jlong);
extern "C" jobject Java_ru_neurostenographer_core_NativeNemotronSession_run(
    JNIEnv*, jobject, jlong, jfloatArray, jint, jint, jfloatArray, jint);
extern "C" jlong Java_ru_neurostenographer_core_NativeNemotronCache_create(
    JNIEnv*, jobject, jfloatArray);
extern "C" void Java_ru_neurostenographer_core_NativeNemotronCache_destroy(
    JNIEnv*, jobject, jlong);
extern "C" jint Java_ru_neurostenographer_core_NativeNemotronCache_frames(
    JNIEnv*, jobject, jlong);
extern "C" jfloatArray Java_ru_neurostenographer_core_NativeNemotronCache_context(
    JNIEnv*, jobject, jlong);
extern "C" void Java_ru_neurostenographer_core_NativeNemotronCache_update(
    JNIEnv*, jobject, jlong, jfloatArray, jint, jfloatArray, jint, jint);
extern "C" void Java_ru_neurostenographer_core_NativeNemotronMel_write(
    JNIEnv*, jobject, jfloatArray, jfloatArray, jfloatArray, jint, jint, jfloatArray);

namespace {
constexpr int speakers = 8, mels = 128, hop = 160, factor = 8;
constexpr int chunk_limit = 340, right_context = 40;

void invalid(JNIEnv* env, const char* message) {
    jclass type = env->FindClass("java/lang/IllegalArgumentException");
    if (type) env->ThrowNew(type, message);
}

struct Handles {
    JNIEnv* env;
    jlong session = 0, cache = 0;
    ~Handles() {
        if (cache) Java_ru_neurostenographer_core_NativeNemotronCache_destroy(env, nullptr, cache);
        if (session) Java_ru_neurostenographer_core_NativeNemotronSession_destroy(env, nullptr, session);
    }
};

struct Turn { float start, end; int speaker; };
using Clock = std::chrono::steady_clock;
int64_t millis(Clock::time_point from, Clock::time_point to) {
    return std::chrono::duration_cast<std::chrono::milliseconds>(to - from).count();
}
}

extern "C" JNIEXPORT jfloatArray JNICALL
Java_ru_neurostenographer_core_NativeNemotronPipeline_run(
    JNIEnv* env, jobject, jfloatArray wave, jfloatArray filters, jfloatArray hann,
    jfloatArray silence, jstring model, jint threads, jobject check_cancelled,
    jfloat activity_threshold, jlongArray timing) {
    if (!wave || !filters || !hann || !silence || !model || !check_cancelled || !timing ||
        env->GetArrayLength(wave) < 1600 || env->GetArrayLength(filters) != mels * 257 ||
        env->GetArrayLength(hann) != 400 || env->GetArrayLength(silence) != 512 ||
        env->GetArrayLength(timing) < 2 || threads < 1 || threads > 4 ||
        !std::isfinite(activity_threshold) || activity_threshold < -2.0f || activity_threshold > 2.0f) {
        invalid(env, "Invalid native Nemotron pipeline input");
        return nullptr;
    }
    jclass callback_type = env->FindClass("kotlin/jvm/functions/Function0");
    if (!callback_type) return nullptr;
    jmethodID invoke = env->GetMethodID(callback_type, "invoke", "()Ljava/lang/Object;");
    jclass step_type = env->FindClass("ru/neurostenographer/core/NemotronStep");
    if (!invoke || !step_type) return nullptr;
    jfieldID logits_field = env->GetFieldID(step_type, "logits", "[F");
    jfieldID logit_frames_field = env->GetFieldID(step_type, "logitFrames", "I");
    jfieldID embeds_field = env->GetFieldID(step_type, "embeds", "[F");
    jfieldID embed_frames_field = env->GetFieldID(step_type, "embedFrames", "I");
    if (!logits_field || !logit_frames_field || !embeds_field || !embed_frames_field) return nullptr;

    const auto started = Clock::now();
    Handles handles{env};
    handles.session = Java_ru_neurostenographer_core_NativeNemotronSession_create(env, nullptr, model, threads);
    if (env->ExceptionCheck() || !handles.session) return nullptr;
    handles.cache = Java_ru_neurostenographer_core_NativeNemotronCache_create(env, nullptr, silence);
    if (env->ExceptionCheck() || !handles.cache) return nullptr;
    const auto loaded = Clock::now();

    const int wave_length = env->GetArrayLength(wave);
    const int mel_frames = 1 + wave_length / hop;
    const int embeddings = (mel_frames + factor - 1) / factor;
    const int valid = std::max(mel_frames - 1, 0);
    std::array<int, speakers> opened{};
    opened.fill(-1);
    std::vector<Turn> turns;
    int written = 0;
    for (int start = 0; start < embeddings;) {
        jobject result = env->CallObjectMethod(check_cancelled, invoke);
        if (env->ExceptionCheck()) return nullptr;
        env->DeleteLocalRef(result);
        if (env->PushLocalFrame(16) != JNI_OK) return nullptr;
        const int end = std::min(start + chunk_limit, embeddings);
        const int chunk_frames = end - start;
        const int mel_start = start * factor;
        const int mel_end = std::min((end + right_context) * factor, mel_frames);
        const int chunk_mel_frames = mel_end - mel_start;
        jfloatArray chunk = env->NewFloatArray(chunk_mel_frames * mels);
        if (!chunk) return nullptr;
        Java_ru_neurostenographer_core_NativeNemotronMel_write(
            env, nullptr, wave, filters, hann, mel_start, chunk_mel_frames, chunk);
        if (env->ExceptionCheck()) return nullptr;
        const int context_frames = Java_ru_neurostenographer_core_NativeNemotronCache_frames(
            env, nullptr, handles.cache);
        jfloatArray context = Java_ru_neurostenographer_core_NativeNemotronCache_context(
            env, nullptr, handles.cache);
        if (env->ExceptionCheck() || !context) return nullptr;
        jobject step = Java_ru_neurostenographer_core_NativeNemotronSession_run(
            env, nullptr, handles.session, chunk, chunk_mel_frames,
            std::max(std::min(mel_end, valid) - mel_start, 0), context, context_frames);
        if (env->ExceptionCheck() || !step) return nullptr;
        auto logits = static_cast<jfloatArray>(env->GetObjectField(step, logits_field));
        auto embeds = static_cast<jfloatArray>(env->GetObjectField(step, embeds_field));
        const int logit_frames = env->GetIntField(step, logit_frames_field);
        const int embed_frames = env->GetIntField(step, embed_frames_field);
        if (env->ExceptionCheck() || !logits || !embeds) return nullptr;
        Java_ru_neurostenographer_core_NativeNemotronCache_update(
            env, nullptr, handles.cache, logits, logit_frames, embeds, embed_frames, chunk_frames);
        if (env->ExceptionCheck()) return nullptr;
        const int from = context_frames * factor;
        const int until = std::min((context_frames + chunk_frames) * factor,
                                   from + (mel_frames - written));
        if (from > until || until > logit_frames) {
            invalid(env, "Unexpected native Nemotron logit frames");
            return nullptr;
        }
        std::vector<float> values(static_cast<size_t>((until - from) * speakers));
        if (!values.empty()) env->GetFloatArrayRegion(logits, from * speakers,
                                                     static_cast<jsize>(values.size()), values.data());
        if (env->ExceptionCheck()) return nullptr;
        for (int row = from; row < until; ++row) {
            for (int speaker = 0; speaker < speakers; ++speaker) {
                const bool active = values[static_cast<size_t>((row - from) * speakers + speaker)] > activity_threshold;
                if (active && opened[speaker] < 0) opened[speaker] = written;
                if (!active && opened[speaker] >= 0) {
                    turns.push_back({opened[speaker] * 0.01f, written * 0.01f, speaker});
                    opened[speaker] = -1;
                }
            }
            ++written;
        }
        env->PopLocalFrame(nullptr);
        start = end;
    }
    for (int speaker = 0; speaker < speakers; ++speaker)
        if (opened[speaker] >= 0)
            turns.push_back({opened[speaker] * 0.01f, written * 0.01f, speaker});
    std::stable_sort(turns.begin(), turns.end(), [](const Turn& left, const Turn& right) {
        if (left.start != right.start) return left.start < right.start;
        return left.speaker < right.speaker;
    });
    std::vector<float> packed;
    packed.reserve(turns.size() * 3);
    for (const auto& turn : turns) {
        packed.push_back(turn.start); packed.push_back(turn.end);
        packed.push_back(static_cast<float>(turn.speaker));
    }
    const auto finished = Clock::now();
    const jlong times[] = {millis(started, loaded), millis(loaded, finished)};
    env->SetLongArrayRegion(timing, 0, 2, times);
    jfloatArray output = env->NewFloatArray(static_cast<jsize>(packed.size()));
    if (output && !packed.empty()) env->SetFloatArrayRegion(output, 0, static_cast<jsize>(packed.size()), packed.data());
    return output;
}

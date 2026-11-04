// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
// C++ ONNX Runtime call boundary for the pinned Nemotron 3 INT8 model.
#include <jni.h>
#include <dlfcn.h>
#include <array>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

#define ORT_API_MANUAL_INIT
#include "onnxruntime_cxx_api.h"

namespace {
void fail(JNIEnv* env, const char* message) {
    jclass type = env->FindClass("java/lang/IllegalStateException");
    if (type) env->ThrowNew(type, message);
}

void init_ort() {
    static const bool initialized = [] {
        void* library = dlopen("libonnxruntime.so", RTLD_NOW | RTLD_LOCAL);
        if (!library) {
            const char* error = dlerror();
            throw std::runtime_error(error ? error : "Cannot load libonnxruntime.so");
        }
        using ApiBase = const OrtApiBase* (*)();
        auto entry = reinterpret_cast<ApiBase>(dlsym(library, "OrtGetApiBase"));
        if (!entry) throw std::runtime_error("OrtGetApiBase missing");
        const OrtApi* api = entry()->GetApi(ORT_API_VERSION);
        if (!api) throw std::runtime_error("ONNX Runtime API version mismatch");
        Ort::InitApi(api);
        return true;
    }();
    (void)initialized;
}

struct Session {
    Ort::Env env;
    Ort::Session session{nullptr};
    Session(const char* model, int threads) : env(ORT_LOGGING_LEVEL_WARNING, "nemotron_c2") {
        Ort::SessionOptions options;
        options.SetIntraOpNumThreads(threads);
        session = Ort::Session(env, model, options);
    }
};

Session* handle(jlong value) { return reinterpret_cast<Session*>(static_cast<intptr_t>(value)); }

std::vector<float> copy(JNIEnv* env, jfloatArray array) {
    std::vector<float> out(static_cast<size_t>(env->GetArrayLength(array)));
    if (!out.empty()) env->GetFloatArrayRegion(array, 0, static_cast<jsize>(out.size()), out.data());
    return out;
}
}

extern "C" JNIEXPORT jlong JNICALL
Java_ru_neurostenographer_core_NativeNemotronSession_create(
    JNIEnv* env, jobject, jstring model_path, jint threads) {
    if (!model_path || threads < 1 || threads > 4) {
        fail(env, "Invalid Nemotron session configuration"); return 0;
    }
    const char* path = env->GetStringUTFChars(model_path, nullptr);
    if (!path) return 0;
    jlong result = 0;
    try {
        init_ort();
        result = static_cast<jlong>(reinterpret_cast<intptr_t>(new Session(path, threads)));
    } catch (const std::exception& error) { fail(env, error.what()); }
    env->ReleaseStringUTFChars(model_path, path);
    return result;
}

extern "C" JNIEXPORT void JNICALL
Java_ru_neurostenographer_core_NativeNemotronSession_destroy(JNIEnv*, jobject, jlong value) {
    delete handle(value);
}

extern "C" JNIEXPORT jobject JNICALL
Java_ru_neurostenographer_core_NativeNemotronSession_run(
    JNIEnv* env, jobject, jlong value, jfloatArray mel_array, jint mel_frames, jint mel_length,
    jfloatArray context_array, jint context_frames) {
    Session* model = handle(value);
    if (!model || mel_frames < 0 || mel_length < 0 || mel_length > mel_frames || context_frames < 0 ||
        env->GetArrayLength(mel_array) != static_cast<int64_t>(mel_frames) * 128 ||
        env->GetArrayLength(context_array) != static_cast<int64_t>(context_frames) * 512) {
        fail(env, "Invalid Nemotron input dimensions"); return nullptr;
    }
    try {
        std::vector<float> mel = copy(env, mel_array), context = copy(env, context_array);
        int64_t valid = mel_length, cached = context_frames;
        const std::array<int64_t, 3> mel_shape{1, mel_frames, 128}, context_shape{1, context_frames, 512};
        const Ort::MemoryInfo memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
        std::array<Ort::Value, 4> inputs{
            Ort::Value::CreateTensor<float>(memory, mel.data(), mel.size(), mel_shape.data(), mel_shape.size()),
            Ort::Value::CreateTensor<int64_t>(memory, &valid, 1, nullptr, 0),
            Ort::Value::CreateTensor<float>(memory, context.data(), context.size(), context_shape.data(), context_shape.size()),
            Ort::Value::CreateTensor<int64_t>(memory, &cached, 1, nullptr, 0),
        };
        const char* input_names[] = {"chunk_mel", "chunk_mel_length", "context_embeds", "context_length"};
        const char* output_names[] = {"logits", "embeds"};
        auto outputs = model->session.Run(Ort::RunOptions{nullptr}, input_names, inputs.data(),
                                           inputs.size(), output_names, 2);
        const auto logits_shape = outputs[0].GetTensorTypeAndShapeInfo().GetShape();
        const auto embeds_shape = outputs[1].GetTensorTypeAndShapeInfo().GetShape();
        if (logits_shape.size() != 3 || embeds_shape.size() != 3 || logits_shape[0] != 1 ||
            embeds_shape[0] != 1 || logits_shape[2] != 8 || embeds_shape[2] != 512 ||
            logits_shape[1] < 0 || embeds_shape[1] < 0) {
            throw std::runtime_error("Unexpected Nemotron output shape");
        }
        const auto logits_count = static_cast<jsize>(logits_shape[1] * 8);
        const auto embeds_count = static_cast<jsize>(embeds_shape[1] * 512);
        jfloatArray logits = env->NewFloatArray(logits_count);
        jfloatArray embeds = env->NewFloatArray(embeds_count);
        if (!logits || !embeds) return nullptr;
        env->SetFloatArrayRegion(logits, 0, logits_count, outputs[0].GetTensorData<float>());
        env->SetFloatArrayRegion(embeds, 0, embeds_count, outputs[1].GetTensorData<float>());
        jclass step = env->FindClass("ru/neurostenographer/core/NemotronStep");
        if (!step) return nullptr;
        jmethodID constructor = env->GetMethodID(step, "<init>", "([FI[FI)V");
        if (!constructor) return nullptr;
        return env->NewObject(step, constructor, logits, static_cast<jint>(logits_shape[1]),
                              embeds, static_cast<jint>(embeds_shape[1]));
    } catch (const std::exception& error) {
        fail(env, error.what()); return nullptr;
    }
}

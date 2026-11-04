// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
// Native speaker cache for the pinned Nemotron diarization export.
#include <jni.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <numeric>
#include <vector>

namespace {
constexpr int hidden = 512, speakers = 8, length = 264, fifo_limit = 40;
constexpr int update_period = 300, subsampling = 8, silence_frames = 1;
constexpr float score_threshold = 0.25f, latest_boost = 0.05f;
constexpr int budget = length / speakers - silence_frames;
constexpr int min_positive = budget / 2, strong = budget * 3 / 4, weak = budget * 3 / 2;

void invalid(JNIEnv* env, const char* message) {
    jclass type = env->FindClass("java/lang/IllegalArgumentException");
    if (type) env->ThrowNew(type, message);
}

std::vector<float> copy(JNIEnv* env, jfloatArray array) {
    std::vector<float> out(static_cast<size_t>(env->GetArrayLength(array)));
    if (!out.empty()) env->GetFloatArrayRegion(array, 0, static_cast<jsize>(out.size()), out.data());
    return out;
}

float sigmoid(float x) {
    const float z = std::exp(-std::abs(x));
    return x >= 0.0f ? 1.0f / (1.0f + z) : z / (1.0f + z);
}

std::vector<int> top_k(int count, int take, const std::vector<float>& values) {
    std::vector<int> indices(static_cast<size_t>(count));
    std::iota(indices.begin(), indices.end(), 0);
    std::stable_sort(indices.begin(), indices.end(), [&](int a, int b) {
        return values[a] > values[b];
    });
    indices.resize(static_cast<size_t>(take));
    return indices;
}

struct Cache {
    std::vector<float> silence, embeds, probs, fifo;
    int cache_frames = 0, fifo_frames = 0;
    bool compressed = false;

    explicit Cache(std::vector<float> silence_values) : silence(std::move(silence_values)),
        embeds(length * hidden), probs(length * speakers), fifo(fifo_limit * hidden) {}

    std::vector<float> pooled(const std::vector<float>& logits, int logit_frames) const {
        const int frames = logit_frames / subsampling;
        std::vector<float> out(static_cast<size_t>(frames * speakers));
        for (int f = 0; f < frames; ++f) for (int s = 0; s < speakers; ++s) {
            float sum = 0.0f;
            for (int k = 0; k < subsampling; ++k)
                sum += sigmoid(logits[(f * subsampling + k) * speakers + s]);
            out[f * speakers + s] = sum / subsampling;
        }
        return out;
    }

    void boost(std::vector<float>& scored, int frames, int take, float amount) const {
        if (take <= 0) return;
        for (int s = 0; s < speakers; ++s) {
            std::vector<float> column(static_cast<size_t>(frames));
            for (int f = 0; f < frames; ++f) column[f] = scored[f * speakers + s];
            for (int f : top_k(frames, take, column)) scored[f * speakers + s] += amount;
        }
    }

    void compress(const std::vector<float>& source_embeds, const std::vector<float>& source_probs,
                  int frames, std::vector<float>& out_embeds, std::vector<float>& out_probs) const {
        std::vector<float> scored(static_cast<size_t>(frames * speakers));
        int positive[speakers]{};
        const float log05 = static_cast<float>(std::log(0.5));
        for (int f = 0; f < frames; ++f) {
            float complements = 0.0f;
            for (int s = 0; s < speakers; ++s)
                complements += std::log(std::max(1.0f - source_probs[f * speakers + s], score_threshold));
            for (int s = 0; s < speakers; ++s) {
                const float p = source_probs[f * speakers + s];
                const float value = p > 0.5f
                    ? std::log(std::max(p, score_threshold))
                        - std::log(std::max(1.0f - p, score_threshold)) + complements - log05
                    : -std::numeric_limits<float>::infinity();
                scored[f * speakers + s] = value;
                if (value > 0.0f) ++positive[s];
            }
        }
        for (int f = 0; f < frames; ++f) for (int s = 0; s < speakers; ++s) {
            const int at = f * speakers + s;
            if (scored[at] <= 0.0f && source_probs[at] > 0.5f && positive[s] >= min_positive)
                scored[at] = -std::numeric_limits<float>::infinity();
        }
        for (int f = length; f < frames; ++f) for (int s = 0; s < speakers; ++s)
            scored[f * speakers + s] += latest_boost;
        boost(scored, frames, strong, static_cast<float>(-2.0 * std::log(0.5)));
        boost(scored, frames, weak, static_cast<float>(-std::log(0.5)));

        const int rows = frames + silence_frames, sentinel = rows * speakers;
        std::vector<float> flat(static_cast<size_t>(sentinel));
        for (int s = 0; s < speakers; ++s) for (int f = 0; f < rows; ++f)
            flat[s * rows + f] = f >= frames ? std::numeric_limits<float>::infinity()
                : scored[f * speakers + s];
        std::vector<int> chosen = top_k(sentinel, length, flat);
        for (int& index : chosen)
            if (flat[index] == -std::numeric_limits<float>::infinity()) index = sentinel;
        std::sort(chosen.begin(), chosen.end());
        out_embeds.assign(length * hidden, 0.0f);
        out_probs.assign(length * speakers, 0.0f);
        for (int row = 0; row < length; ++row) {
            const int index = chosen[row];
            const int frame = index == sentinel ? frames : std::min(index % rows, frames);
            if (frame >= frames) {
                std::copy_n(silence.begin(), hidden, out_embeds.begin() + row * hidden);
            } else {
                std::copy_n(source_embeds.begin() + frame * hidden, hidden, out_embeds.begin() + row * hidden);
                std::copy_n(source_probs.begin() + frame * speakers, speakers, out_probs.begin() + row * speakers);
            }
        }
    }

    void update(const std::vector<float>& logits, int logit_frames,
                const std::vector<float>& step_embeds, int chunk_frames) {
        const std::vector<float> pooled_probs = pooled(logits, logit_frames);
        const int chunk_start = cache_frames + fifo_frames;
        const int pending = fifo_frames + chunk_frames;
        std::vector<float> fifo_embeds(static_cast<size_t>(pending * hidden));
        std::copy_n(fifo.begin(), fifo_frames * hidden, fifo_embeds.begin());
        std::copy_n(step_embeds.begin() + chunk_start * hidden, chunk_frames * hidden,
                    fifo_embeds.begin() + fifo_frames * hidden);
        int remaining = pending;
        const int popped = pending <= fifo_limit ? 0
            : std::min(std::max(update_period, pending - fifo_limit), pending);
        if (popped > 0) {
            int rows = cache_frames + popped;
            std::vector<float> cache_embeds(static_cast<size_t>(rows * hidden));
            std::vector<float> cache_probs(static_cast<size_t>(rows * speakers));
            std::copy_n(embeds.begin(), cache_frames * hidden, cache_embeds.begin());
            std::copy_n(fifo_embeds.begin(), popped * hidden, cache_embeds.begin() + cache_frames * hidden);
            const auto& source_probs = compressed ? probs : pooled_probs;
            std::copy_n(source_probs.begin(), cache_frames * speakers, cache_probs.begin());
            std::copy_n(pooled_probs.begin() + cache_frames * speakers, popped * speakers,
                        cache_probs.begin() + cache_frames * speakers);
            remaining = pending - popped;
            fifo_embeds.erase(fifo_embeds.begin(), fifo_embeds.begin() + popped * hidden);
            if (rows > length) {
                std::vector<float> kept_embeds, kept_probs;
                compress(cache_embeds, cache_probs, rows, kept_embeds, kept_probs);
                cache_embeds = std::move(kept_embeds);
                cache_probs = std::move(kept_probs);
                compressed = true;
                rows = length;
            }
            cache_frames = rows;
            std::copy_n(cache_embeds.begin(), rows * hidden, embeds.begin());
            std::copy_n(cache_probs.begin(), rows * speakers, probs.begin());
        }
        fifo_frames = remaining;
        std::copy_n(fifo_embeds.begin(), remaining * hidden, fifo.begin());
    }
};

Cache* handle(jlong value) { return reinterpret_cast<Cache*>(static_cast<intptr_t>(value)); }
}

extern "C" JNIEXPORT jlong JNICALL
Java_ru_neurostenographer_core_NativeNemotronCache_create(JNIEnv* env, jobject, jfloatArray silence) {
    if (env->GetArrayLength(silence) != hidden) { invalid(env, "Invalid silence embedding"); return 0; }
    return static_cast<jlong>(reinterpret_cast<intptr_t>(new Cache(copy(env, silence))));
}

extern "C" JNIEXPORT void JNICALL
Java_ru_neurostenographer_core_NativeNemotronCache_destroy(JNIEnv*, jobject, jlong value) {
    delete handle(value);
}

extern "C" JNIEXPORT jint JNICALL
Java_ru_neurostenographer_core_NativeNemotronCache_frames(JNIEnv* env, jobject, jlong value) {
    Cache* cache = handle(value);
    if (!cache) { invalid(env, "Closed Nemotron cache"); return 0; }
    return cache->cache_frames + cache->fifo_frames;
}

extern "C" JNIEXPORT jfloatArray JNICALL
Java_ru_neurostenographer_core_NativeNemotronCache_context(JNIEnv* env, jobject, jlong value) {
    Cache* cache = handle(value);
    if (!cache) { invalid(env, "Closed Nemotron cache"); return nullptr; }
    const int count = cache->cache_frames + cache->fifo_frames;
    jfloatArray out = env->NewFloatArray(count * hidden);
    if (!out) return nullptr;
    env->SetFloatArrayRegion(out, 0, cache->cache_frames * hidden, cache->embeds.data());
    env->SetFloatArrayRegion(out, cache->cache_frames * hidden, cache->fifo_frames * hidden,
                             cache->fifo.data());
    return out;
}

extern "C" JNIEXPORT void JNICALL
Java_ru_neurostenographer_core_NativeNemotronCache_update(
    JNIEnv* env, jobject, jlong value, jfloatArray logits, jint logit_frames,
    jfloatArray embeds, jint embed_frames, jint chunk_frames) {
    Cache* cache = handle(value);
    const int pending = cache ? cache->fifo_frames + chunk_frames : 0;
    const int popped = pending <= fifo_limit ? 0
        : std::min(std::max(update_period, pending - fifo_limit), pending);
    if (!cache || logit_frames < 0 || embed_frames < 0 || chunk_frames < 0 || chunk_frames > 340 ||
        env->GetArrayLength(logits) != static_cast<int64_t>(logit_frames) * speakers ||
        env->GetArrayLength(embeds) != static_cast<int64_t>(embed_frames) * hidden ||
        cache->cache_frames + cache->fifo_frames + chunk_frames > embed_frames ||
        cache->cache_frames + popped > logit_frames / subsampling) {
        invalid(env, "Invalid Nemotron cache step"); return;
    }
    cache->update(copy(env, logits), logit_frames, copy(env, embeds), chunk_frames);
}

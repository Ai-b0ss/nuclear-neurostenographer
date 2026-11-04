// SPDX-License-Identifier: LicenseRef-OpenMDW-1.1
// Native implementation of the pinned Nemotron log-mel transform.
#include <jni.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>

namespace {
constexpr int fft_size = 512, win_size = 400, bins = 257, mels = 128, hop = 160;
constexpr float preemphasis = 0.97f;
constexpr float log_guard = 0x1p-24f;

struct CriticalArray {
    JNIEnv* env;
    jfloatArray array;
    jfloat* data;
    CriticalArray(JNIEnv* e, jfloatArray a) : env(e), array(a),
        data(static_cast<jfloat*>(e->GetPrimitiveArrayCritical(a, nullptr))) {}
    ~CriticalArray() { if (data) env->ReleasePrimitiveArrayCritical(array, data, 0); }
    CriticalArray(const CriticalArray&) = delete;
    CriticalArray& operator=(const CriticalArray&) = delete;
};
}

extern "C" JNIEXPORT void JNICALL
Java_ru_neurostenographer_core_NativeNemotronMel_write(
    JNIEnv* env, jobject, jfloatArray wave_array, jfloatArray filter_array,
    jfloatArray hann_array, jint first, jint count, jfloatArray output_array) {
    const int wave_length = env->GetArrayLength(wave_array);
    if (first < 0 || count < 0 || env->GetArrayLength(filter_array) != mels * bins ||
        env->GetArrayLength(hann_array) != win_size ||
        static_cast<int64_t>(count) * mels > env->GetArrayLength(output_array) ||
        static_cast<int64_t>(first) + count > 1 + wave_length / hop) {
        jclass error = env->FindClass("java/lang/IllegalArgumentException");
        if (error) env->ThrowNew(error, "Invalid Nemotron mel dimensions");
        return;
    }
    CriticalArray wave(env, wave_array);
    CriticalArray filters(env, filter_array);
    CriticalArray hann(env, hann_array);
    CriticalArray output(env, output_array);
    if (!wave.data || !filters.data || !hann.data || !output.data) return;

    std::array<double, fft_size> window{}, re{}, im{};
    std::array<double, fft_size / 2> cosines{}, sines{};
    std::array<float, bins> power{};
    std::array<int, mels> starts{}, ends{};
    for (int i = 0; i < win_size; ++i) window[(fft_size - win_size) / 2 + i] = hann.data[i];
    for (int i = 0; i < fft_size / 2; ++i) {
        const double angle = 2.0 * std::acos(-1.0) * i / fft_size;
        cosines[i] = std::cos(angle); sines[i] = std::sin(angle);
    }
    for (int m = 0; m < mels; ++m) {
        int a = 0, b = bins;
        while (a < bins && filters.data[m * bins + a] == 0.0f) ++a;
        while (b > a && filters.data[m * bins + b - 1] == 0.0f) --b;
        starts[m] = a; ends[m] = b;
    }
    for (int index = 0; index < count; ++index) {
        const int frame = first + index;
        const int row = index * mels;
        if (frame == wave_length / hop) {
            for (int m = 0; m < mels; ++m) output.data[row + m] = 0.0f;
            continue;
        }
        const int start = frame * hop - fft_size / 2;
        for (int i = 0; i < fft_size; ++i) {
            const int pos = start + i;
            float value = 0.0f;
            if (pos >= 0 && pos < wave_length) {
                value = pos == 0 ? wave.data[0] :
                    wave.data[pos] - preemphasis * wave.data[pos - 1];
            }
            re[i] = value * window[i]; im[i] = 0.0;
        }
        int j = 0;
        for (int i = 1; i < fft_size; ++i) {
            int bit = fft_size >> 1;
            while (j & bit) { j ^= bit; bit >>= 1; }
            j ^= bit;
            if (i < j) std::swap(re[i], re[j]);
        }
        for (int size = 2; size <= fft_size; size *= 2) {
            const int half = size / 2, step = fft_size / size;
            for (int i = 0; i < fft_size; i += size) for (int k = 0; k < half; ++k) {
                const int w = k * step;
                const double tr = re[i + k + half] * cosines[w] + im[i + k + half] * sines[w];
                const double ti = im[i + k + half] * cosines[w] - re[i + k + half] * sines[w];
                re[i + k + half] = re[i + k] - tr;
                im[i + k + half] = im[i + k] - ti;
                re[i + k] += tr; im[i + k] += ti;
            }
        }
        for (int k = 0; k < bins; ++k) {
            const float magnitude = std::sqrt(static_cast<float>(re[k] * re[k] + im[k] * im[k]));
            power[k] = magnitude * magnitude;
        }
        for (int m = 0; m < mels; ++m) {
            float sum = 0.0f;
            for (int k = starts[m]; k < ends[m]; ++k)
                sum += filters.data[m * bins + k] * power[k];
            output.data[row + m] = std::log(sum + log_guard);
        }
    }
}

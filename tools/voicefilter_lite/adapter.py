"""Independent offline research adapter for the pinned VoiceFilter-Lite ONNX files."""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = ROOT / ".local" / "voicefilter-lite" / "models"
LOCK_PATH = Path(__file__).with_name("lock.json")
LOCK = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
MODEL_SPECS = {name: spec for name, spec in LOCK["files"].items() if name.endswith(".onnx")}
SAMPLE_RATE = 16000
ENROLLMENT_SECONDS = 3.0


class AdapterError(ValueError):
    pass


@dataclass(frozen=True)
class AudioData:
    samples: np.ndarray
    sample_rate: int
    source_frames: int
    source_channels: int

    @property
    def duration_seconds(self) -> float:
        return self.source_frames / self.sample_rate


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_models(model_dir: Path = DEFAULT_MODEL_DIR, specs=None) -> dict:
    specs = MODEL_SPECS if specs is None else specs
    result = {}
    for name, spec in specs.items():
        path = model_dir / name
        if not path.is_file():
            raise AdapterError(f"Missing pinned model: {path}")
        size = path.stat().st_size
        digest = sha256(path)
        if size != spec["size_bytes"] or digest != spec["sha256"]:
            raise AdapterError(
                f"Model integrity mismatch: {path}; expected size={spec['size_bytes']} "
                f"sha256={spec['sha256']}, got size={size} sha256={digest}"
            )
        result[name] = {"size_bytes": size, "sha256": digest}
    return result


def _decode_pcm(raw: bytes, sample_width: int, channels: int) -> np.ndarray:
    if sample_width == 1:
        values = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        values = (values - 128.0) / 128.0
    elif sample_width == 2:
        values = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 3:
        octets = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        values_i32 = octets[:, 0] | (octets[:, 1] << 8) | (octets[:, 2] << 16)
        values_i32 = (values_i32 ^ 0x800000) - 0x800000
        values = values_i32.astype(np.float32) / 8388608.0
    elif sample_width == 4:
        values = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise AdapterError(f"Unsupported PCM sample width: {sample_width * 8} bits")
    return values.reshape(-1, channels).mean(axis=1, dtype=np.float32)


def read_wav(path: Path, max_duration_seconds: float = 600.0) -> AudioData:
    path = Path(path)
    if not path.is_file():
        raise AdapterError(f"Input WAV does not exist or is not a file: {path}")
    if max_duration_seconds <= 0:
        raise AdapterError("max_duration_seconds must be positive")
    try:
        with wave.open(str(path), "rb") as stream:
            channels = stream.getnchannels()
            sample_width = stream.getsampwidth()
            sample_rate = stream.getframerate()
            frames = stream.getnframes()
            compression = stream.getcomptype()
            if compression != "NONE":
                raise AdapterError(f"Only uncompressed PCM WAV is supported: {path}")
            if channels not in (1, 2):
                raise AdapterError(f"Only mono or stereo WAV is supported, got {channels} channels")
            if sample_width not in (1, 2, 3, 4):
                raise AdapterError(f"Unsupported PCM sample width: {sample_width * 8} bits")
            if not 1000 <= sample_rate <= 384000:
                raise AdapterError(f"Invalid WAV sample rate: {sample_rate}")
            if frames <= 0:
                raise AdapterError(f"Empty WAV: {path}")
            if frames / sample_rate > max_duration_seconds:
                raise AdapterError(
                    f"WAV duration {frames / sample_rate:.3f}s exceeds limit "
                    f"{max_duration_seconds:.3f}s: {path}"
                )
            raw = stream.readframes(frames)
    except (wave.Error, EOFError, OSError) as error:
        raise AdapterError(f"Cannot read PCM WAV {path}: {error}") from error
    expected_bytes = frames * channels * sample_width
    if len(raw) != expected_bytes:
        raise AdapterError(f"Truncated WAV payload: expected {expected_bytes} bytes, got {len(raw)}")
    samples = _decode_pcm(raw, sample_width, channels)
    if samples.size != frames or not np.isfinite(samples).all():
        raise AdapterError(f"Invalid PCM samples in {path}")
    return AudioData(samples.astype(np.float32), sample_rate, frames, channels)


def resample_16k(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    if sample_rate == SAMPLE_RATE:
        return np.ascontiguousarray(samples, dtype=np.float32)
    from scipy.signal import resample_poly

    divisor = math.gcd(sample_rate, SAMPLE_RATE)
    converted = resample_poly(samples, SAMPLE_RATE // divisor, sample_rate // divisor)
    return np.ascontiguousarray(converted, dtype=np.float32)


def prepare_enrollment(samples: np.ndarray, enrollment_seconds: float = ENROLLMENT_SECONDS) -> np.ndarray:
    required = int(round(enrollment_seconds * SAMPLE_RATE))
    if required <= 0:
        raise AdapterError("Enrollment duration must be positive")
    if samples.ndim != 1 or samples.size < required:
        raise AdapterError(
            f"Enrollment must contain at least {enrollment_seconds:.3f}s at 16 kHz; "
            f"got {samples.size / SAMPLE_RATE:.3f}s"
        )
    selected = np.ascontiguousarray(samples[:required], dtype=np.float32)
    if not np.isfinite(selected).all() or float(np.max(np.abs(selected))) <= 1e-6:
        raise AdapterError("Enrollment is empty, non-finite, or digital silence")
    return selected


def prepare_mixture(samples: np.ndarray) -> np.ndarray:
    if samples.ndim != 1 or samples.size < 160:
        raise AdapterError("Mixture must contain at least 160 samples (10 ms) at 16 kHz")
    mixture = np.ascontiguousarray(samples, dtype=np.float32)
    if not np.isfinite(mixture).all():
        raise AdapterError("Mixture contains non-finite samples")
    return mixture


def mel_basis(sample_rate: int, n_fft: int, n_mels: int) -> np.ndarray:
    if n_mels <= 0 or n_fft <= 1 or sample_rate <= 0:
        raise AdapterError("Invalid mel configuration")
    fft_freqs = np.linspace(0.0, sample_rate / 2.0, n_fft // 2 + 1)
    mel_points = 2595.0 * np.log10(1.0 + np.linspace(0.0, sample_rate / 2.0, n_mels + 2) / 700.0)
    lower = (fft_freqs - mel_points[:-2, None]) / (mel_points[1:-1] - mel_points[:-2])[:, None]
    upper = (mel_points[2:, None] - fft_freqs) / (mel_points[2:] - mel_points[1:-1])[:, None]
    weights = np.maximum(0.0, np.minimum(lower, upper))
    weights *= (2.0 / (mel_points[2:] - mel_points[:-2]))[:, None]
    return weights.astype(np.float32)


def main_mel_projection(sample_rate: int, n_fft: int, n_mels: int) -> tuple[np.ndarray, np.ndarray]:
    basis = mel_basis(sample_rate, n_fft, n_mels).T
    inverse = np.linalg.pinv(basis.T, rcond=0.1).astype(np.float32)
    return basis, inverse


def stft_power(samples: np.ndarray, n_fft: int, win_length: int, hop: int, window: np.ndarray) -> np.ndarray:
    if samples.size < n_fft:
        raise AdapterError(f"Need at least {n_fft} samples for STFT, got {samples.size}")
    if window.shape != (win_length,):
        raise AdapterError("STFT window shape mismatch")
    count = 1 + (samples.size - n_fft) // hop
    frames = np.empty((count, n_fft), dtype=np.float32)
    for index in range(count):
        start = index * hop
        frames[index] = samples[start:start + n_fft]
    padded_window = np.zeros(n_fft, dtype=np.float32)
    padded_window[:win_length] = window
    spectrum = np.fft.rfft(frames * padded_window, axis=1)
    return (spectrum.real ** 2 + spectrum.imag ** 2).T.astype(np.float32)


def dvector_windows(enrollment: np.ndarray, config: dict) -> np.ndarray:
    power = stft_power(
        enrollment,
        config["n_fft"],
        config["win_length"],
        config["hop_length"],
        np.hamming(config["win_length"]).astype(np.float32),
    )
    basis = mel_basis(SAMPLE_RATE, config["n_fft"], config["n_mels"])
    features = np.log10(basis @ power + 1e-10).T.astype(np.float32)
    width = config["window"]
    stride = config["stride"]
    if features.shape[0] < width:
        features = np.pad(features, ((0, width - features.shape[0]), (0, 0)))
    count = 1 + (features.shape[0] - width) // stride
    windows = np.stack([features[index * stride:index * stride + width] for index in range(count)])
    return windows.astype(np.float32)


def stack_left(frame: np.ndarray, context: list[np.ndarray], stack: int, n_mels: int) -> np.ndarray:
    context.append(frame)
    if len(context) > stack:
        del context[:-stack]
    result = np.zeros((1, stack, n_mels), dtype=np.float32)
    offset = stack - len(context)
    for index, value in enumerate(context):
        result[0, offset + index] = value
    return result.reshape(1, 1, -1)


def write_wav_atomic(path: Path, samples: np.ndarray) -> dict:
    path = Path(path)
    if path.suffix.lower() != ".wav":
        raise AdapterError(f"Output must have .wav extension: {path}")
    if samples.ndim != 1 or samples.size == 0 or not np.isfinite(samples).all():
        raise AdapterError("Refusing to write empty or non-finite enhanced audio")
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = float(np.max(np.abs(samples)))
    scale = 1.0 / peak if peak > 1.0 else 1.0
    pcm = np.clip(np.rint(samples * scale * 32767.0), -32768, 32767).astype("<i2")
    temporary = path.with_name(path.name + ".part")
    try:
        with wave.open(str(temporary), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(SAMPLE_RATE)
            stream.writeframes(pcm.tobytes())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"output_peak_before_scaling": peak, "output_scale": scale, "output_sha256": sha256(path)}


class VoiceFilterLite:
    def __init__(self, model_dir: Path = DEFAULT_MODEL_DIR, threads: int = 1):
        if threads <= 0:
            raise AdapterError("threads must be positive")
        self.model_dir = Path(model_dir)
        self.models = verify_models(self.model_dir)
        try:
            import onnxruntime as ort
        except ImportError as error:
            raise AdapterError("onnxruntime is required; run provision.py --install-deps") from error
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.mask_session = ort.InferenceSession(
            str(self.model_dir / "voicefilter_lite.int8.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.embedder_session = ort.InferenceSession(
            str(self.model_dir / "embedder.int8.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.config = self._read_config(self.mask_session, "mask_predictor")
        self.dvector_config = self._read_config(self.embedder_session, "dvector")
        self._validate_contract()
        self.mel, self.mel_pinv = main_mel_projection(
            SAMPLE_RATE, self.config["n_fft"], self.config["n_mels"]
        )
        self.hann = np.hanning(self.config["win_length"]).astype(np.float32)
        self.layers = self.config["num_lstm_layers"]
        self.hidden = self.config["hidden_dim"]
        self.hop = self.config["hop_length"]
        self.n_fft = self.config["n_fft"]
        self.win_length = self.config["win_length"]
        self.n_mels = self.config["n_mels"]
        self.frame_stack = self.config["frame_stack"]
        self.n_freq = self.n_fft // 2 + 1
        self.buffer_frames = (self.n_fft + self.hop - 1) // self.hop
        self.buffer_length = (self.buffer_frames - 1) * self.hop + self.n_fft
        self.wss = self._window_square_sum()

    @staticmethod
    def _read_config(session, expected_kind: str) -> dict:
        metadata = session.get_modelmeta().custom_metadata_map
        if metadata.get("model_kind") != expected_kind or "voicefilter_lite_config" not in metadata:
            raise AdapterError(f"ONNX metadata does not identify {expected_kind}")
        try:
            return json.loads(metadata["voicefilter_lite_config"])
        except (TypeError, json.JSONDecodeError) as error:
            raise AdapterError(f"Invalid {expected_kind} ONNX metadata") from error

    def _validate_contract(self) -> None:
        expected = {
            "sample_rate": 16000,
            "n_fft": 1200,
            "win_length": 640,
            "hop_length": 160,
            "n_mels": 128,
            "frame_stack": 4,
            "d_vector_dim": 256,
            "hidden_dim": 512,
            "num_lstm_layers": 3,
        }
        for key, value in expected.items():
            if self.config.get(key) != value:
                raise AdapterError(f"Unsupported mask config {key}={self.config.get(key)!r}; expected {value}")
        dvector_expected = {
            "sample_rate": 16000,
            "n_fft": 512,
            "win_length": 400,
            "hop_length": 160,
            "n_mels": 40,
            "window": 80,
            "stride": 40,
            "emb_dim": 256,
        }
        for key, value in dvector_expected.items():
            if self.dvector_config.get(key) != value:
                raise AdapterError(
                    f"Unsupported d-vector config {key}={self.dvector_config.get(key)!r}; expected {value}"
                )
        if [item.name for item in self.mask_session.get_inputs()] != ["stacked_logmel", "dvec", "h0", "c0"]:
            raise AdapterError("Unexpected mask ONNX input contract")
        if [item.name for item in self.mask_session.get_outputs()] != ["mask", "f_adapt", "hN", "cN"]:
            raise AdapterError("Unexpected mask ONNX output contract")
        if [item.name for item in self.embedder_session.get_inputs()] != ["mel_window"]:
            raise AdapterError("Unexpected embedder ONNX input contract")
        if [item.name for item in self.embedder_session.get_outputs()] != ["embedding"]:
            raise AdapterError("Unexpected embedder ONNX output contract")

    def enrollment_vector(self, enrollment: np.ndarray) -> np.ndarray:
        windows = dvector_windows(enrollment, self.dvector_config)
        embeddings = self.embedder_session.run(["embedding"], {"mel_window": windows})[0]
        if embeddings.shape != (windows.shape[0], 256) or not np.isfinite(embeddings).all():
            raise AdapterError("Embedder returned invalid output")
        norms = np.linalg.norm(embeddings, axis=-1, keepdims=True) + 1e-12
        mean = (embeddings / norms).mean(axis=0)
        vector = mean / (np.linalg.norm(mean) + 1e-12)
        if not np.isfinite(vector).all():
            raise AdapterError("Enrollment produced a non-finite d-vector")
        return vector.astype(np.float32)

    def _window_square_sum(self) -> np.ndarray:
        result = np.zeros(self.buffer_length, dtype=np.float32)
        for index in range(self.buffer_frames):
            start = index * self.hop
            result[start:start + self.win_length] += self.hann ** 2
        return result

    def enhance(self, enrollment: np.ndarray, mixture: np.ndarray) -> np.ndarray:
        enrollment = prepare_enrollment(enrollment)
        mixture = prepare_mixture(mixture)
        dvec = self.enrollment_vector(enrollment).reshape(1, -1)
        h = np.zeros((self.layers, 1, self.hidden), dtype=np.float32)
        c = np.zeros_like(h)
        context: list[np.ndarray] = []
        audio_buffer = np.zeros(self.buffer_length, dtype=np.float32)
        spec_buffer = np.zeros((self.n_freq, self.buffer_frames), dtype=np.complex64)
        suppression = 0.0
        output = np.empty(((mixture.size + self.hop - 1) // self.hop) * self.hop, dtype=np.float32)
        floor = float(self.config["log_mel_floor"])
        beta = float(self.config["adaptive_w_beta"])
        slope = float(self.config["adaptive_w_a"])
        intercept = float(self.config["adaptive_w_b"])
        padded_window = np.zeros(self.n_fft, dtype=np.float32)
        padded_window[:self.win_length] = self.hann
        for chunk_index, start in enumerate(range(0, mixture.size, self.hop)):
            chunk = mixture[start:start + self.hop]
            if chunk.size < self.hop:
                chunk = np.pad(chunk, (0, self.hop - chunk.size))
            audio_buffer = np.concatenate([audio_buffer[self.hop:], chunk])
            spectrum = np.fft.rfft(audio_buffer[-self.n_fft:] * padded_window).astype(np.complex64)
            power = (spectrum.real ** 2 + spectrum.imag ** 2).astype(np.float32)
            log_mel = np.log(self.mel.T @ power + floor).astype(np.float32)
            stacked = stack_left(log_mel, context, self.frame_stack, self.n_mels)
            mask, f_adapt, h, c = self.mask_session.run(
                ["mask", "f_adapt", "hN", "cN"],
                {"stacked_logmel": stacked, "dvec": dvec, "h0": h, "c0": c},
            )
            mask = np.asarray(mask).reshape(-1).astype(np.float32)
            adapt = float(np.asarray(f_adapt).reshape(-1)[0])
            if mask.shape != (self.n_mels,) or not np.isfinite(mask).all() or not math.isfinite(adapt):
                raise AdapterError("Mask predictor returned invalid output")
            raw_linear = np.maximum(np.exp(log_mel) - floor, 0.0)
            filtered = np.maximum(mask * raw_linear, 0.0)
            target = slope * adapt + intercept
            suppression = float(np.clip(beta * suppression + (1.0 - beta) * target, 0.0, 1.0))
            enhanced = suppression * filtered + (1.0 - suppression) * raw_linear
            magnitude_squared = np.maximum(self.mel_pinv @ enhanced, 0.0)
            enhanced_spectrum = (np.sqrt(magnitude_squared) * np.exp(1j * np.angle(spectrum))).astype(np.complex64)
            spec_buffer = np.concatenate([spec_buffer[:, 1:], enhanced_spectrum.reshape(-1, 1)], axis=1)
            ola = np.zeros(self.buffer_length, dtype=np.float32)
            for frame_index in range(self.buffer_frames):
                frame = np.fft.irfft(spec_buffer[:, frame_index], n=self.n_fft)[:self.win_length]
                frame_start = frame_index * self.hop
                ola[frame_start:frame_start + self.win_length] += frame * self.hann
            nonzero = self.wss > 1e-10
            ola[nonzero] /= self.wss[nonzero]
            newest = (self.buffer_frames - 1) * self.hop
            output[chunk_index * self.hop:(chunk_index + 1) * self.hop] = ola[newest:newest + self.hop]
        result = output[:mixture.size]
        if not np.isfinite(result).all():
            raise AdapterError("Enhanced audio contains non-finite samples")
        return result

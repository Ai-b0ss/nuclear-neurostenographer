import com.k2fsa.sherpa.onnx.*;
import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;

/** ARM64 on-device ASR benchmark run via app_process (no APK). Args: <a0|a3> <modelDir> <wavDir> <listFile> <threads> <out.tsv>
 *  Output TSV: id, dur_s, dec_ms, text, plus trailing '#' lines with load_ms, VmHWM_kB, battery temp (0.1C) before/after. Hypotheses are on device only. */
public class PhoneAsrBench {
    static String read(String p) { try { return new String(Files.readAllBytes(Paths.get(p))).trim(); } catch (Exception e) { return "NA"; } }
    static long hwm() { for (String l : read("/proc/self/status").split("\n")) if (l.startsWith("VmHWM")) return Long.parseLong(l.replaceAll("[^0-9]", "")); return -1; }
    static float[] wav(String p) throws Exception {
        byte[] b = Files.readAllBytes(Paths.get(p)); int off = 44; // our WAVs are canonical 44-byte header PCM16 mono 16 kHz
        ShortBuffer sb = ByteBuffer.wrap(b, off, b.length - off).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer();
        float[] f = new float[sb.remaining()]; for (int i = 0; i < f.length; i++) f[i] = sb.get(i) / 32768f; return f;
    }
    public static void main(String[] a) throws Exception {
        System.loadLibrary("sherpa-onnx-jni");
        String mode = a[0], md = a[1], wd = a[2]; int th = Integer.parseInt(a[4]);
        OfflineModelConfig mc = new OfflineModelConfig();
        mc.setNumThreads(th); mc.setProvider("cpu");
        if (mode.equals("a3")) {
            OfflineTransducerModelConfig t = new OfflineTransducerModelConfig();
            t.setEncoder(md + "/gigaam_v3_e2e_rnnt_encoder_int8.onnx"); t.setDecoder(md + "/gigaam_v3_e2e_rnnt_decoder.onnx"); t.setJoiner(md + "/gigaam_v3_e2e_rnnt_joint.onnx");
            mc.setTransducer(t); mc.setTokens(md + "/gigaam_v3_e2e_rnnt_tokens.txt"); mc.setModelType("nemo_transducer");
        } else {
            OfflineNemoEncDecCtcModelConfig n = new OfflineNemoEncDecCtcModelConfig(); n.setModel(md + "/model.int8.onnx");
            mc.setNemo(n); mc.setTokens(md + "/tokens.txt");
        }
        OfflineRecognizerConfig cfg = new OfflineRecognizerConfig(); cfg.setModelConfig(mc); cfg.setDecodingMethod("greedy_search");
        String t0s = read("/sys/class/power_supply/battery/temp");
        long t0 = System.nanoTime(); OfflineRecognizer r = new OfflineRecognizer(null, cfg); long load = (System.nanoTime() - t0) / 1000000;
        StringBuilder out = new StringBuilder(); double tot = 0, dur = 0;
        for (String id : Files.readAllLines(Paths.get(a[3]))) {
            if (id.trim().isEmpty()) continue; float[] x = wav(wd + "/" + id.trim() + ".wav");
            long s = System.nanoTime(); OfflineStream st = r.createStream(); st.acceptWaveform(x, 16000); r.decode(st);
            String text = r.getResult(st).getText(); st.release(); long ms = (System.nanoTime() - s) / 1000000;
            double d = x.length / 16000.0; tot += ms; dur += d;
            out.append(id.trim()).append('\t').append(String.format(Locale.ROOT, "%.3f", d)).append('\t').append(ms).append('\t').append(text.replace('\t', ' ').replace('\n', ' ')).append('\n');
        }
        out.append("#mode=").append(mode).append(" threads=").append(th).append(" load_ms=").append(load).append(" rtf_total=").append(String.format(Locale.ROOT, "%.4f", tot / 1000 / dur))
           .append(" VmHWM_kB=").append(hwm()).append(" temp_before=").append(t0s).append(" temp_after=").append(read("/sys/class/power_supply/battery/temp")).append('\n');
        Files.write(Paths.get(a[5]), out.toString().getBytes("UTF-8")); System.out.print(out.substring(out.lastIndexOf("#")));
    }
}

package ru.neurostenographer.app;

import ai.onnxruntime.*;
import java.io.File;
import java.io.IOException;
import java.nio.FloatBuffer;
import java.nio.LongBuffer;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Reference ONNX RNN-T implementation ported from the team's independent HONOR bench.
 * CPU inference only. Each instance owns all ONNX sessions and MUST be closed.
 */
public final class FddtOnnxRecognizer implements AutoCloseable {
    public static final int SR = 16000, BLANK = 1024, HID = 320, DIM = 768, MAX_SYMS = 10;
    public static final class TimedPiece {
        public final long timeMs;
        public final String piece;
        public TimedPiece(long timeMs, String piece) { this.timeMs = timeMs; this.piece = piece; }
    }
    private final OrtEnvironment env;
    private final OrtSession.SessionOptions options;
    private final OrtSession encoder, decoder, joint;
    private final List<String> pieces;

    public FddtOnnxRecognizer(File dir, int threads) throws Exception {
        // Validate the tokenizer before allocating any native sessions.
        pieces = new ArrayList<>();
        for (String line : Files.readAllLines(new File(dir, "tokens.txt").toPath())) {
            int split = line.lastIndexOf(' ');
            if (split < 0 || Integer.parseInt(line.substring(split+1)) != pieces.size())
                throw new IOException("Invalid tokens.txt");
            pieces.add(line.substring(0, split));
        }
        if (pieces.size() != BLANK + 1) throw new IOException("Unexpected RNN-T token count");
        env = OrtEnvironment.getEnvironment();
        options = new OrtSession.SessionOptions();
        options.setIntraOpNumThreads(threads);
        options.setInterOpNumThreads(1);
        options.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT);
        // Avoid retaining partially initialized native sessions on construction errors.
        OrtSession e = null, d = null, j = null;
        try {
            e = openEncoder(dir,threads);
            d = env.createSession(new File(dir, "decoder.onnx").getAbsolutePath(), options);
            j = env.createSession(new File(dir, "joint.onnx").getAbsolutePath(), options);
        } catch (Exception ex) {
            if (j != null) j.close();
            if (d != null) d.close();
            if (e != null) e.close();
            options.close();
            throw ex;
        }
        encoder = e; decoder = d; joint = j;
    }

    /** Device-local CPU graph cache: weights and ORT version identify it. Never
     * distribute this hardware-optimized graph to a different device/provider.
     * A cache error falls back to the pinned original model.
     */
    private OrtSession openEncoder(File dir, int threads) throws OrtException {
        File source = new File(dir,"encoder_fddt.int8.onnx");
        File cache = new File(dir,"encoder-98d9a048-cpu-"+env.getVersion()+".optimized.onnx");
        if (cache.isFile() && cache.length()>0) {
            try (OrtSession.SessionOptions saved = new OrtSession.SessionOptions()) {
                saved.setIntraOpNumThreads(threads);
                saved.setInterOpNumThreads(1);
                saved.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.NO_OPT);
                return env.createSession(cache.getAbsolutePath(),saved);
            } catch (OrtException badCache) { cache.delete(); }
        }
        File partial = new File(cache.getAbsolutePath()+".partial.onnx");
        partial.delete();
        try (OrtSession.SessionOptions build = new OrtSession.SessionOptions()) {
            build.setIntraOpNumThreads(threads);
            build.setInterOpNumThreads(1);
            build.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT);
            build.setOptimizedModelFilePath(partial.getAbsolutePath());
            OrtSession session = env.createSession(source.getAbsolutePath(),build);
            if (partial.length()>0) partial.renameTo(cache);
            return session;
        } catch (OrtException unavailableCache) {
            // Low storage or a runtime without serialization must not lose ASR.
            return env.createSession(source.getAbsolutePath(),options);
        } finally { partial.delete(); }
    }

    /** STNO mask: flat [4, ceil(samples/16000*25)+1], row-major. */
    public List<TimedPiece> decode(float[] audio, float[] mask, int frames, Runnable cancelled)
            throws OrtException {
        if (audio.length < SR || audio.length > 25*SR || frames != (int)Math.ceil(audio.length/640.0)+1
                || mask.length != 4*frames) {
            throw new IllegalArgumentException("FDDT expects 1..25s PCM16k and [4,M] STNO");
        }
        cancelled.run();
        float[][][] encoded;
        long timeFrames;
        try (OnnxTensor ta = OnnxTensor.createTensor(env, FloatBuffer.wrap(audio), new long[]{1,audio.length});
             OnnxTensor tl = OnnxTensor.createTensor(env, LongBuffer.wrap(new long[]{audio.length}), new long[]{1});
             OnnxTensor tm = OnnxTensor.createTensor(env, FloatBuffer.wrap(mask), new long[]{1,4,frames});
             OrtSession.Result r = encoder.run(Map.of("audio",ta,"length",tl,"mask",tm))) {
            encoded = (float[][][]) r.get(0).getValue();
            Object out = r.get(1).getValue();
            timeFrames = out instanceof long[] ? ((long[])out)[0] : ((int[])out)[0];
        }
        if (timeFrames <= 0 || timeFrames > 1000) throw new IllegalStateException("Invalid encoder sequence");
        float[] hidden = new float[HID], cell = new float[HID];
        float[][] state = predict(BLANK,hidden,cell);
        List<TimedPiece> out = new ArrayList<>();
        for (int t=0;t<timeFrames;t++) {
            cancelled.run();
            float[] f = new float[DIM];
            for (int d=0;d<DIM;d++) f[d] = encoded[0][d][t];
            for (int k=0;k<MAX_SYMS;k++) {
                int id = argmax(f, state[0]);
                if (id == BLANK) break;
                if (id < 0 || id >= pieces.size()) throw new IllegalStateException("Invalid token");
                long ms = Math.round(t * (1000.0 * audio.length / SR / timeFrames));
                out.add(new TimedPiece(ms, pieces.get(id)));
                hidden = state[1]; cell = state[2];
                state = predict(id, hidden, cell);
            }
        }
        return out;
    }

    private float[][] predict(long id, float[] hidden, float[] cell) throws OrtException {
        try (OnnxTensor x = OnnxTensor.createTensor(env,LongBuffer.wrap(new long[]{id}),new long[]{1,1});
             OnnxTensor h = OnnxTensor.createTensor(env,FloatBuffer.wrap(hidden),new long[]{1,1,HID});
             OnnxTensor c = OnnxTensor.createTensor(env,FloatBuffer.wrap(cell),new long[]{1,1,HID});
             OrtSession.Result r = decoder.run(Map.of("x",x,"hi",h,"ci",c))) {
            float[][][] g = (float[][][])r.get(0).getValue();
            float[][][] ho = (float[][][])r.get(1).getValue();
            float[][][] co = (float[][][])r.get(2).getValue();
            return new float[][]{g[0][0].clone(),ho[0][0].clone(),co[0][0].clone()};
        }
    }

    private int argmax(float[] f,float[] g) throws OrtException {
        try (OnnxTensor e=OnnxTensor.createTensor(env,FloatBuffer.wrap(f),new long[]{1,DIM,1});
             OnnxTensor d=OnnxTensor.createTensor(env,FloatBuffer.wrap(g),new long[]{1,HID,1});
             OrtSession.Result r=joint.run(Map.of("enc",e,"dec",d))) {
            float[] v=((float[][][][])r.get(0).getValue())[0][0][0];
            int best=0;
            for (int i=1;i<v.length;i++) if (v[i]>v[best]) best=i;
            return best;
        }
    }
    @Override public void close() throws OrtException {
        try { joint.close(); } finally {
            try { decoder.close(); } finally {
                try { encoder.close(); } finally { options.close(); }
            }
        }
    }
}

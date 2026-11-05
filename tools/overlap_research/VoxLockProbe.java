package ru.neurostenographer.research;

import ai.onnxruntime.*;
import java.io.*;
import java.nio.*;
import java.util.*;

/** Minimal v2-graph CPU probe, no network/Android app or speaker claims.
 * Implements pinned core.py reflect pad,128-hop,Hann-squared OLA,gain -0.5.
 */
public final class VoxLockProbe {
  static float[] read(String name) throws IOException {
    byte[] b=java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(name));
    ByteBuffer v=ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN);
    if(v.getInt()!=0x46464952 || v.getInt(8)!=0x45564157)throw new IOException("Not WAV");
    int data=-1,n=0;
    for(int p=12;p+8<=b.length;){
      int id=v.getInt(p),size=v.getInt(p+4);if(size<0 || p+8L+size>b.length)throw new IOException("Bad WAV extent");
      if(id==0x20746d66 && (v.getShort(p+8)!=1 || v.getShort(p+10)!=1 || v.getInt(p+12)!=16000 || v.getShort(p+22)!=16))throw new IOException("PCM16 mono16k required");
      if(id==0x61746164){data=p+8;n=size/2;break;}p+=8+size+(size&1);
    }
    if(data<0 || n<1600)throw new IOException("Missing/short PCM");
    float[] x=new float[n];for(int i=0;i<n;i++)x[i]=v.getShort(data+2*i)/32768f;return x;
  }
  static void write(String name,float[] x)throws IOException{
    ByteBuffer b=ByteBuffer.allocate(44+2*x.length).order(ByteOrder.LITTLE_ENDIAN);
    b.putInt(0x46464952).putInt(36+2*x.length).putInt(0x45564157).putInt(0x20746d66).putInt(16).putShort((short)1).putShort((short)1).putInt(16000).putInt(32000).putShort((short)2).putShort((short)16).putInt(0x61746164).putInt(2*x.length);
    for(float a:x){if(!Float.isFinite(a))throw new IOException("Nonfinite output");b.putShort((short)Math.round(Math.max(-1,Math.min(32767/32768f,a))*32768));}
    java.nio.file.Files.write(java.nio.file.Paths.get(name),b.array());
  }
  static float[] floats(OnnxTensor t){FloatBuffer b=t.getFloatBuffer();float[] x=new float[b.remaining()];b.get(x);return x;}
  static long cpu(){try{return ((Long)Class.forName("android.os.Process").getMethod("getElapsedCpuTime").invoke(null))*1000000L;}catch(Exception e){return -1;}}
  public static void main(String[] args)throws Exception{
    if(args.length!=5)throw new IllegalArgumentException("models mix.wav enroll.wav out.wav meta.json");
    float[] x=read(args[1]),sample=read(args[2]);if(sample.length!=48000)throw new IllegalArgumentException("Enrollment must be48000 samples");
    long started=System.nanoTime();
    OrtEnvironment env=OrtEnvironment.getEnvironment();
    try(OrtSession.SessionOptions options=new OrtSession.SessionOptions()){
      options.setIntraOpNumThreads(1);
      try(OrtSession enroll=env.createSession(args[0]+"/enroll.onnx",options);OrtSession chunk=env.createSession(args[0]+"/chunk_int8.onnx",options)){
        long loaded=System.nanoTime();long cpuStart=cpu();
        try(OnnxTensor et=OnnxTensor.createTensor(env,FloatBuffer.wrap(sample),new long[]{1,48000});OrtSession.Result er=enroll.run(Collections.singletonMap("enroll",et))){
          String[] voice={"enroll_n","k","v"};Map<String,OnnxTensor> inputs=new HashMap<>();
          for(int i=0;i<3;i++)inputs.put(voice[i],(OnnxTensor)er.get(i));
          long[] state=((TensorInfo)chunk.getInputInfo().get("h").getInfo()).getShape();int count=1;for(long z:state)count*=z;
          float[] hs=new float[count],cs=new float[count];
          float[] pad=new float[x.length+512];System.arraycopy(x,0,pad,256,x.length);
          for(int i=0;i<256;i++){pad[255-i]=x[i+1];pad[256+x.length+i]=x[x.length-2-i];}
          int frames=1+(pad.length-512)/128;float[] ola=new float[frames*128+512],norm=new float[ola.length];
          float[] win=new float[512];for(int i=0;i<512;i++){float w=(float)(.5-.5*Math.cos(2*Math.PI*i/512));win[i]=w*w;}
          for(int f=0;f<frames;){
            int k=Math.min(100,frames-f);float[] part=Arrays.copyOfRange(pad,f*128,f*128+(k-1)*128+512);
            try(OnnxTensor wav=OnnxTensor.createTensor(env,FloatBuffer.wrap(part),new long[]{1,part.length});
                OnnxTensor ht=OnnxTensor.createTensor(env,FloatBuffer.wrap(hs),state);OnnxTensor ct=OnnxTensor.createTensor(env,FloatBuffer.wrap(cs),state)){
              inputs.put("wav",wav);inputs.put("h",ht);inputs.put("c",ct);
              try(OrtSession.Result r=chunk.run(inputs)){
                float[] fr=floats((OnnxTensor)r.get(0));hs=floats((OnnxTensor)r.get(1));cs=floats((OnnxTensor)r.get(2));
                if(fr.length!=k*512)throw new IllegalStateException("Frame shape mismatch");
                for(int j=0;j<k;j++)for(int i=0;i<512;i++){int at=(f+j)*128+i;ola[at]+=fr[j*512+i];norm[at]+=win[i];}
              }
            }f+=k;
          }
          float[] y=new float[x.length];float peak=0;double energy=0;int clipped=0;
          for(int i=0;i<y.length;i++){int at=i+256;y[i]=-.5f*ola[at]/(norm[at]>1e-11?norm[at]:1);peak=Math.max(peak,Math.abs(y[i]));energy+=y[i]*y[i];if(Math.abs(y[i])>=1)clipped++;}
          long finished=System.nanoTime(),cpuEnd=cpu();write(args[3],y);
          String meta="{\"status\":\"OK\",\"samples\":"+y.length+",\"load_ms\":"+(loaded-started)/1e6+",\"infer_ms\":"+(finished-loaded)/1e6+",\"process_cpu_ms\":"+((cpuStart<0 || cpuEnd<0)?-1:(cpuEnd-cpuStart)/1e6)+",\"peak\":"+peak+",\"clipped\":"+clipped+",\"rms\":"+Math.sqrt(energy/y.length)+",\"ort\":\""+env.getVersion()+"\",\"threads\":1}";
          java.nio.file.Files.write(java.nio.file.Paths.get(args[4]),meta.getBytes("UTF-8"));System.out.println(meta);
        }
      }
    }
  }
}

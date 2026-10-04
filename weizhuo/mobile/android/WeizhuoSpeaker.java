package com.snowdar.weizhuomobile;

import android.content.Context;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import java.util.Locale;
import java.util.Set;
import java.io.*;
import java.nio.*;
import java.util.concurrent.*;
import android.media.*;
import android.util.Log;
import org.json.*;
import com.k2fsa.sherpa.onnx.*;

/** On-device Chinese speech. A single lane, never interrupt with a newer action. */
public final class WeizhuoSpeaker {
    private TextToSpeech engine;
    private OfflineTts offline;
    private final android.content.SharedPreferences preferences;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private volatile boolean loading = true;
    private volatile boolean offlineAvailable = false;
    private volatile int voice = 0;
    private volatile int generation = 0;
    private volatile AudioTrack player;
    private File voiceDirectory;
    public boolean available() { return offlineAvailable; }
    public String getVoicePath() { return voiceDirectory == null ? "" : voiceDirectory.getAbsolutePath(); }
    public int getVoice() { return voice; }
    public void setVoice(int value) { if (value >= 0 && value <= 3) { voice = value; preferences.edit().putInt("announcer",value).apply(); } }
    private void unpack(Context context, String asset, File target) throws IOException {
        String[] entries=context.getAssets().list(asset);
        if(entries.length>0) { target.mkdirs(); for(String entry:entries) unpack(context,asset+"/"+entry,new File(target,entry)); }
        else { try(InputStream in=context.getAssets().open(asset);OutputStream out=new FileOutputStream(target)) { byte[] bytes=new byte[65536];int count;while((count=in.read(bytes))!=-1)out.write(bytes,0,count); } }
    }
    private void loadOffline(Context context) {
        try {
            voiceDirectory=new File(context.getFilesDir(),"voice-build-"+context.getPackageManager().getPackageInfo(context.getPackageName(),0).versionCode);
            if(!new File(voiceDirectory,".complete").exists()) { unpack(context,"Voice",voiceDirectory);new File(voiceDirectory,".complete").createNewFile(); }
            OfflineTtsVitsModelConfig vits=new OfflineTtsVitsModelConfig();
            vits.setModel(new File(voiceDirectory,"model.onnx").getPath());
            vits.setLexicon(new File(voiceDirectory,"lexicon.txt").getPath());
            vits.setTokens(new File(voiceDirectory,"tokens.txt").getPath());
            vits.setDictDir(new File(voiceDirectory,"dict").getPath());
            vits.setNoiseScale(.667f);vits.setNoiseScaleW(.8f);vits.setLengthScale(1f);
            OfflineTtsModelConfig model=new OfflineTtsModelConfig();model.setVits(vits);model.setNumThreads(4);model.setProvider("cpu");
            OfflineTtsConfig config=new OfflineTtsConfig();config.setModel(model);config.setRuleFsts(new File(voiceDirectory,"number.fst").getPath());config.setMaxNumSentences(1);config.setSilenceScale(.2f);
            offline=new OfflineTts(null,config);offlineAvailable=offline.numSpeakers()>2;
            status="四音色已就绪";Log.i("WeizhuoVoice",status);
        } catch(Exception | LinkageError error) { offlineAvailable=false;status="离线音色加载失败："+error.getMessage();Log.e("WeizhuoVoice",status,error); }
        finally { loading=false; }
    }
    public void speakClipPaths(String json) {
        if(speaking || loading)return;
        final int ticket=generation;speaking=true;status="正在组合播报";
        worker.execute(() -> { try {
            Object payload=new JSONTokener(json).nextValue();JSONArray paths=payload instanceof JSONObject?((JSONObject)payload).getJSONArray("paths"):(JSONArray)payload;
            ByteArrayOutputStream all=new ByteArrayOutputStream();int rate=0;
            if(paths.length()>1024)throw new IOException("片段过多");
            for(int i=0;i<paths.length();i++) {
                File file=new File(paths.getString(i));
                if(!file.getCanonicalPath().startsWith(new File(voiceDirectory,"Serena").getCanonicalPath()+File.separator))throw new IOException("非法音频路径");
                byte[] bytes=java.nio.file.Files.readAllBytes(file.toPath());ByteBuffer b=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
                if(b.getInt(0)!=0x46464952 || b.getInt(8)!=0x45564157)throw new IOException("不是 WAV");
                int sampleRate=0,bits=0,format=0,channels=0;
                for(int offset=12;offset+8<=bytes.length;) {
                    int tag=b.getInt(offset),size=b.getInt(offset+4),start=offset+8;
                    if(size<0 || start+size>bytes.length)throw new IOException("WAV 截断");
                    if(tag==0x20746d66) {format=b.getShort(start)&65535;channels=b.getShort(start+2);sampleRate=b.getInt(start+4);bits=b.getShort(start+14);}
                    if(tag==0x61746164) {
                        if(format!=1 || bits!=16 || channels!=1 || (rate!=0 && rate!=sampleRate))throw new IOException("WAV 格式不一致");
                        rate=sampleRate;all.write(bytes,start,size);
                    }
                    offset=start+size+(size&1);
                }
            }
            byte[] bytes=all.toByteArray();float[] samples=new float[bytes.length/2];ByteBuffer b=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
            for(int i=0;i<samples.length;i++)samples[i]=b.getShort()/32768f;
            play(samples,rate,ticket);
        } catch(Exception error){status="播报失败："+error.getMessage();Log.e("WeizhuoVoice",status,error);} finally {if(ticket==generation)speaking=false;} });
    }
    private void play(float[] samples,int rate,int ticket) throws Exception {
        if(ticket!=generation || samples.length==0)return;
        AudioTrack track=new AudioTrack.Builder().setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()).setAudioFormat(new AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_FLOAT).setSampleRate(rate).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build()).setBufferSizeInBytes(Math.max(AudioTrack.getMinBufferSize(rate,AudioFormat.CHANNEL_OUT_MONO,AudioFormat.ENCODING_PCM_FLOAT),rate)).setTransferMode(AudioTrack.MODE_STREAM).build();
        player=track;track.play();status="正在播放";Log.i("WeizhuoVoice","播放 rate="+rate+" samples="+samples.length+" voice="+voice);
        try {int offset=0;while(offset<samples.length && ticket==generation) {int n=track.write(samples,offset,Math.min(4096,samples.length-offset),AudioTrack.WRITE_BLOCKING);if(n<0)throw new IOException("音频输出错误 "+n);offset+=n;}
            long deadline=System.currentTimeMillis()+2000;while(ticket==generation && track.getPlaybackHeadPosition()<samples.length && System.currentTimeMillis()<deadline)Thread.sleep(10);
            if(ticket==generation)status="音色已就绪";
        } finally {if(player==track)player=null;track.release();}
    }
    public void stop() { generation++;speaking=false;AudioTrack track=player;if(track!=null)try{track.pause();track.flush();}catch(IllegalStateException ignored){} }
    private volatile boolean initializing = true;
    private volatile boolean speaking = false;
    private volatile boolean usable = false;
    private volatile String status = "系统语音准备中";
    private int sequence = 0;
    private volatile String current = "";

    public WeizhuoSpeaker(Context context) {
        preferences=context.getSharedPreferences("weizhuo-voice",Context.MODE_PRIVATE);
        voice=preferences.getInt("announcer",2);
        Handler main = new Handler(Looper.getMainLooper());
        worker.execute(() -> loadOffline(context.getApplicationContext()));
        engine = new TextToSpeech(context.getApplicationContext(),
            result -> main.post(() -> initialize(result)));
    }
    private void initialize(int result) {
        initializing = false;
        if (result != TextToSpeech.SUCCESS) {
            status = "系统语音引擎初始化失败";
            return;
        }
        int language = engine.setLanguage(Locale.SIMPLIFIED_CHINESE);
        if (language < TextToSpeech.LANG_AVAILABLE) {
            status = "系统中文音色未安装，请在系统语音设置下载";
            return;
        }
        Set<Voice> voices = engine.getVoices();
        Voice best = null;
        if (voices != null) for (Voice voice : voices) {
            if ("zh".equals(voice.getLocale().getLanguage()) && !voice.isNetworkConnectionRequired()
                    && (best == null || voice.getQuality() > best.getQuality())) best = voice;
        }
        if (best != null) engine.setVoice(best);
        Voice selected = engine.getVoice();
        if (selected != null && selected.isNetworkConnectionRequired()) {
            status = "系统中文离线音色未安装，请在系统语音设置下载";
            return;
        }
        engine.setSpeechRate(1.0f);
        engine.setPitch(1.0f);
        engine.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String id) { if (id.equals(current)) status = "正在播放"; }
            @Override public void onDone(String id) { finish(id, "系统音色已就绪"); }
            @Override public void onError(String id) { finish(id, "系统播报失败"); }
            @Override public void onError(String id, int error) { finish(id, "系统播报失败：" + error); }
            @Override public void onStop(String id, boolean interrupted) { finish(id, "系统音色已就绪"); }
        });
        usable = true;
        status = "系统音色已就绪";
    }
    private void finish(String id, String message) {
        if (id.equals(current)) { speaking = false; status = message; }
    }
    public boolean busy() { return (voice==0 ? initializing : loading) || speaking; }
    public String getStatus() { return status; }
    public void speakText(String text) {
        if(voice==1 || voice==2) {
            if(loading || !offlineAvailable || speaking)return;
            final int sid=voice,ticket=generation;speaking=true;status="正在合成";
            worker.execute(() -> {try {long issued=System.nanoTime();GeneratedAudio audio=offline.generate(text,sid,1f);Log.i("WeizhuoVoice","合成 ms="+(System.nanoTime()-issued)/1000000);play(audio.getSamples(),audio.getSampleRate(),ticket);}catch(Exception error){status="合成失败："+error.getMessage();Log.e("WeizhuoVoice",status,error);}finally{if(ticket==generation)speaking=false;}});return;
        }
        if (!usable || speaking) return;
        current = "weizhuo-" + (++sequence);
        speaking = true;
        Bundle params = new Bundle();
        params.putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, 1.0f);
        if (engine.speak(text, TextToSpeech.QUEUE_ADD, params, current) == TextToSpeech.ERROR)
            finish(current, "系统播报提交失败");
    }
    public void stopSpeakingAtBoundary(int ignored) {
        stop();
        current = "";
        speaking = false;
        if (engine != null) engine.stop();
    }
}

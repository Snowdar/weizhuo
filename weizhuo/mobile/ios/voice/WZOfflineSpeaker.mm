// Project-owned iOS bridge. Model inference stays off the UI/server thread.
#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>
#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>
#import <SherpaOnnxC/sherpa-onnx/c-api/c-api.h>

@interface WZOfflineSpeaker : NSObject
@property(atomic) NSInteger generation;
@property(atomic,copy) NSString *status;
@property(nonatomic,readonly) NSInteger voice;
+ (instancetype)sharedSpeaker;
- (BOOL)available;
- (BOOL)busy;
- (void)setVoice:(NSInteger)voice;
- (void)speakText:(NSString *)text;
- (void)stop;
- (void)speakClipPaths:(NSString *)json;
- (void)enqueueBuffer:(AVAudioPCMBuffer *)buffer ticket:(NSInteger)ticket issued:(NSTimeInterval)issued;
- (void)finishTicket:(NSInteger)ticket;
@end

@implementation WZOfflineSpeaker {
 dispatch_queue_t _worker;
 const SherpaOnnxOfflineTts *_tts;
 AVAudioEngine *_engine;
 AVAudioPlayerNode *_player;
 NSInteger _voice;
 NSInteger _pending;
 BOOL _available;
}
+ (instancetype)sharedSpeaker {
 static WZOfflineSpeaker *speaker; static dispatch_once_t once;
 dispatch_once(&once,^{speaker=[WZOfflineSpeaker new];});return speaker;
}
- (instancetype)init {
 if((self=[super init])) {
  _worker=dispatch_queue_create("weizhuo.offline.voice",dispatch_queue_attr_make_with_qos_class(DISPATCH_QUEUE_SERIAL,QOS_CLASS_USER_INITIATED,0));
  self.status=@"正在准备音色";
  _voice=[[NSUserDefaults standardUserDefaults] objectForKey:@"weizhuo.voice"] ? [[NSUserDefaults standardUserDefaults] integerForKey:@"weizhuo.voice"] : 2;
  if(_voice!=1 && _voice!=2)_voice=2;
  NSString *base=[[NSBundle mainBundle] pathForResource:@"Voice" ofType:nil];
  _available=base && [[NSFileManager defaultManager] fileExistsAtPath:[base stringByAppendingPathComponent:@"model.onnx"]];
  [[NSNotificationCenter defaultCenter] addObserver:self selector:@selector(stop) name:UIApplicationWillResignActiveNotification object:nil];
  if(_available)dispatch_async(_worker,^{@autoreleasepool{
   SherpaOnnxOfflineTtsConfig c={};
   NSString *model=[base stringByAppendingPathComponent:@"model.onnx"],*lex=[base stringByAppendingPathComponent:@"lexicon.txt"],*tokens=[base stringByAppendingPathComponent:@"tokens.txt"],*dict=[base stringByAppendingPathComponent:@"dict"],*numbers=[base stringByAppendingPathComponent:@"number.fst"];
   c.model.vits.model=model.UTF8String;c.model.vits.lexicon=lex.UTF8String;c.model.vits.tokens=tokens.UTF8String;c.model.vits.dict_dir=dict.UTF8String;
   c.model.vits.noise_scale=.667;c.model.vits.noise_scale_w=.8;c.model.vits.length_scale=1;
   c.model.num_threads=4;c.model.provider="cpu";c.rule_fsts=numbers.UTF8String;c.max_num_sentences=1;c.silence_scale=.2;
   self->_tts=SherpaOnnxCreateOfflineTts(&c);
   if(!self->_tts){self.status=@"音色加载失败";NSLog(@"围桌：离线语音加载失败");}
   else {self.status=@"音色已就绪";NSLog(@"围桌：离线语音模型已就绪");}
  }});
 }
 return self;
}
- (BOOL)available{return _available;}
- (BOOL)busy{return _pending>0;}
- (NSInteger)voice{return _voice;}
- (void)setVoice:(NSInteger)voice {
 if(voice!=1 && voice!=2)return;
 if(_voice!=voice){[self stop];_voice=voice;[[NSUserDefaults standardUserDefaults] setInteger:voice forKey:@"weizhuo.voice"];}
}
- (void)stop {self.generation+=1;_pending=0;[_player stop];[_engine stop];_player=nil;_engine=nil;}
- (void)finishTicket:(NSInteger)ticket {if(ticket==self.generation && _pending>0)_pending--;}
- (void)speakText:(NSString *)text {
 if(!_available || !text.length || _pending>=16 || UIApplication.sharedApplication.applicationState!=UIApplicationStateActive){self.status=@"未进入播放队列";return;}
 self.status=@"正在合成";
 text=[text substringToIndex:MIN(text.length,1000)];
 NSInteger ticket=self.generation,sid=_voice;NSTimeInterval issued=NSProcessInfo.processInfo.systemUptime;_pending++;
 dispatch_async(_worker,^{@autoreleasepool{
  if(ticket!=self.generation || NSProcessInfo.processInfo.systemUptime-issued>30 || !self->_tts){dispatch_async(dispatch_get_main_queue(),^{[self finishTicket:ticket];});return;}
  SherpaOnnxGenerationConfig cfg={};cfg.num_steps=1;cfg.sid=(int32_t)sid;cfg.speed=1;cfg.silence_scale=.2;
  const SherpaOnnxGeneratedAudio *audio=SherpaOnnxOfflineTtsGenerateWithConfig(self->_tts,text.UTF8String,&cfg,NULL,NULL);
  AVAudioPCMBuffer *buffer=nil;
  if(audio && audio->n>0 && audio->sample_rate==16000){
   AVAudioFormat *format=[[AVAudioFormat alloc] initWithCommonFormat:AVAudioPCMFormatFloat32 sampleRate:16000 channels:1 interleaved:NO];
   buffer=[[AVAudioPCMBuffer alloc] initWithPCMFormat:format frameCapacity:audio->n];buffer.frameLength=audio->n;
   memcpy(buffer.floatChannelData[0],audio->samples,audio->n*sizeof(float));
  }
  if(audio)SherpaOnnxDestroyOfflineTtsGeneratedAudio(audio);
  dispatch_async(dispatch_get_main_queue(),^{[self enqueueBuffer:buffer ticket:ticket issued:issued];});
 }});
}
- (void)enqueueBuffer:(AVAudioPCMBuffer *)buffer ticket:(NSInteger)ticket issued:(NSTimeInterval)issued {
 if(!buffer){self.status=@"未生成音频";NSLog(@"围桌：语音合成未生成音频");}
 if(!buffer || ticket!=self.generation || NSProcessInfo.processInfo.systemUptime-issued>30 || UIApplication.sharedApplication.applicationState!=UIApplicationStateActive){[self finishTicket:ticket];return;}
 NSError *error=nil;
 [[AVAudioSession sharedInstance] setCategory:AVAudioSessionCategoryPlayback mode:AVAudioSessionModeDefault options:AVAudioSessionCategoryOptionMixWithOthers error:&error];
 [[AVAudioSession sharedInstance] setActive:YES error:&error];
 if(!self->_engine){self->_engine=[AVAudioEngine new];self->_player=[AVAudioPlayerNode new];[self->_engine attachNode:self->_player];[self->_engine connect:self->_player to:self->_engine.mainMixerNode format:buffer.format];}
 if(!self->_engine.running && ![self->_engine startAndReturnError:&error]){self.status=@"音频启动失败";NSLog(@"围桌：播报音频不可用 %@",error);[self finishTicket:ticket];return;}
 [self->_player scheduleBuffer:buffer completionCallbackType:AVAudioPlayerNodeCompletionDataPlayedBack completionHandler:^(AVAudioPlayerNodeCompletionCallbackType type){dispatch_async(dispatch_get_main_queue(),^{[self finishTicket:ticket];});}];
 [self->_player play];self.status=@"正在播放";
 NSLog(@"围桌播报 sid=%ld 合成到调度=%.0fms",(long)_voice,(NSProcessInfo.processInfo.systemUptime-issued)*1000);
}
- (void)speakClipPaths:(NSString *)json {
 if(_pending>=16 || UIApplication.sharedApplication.applicationState!=UIApplicationStateActive){self.status=@"未进入播放队列";return;}
 id payload=[NSJSONSerialization JSONObjectWithData:[json dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
 BOOL preserveSamples=[payload isKindOfClass:NSDictionary.class] && [payload[@"preserveSamples"] isEqual:@YES];
 NSArray *paths=[payload isKindOfClass:NSDictionary.class]?payload[@"paths"]:payload;
 if(![paths isKindOfClass:NSArray.class] || !paths.count || paths.count>(preserveSamples?1024:120))return;
 for(id path in paths)if(![path isKindOfClass:NSString.class])return;
 NSInteger ticket=self.generation;NSTimeInterval issued=NSProcessInfo.processInfo.systemUptime;_pending++;self.status=@"正在组合播报";
 dispatch_async(_worker,^{@autoreleasepool{
  if(ticket!=self.generation){return;}
  NSMutableData *samples=[NSMutableData data];double rate=0;
  for(NSString *path in paths){
   NSError *error=nil;AVAudioFile *file=[[AVAudioFile alloc] initForReading:[NSURL fileURLWithPath:path] error:&error];
   if(!file || file.processingFormat.channelCount!=1 || (rate && rate!=file.processingFormat.sampleRate)){samples=nil;break;}
   rate=file.processingFormat.sampleRate;
   AVAudioPCMBuffer *part=[[AVAudioPCMBuffer alloc] initWithPCMFormat:file.processingFormat frameCapacity:(AVAudioFrameCount)file.length];
   if(![file readIntoBuffer:part error:&error] || !part.floatChannelData){samples=nil;break;}
   const float *a=part.floatChannelData[0];NSUInteger first=0,last=part.frameLength;
   // Only remove verified near-zero edge silence, with 20ms guards for weak consonants.
   if(!preserveSamples){
    while(first<last && fabsf(a[first])<0.00015f)first++;
    while(last>first && fabsf(a[last-1])<0.00015f)last--;
    first=first>(NSUInteger)(rate*.020)?first-(NSUInteger)(rate*.020):0;
    last=MIN(part.frameLength,last+(NSUInteger)(rate*.020));
   }
   [samples appendBytes:a+first length:(last-first)*sizeof(float)];
  }
  AVAudioPCMBuffer *buffer=nil;
  if(samples.length && rate){AVAudioFormat *format=[[AVAudioFormat alloc] initWithCommonFormat:AVAudioPCMFormatFloat32 sampleRate:rate channels:1 interleaved:NO];buffer=[[AVAudioPCMBuffer alloc] initWithPCMFormat:format frameCapacity:(AVAudioFrameCount)(samples.length/sizeof(float))];buffer.frameLength=buffer.frameCapacity;memcpy(buffer.floatChannelData[0],samples.bytes,samples.length);}
  dispatch_async(dispatch_get_main_queue(),^{[self enqueueBuffer:buffer ticket:ticket issued:issued];});
 }});
}
@end

// UIKit keyboard geometry is authoritative when WKWebView reports a stale visual viewport.
@interface WZKeyboardTracker : NSObject
@property(nonatomic,weak) WKWebView *webView;
@property(nonatomic,weak) UIScrollView *observedScroll;
@property(nonatomic) BOOL tableLocked;
@property(nonatomic) BOOL correctingOffset;
@property(nonatomic) CGRect keyboardFrame;
@property(nonatomic) double animationDuration;
@property(nonatomic) NSInteger animationCurve;
+ (instancetype)sharedTracker;
- (NSString *)stateJSON;
@end
static void *WZTableScrollContext=&WZTableScrollContext;
@implementation WZKeyboardTracker
@synthesize webView=_webView,tableLocked=_tableLocked;
+ (instancetype)sharedTracker {static WZKeyboardTracker *t;static dispatch_once_t once;dispatch_once(&once,^{t=[WZKeyboardTracker new];});return t;}
- (instancetype)init {if((self=[super init])){NSNotificationCenter *n=NSNotificationCenter.defaultCenter;[n addObserver:self selector:@selector(changed:) name:UIKeyboardWillChangeFrameNotification object:nil];[n addObserver:self selector:@selector(changed:) name:UIKeyboardDidChangeFrameNotification object:nil];[n addObserver:self selector:@selector(hidden:) name:UIKeyboardDidHideNotification object:nil];}return self;}
- (void)setWebView:(WKWebView *)web {
 if(_webView==web)return;
 [self.observedScroll removeObserver:self forKeyPath:@"contentOffset" context:WZTableScrollContext];
 _webView=web;self.observedScroll=web.scrollView;
 [self.observedScroll addObserver:self forKeyPath:@"contentOffset" options:0 context:WZTableScrollContext];
}
- (void)setTableLocked:(BOOL)locked {
 if(_tableLocked==locked)return;
 _tableLocked=locked;[self preserveTableOffset];
}
- (void)preserveTableOffset {
 // WebKit can pan focused inputs even with scrollEnabled=NO. Keep only the
 // outer table viewport still; nested DOM scrollers and the responder stay intact.
 UIScrollView *scroll=self.observedScroll;
 if(!self.tableLocked||self.correctingOffset||!scroll||CGPointEqualToPoint(scroll.contentOffset,CGPointZero))return;
 self.correctingOffset=YES;
 [scroll setContentOffset:CGPointZero animated:NO];
 self.correctingOffset=NO;
}
- (void)observeValueForKeyPath:(NSString *)key ofObject:(id)object change:(NSDictionary *)change context:(void *)context {
 if(context==WZTableScrollContext){[self preserveTableOffset];return;}
 [super observeValueForKeyPath:key ofObject:object change:change context:context];
}
- (void)dealloc {
 [self.observedScroll removeObserver:self forKeyPath:@"contentOffset" context:WZTableScrollContext];
 [NSNotificationCenter.defaultCenter removeObserver:self];
}
- (void)pushFrame {
 WKWebView *web=self.webView;if(!web)return;
 NSString *script=[NSString stringWithFormat:@"window.__weizhuoKeyboard=%@;window.dispatchEvent(new Event('weizhuokeyboard'));",[self stateJSON]];
 [web evaluateJavaScript:script completionHandler:nil];
}
- (void)changed:(NSNotification *)n {self.keyboardFrame=[n.userInfo[UIKeyboardFrameEndUserInfoKey] CGRectValue];self.animationDuration=[n.userInfo[UIKeyboardAnimationDurationUserInfoKey] doubleValue];self.animationCurve=[n.userInfo[UIKeyboardAnimationCurveUserInfoKey] integerValue];[self pushFrame];}
- (void)hidden:(NSNotification *)n {self.keyboardFrame=CGRectZero;[self pushFrame];}
- (NSString *)stateJSON {
 WKWebView *web=self.webView;CGRect bounds=web.bounds;CGRect overlap=CGRectZero;
 if(web.window && !CGRectIsEmpty(self.keyboardFrame)){CGRect frame=[web convertRect:self.keyboardFrame fromCoordinateSpace:web.window.screen.coordinateSpace];overlap=CGRectIntersection(bounds,frame);}
 BOOL visible=!CGRectIsNull(overlap) && overlap.size.height>80 && overlap.size.width>bounds.size.width*.8;
 NSDictionary *state=@{@"visible":@(visible),@"top":@(visible?CGRectGetMinY(overlap)-CGRectGetMinY(bounds):bounds.size.height),@"height":@(bounds.size.height),@"width":@(bounds.size.width),@"duration":@(self.animationDuration),@"curve":@(self.animationCurve),@"offsetX":@(web.scrollView.contentOffset.x),@"offsetY":@(web.scrollView.contentOffset.y)};
 NSData *data=[NSJSONSerialization dataWithJSONObject:state options:0 error:nil];return [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
}
@end

@interface WZSystemSpeaker : NSObject <AVSpeechSynthesizerDelegate>
- (BOOL)busy;
- (void)speakText:(NSString *)text;
- (void)stopSpeakingAtBoundary:(NSInteger)boundary;
@end
@implementation WZSystemSpeaker {
 AVSpeechSynthesizer *_synth;
 AVSpeechUtterance *_active;
 NSInteger _pending;
}
- (instancetype)init {if((self=[super init])){_synth=[AVSpeechSynthesizer new];_synth.delegate=self;[[NSNotificationCenter defaultCenter] addObserver:self selector:@selector(background:) name:UIApplicationWillResignActiveNotification object:nil];}return self;}
- (BOOL)busy{return _pending>0;}
- (void)background:(NSNotification *)n {[self stopSpeakingAtBoundary:0];}
- (void)speakText:(NSString *)text {
 if(_pending>0 || !text.length)return;
 NSError *error=nil;[[AVAudioSession sharedInstance] setCategory:AVAudioSessionCategoryPlayback mode:AVAudioSessionModeDefault options:AVAudioSessionCategoryOptionMixWithOthers error:&error];[[AVAudioSession sharedInstance] setActive:YES error:&error];
 AVSpeechUtterance *u=[AVSpeechUtterance speechUtteranceWithString:text];
 AVSpeechSynthesisVoice *best=nil;for(AVSpeechSynthesisVoice *v in AVSpeechSynthesisVoice.speechVoices)if([v.language hasPrefix:@"zh-CN"] && (!best || v.quality>best.quality))best=v;
 u.voice=best?:[AVSpeechSynthesisVoice voiceWithLanguage:@"zh-CN"];u.rate=.48;u.pitchMultiplier=1;u.preUtteranceDelay=.04;u.postUtteranceDelay=.10;
 _active=u;_pending++;[_synth speakUtterance:u];
}
- (void)stopSpeakingAtBoundary:(NSInteger)boundary {_active=nil;[_synth stopSpeakingAtBoundary:AVSpeechBoundaryImmediate];_pending=0;}
- (void)speechSynthesizer:(AVSpeechSynthesizer *)synth didFinishSpeechUtterance:(AVSpeechUtterance *)u {if(u==_active){_active=nil;_pending=0;}}
- (void)speechSynthesizer:(AVSpeechSynthesizer *)synth didCancelSpeechUtterance:(AVSpeechUtterance *)u {if(u==_active){_active=nil;_pending=0;}}
@end

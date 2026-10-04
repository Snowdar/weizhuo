const fs=require('fs'),vm=require('vm'),assert=require('assert');
let clock=Date.now();const testDate={now:()=>clock};
const source=fs.readFileSync(require('path').join(__dirname,'mobile/src/weizhuomobile/service_navigation.js'),'utf8').replaceAll('__SPEECH_READY__','true').replaceAll('__SAFE_AREA__','{}').replaceAll('__NATIVE_SPEECH__','true').replaceAll('__DUAL_VOICE__','true').replaceAll('__VOICE_CHOICE__','2').replaceAll('__VOICE_CHOICES__','[0,1,2,3]').replaceAll('__KEYBOARD__','{}').replaceAll('__VOICE_STATUS__','"音色已就绪"').replaceAll('__NETWORK_NOTICE__','""');
function fixture(host){
 const buttons=[],tools={hidden:false,querySelector(s){return s==='[data-host-sound]'?host:buttons[0]},appendChild(b){buttons.push(b)},closest(){return null}};
 const window={dispatchEvent(){},__weizhuoSpeechQueue:[{text:'三号玩家跟注25分',at:Date.now()}]};
 const document={body:{},hidden:false,documentElement:{classList:{add(){},contains(){return false}},style:{setProperty(){}}},getElementById(){return true},querySelector(s){return s==='[data-native-audition]'?buttons[1]:tools},createElement(){return {dataset:{},style:{},setAttribute(){}}}};
 return {context:vm.createContext({window,document,location:{hostname:'127.0.0.1'},Date:testDate,Event:class Event{constructor(type){this.type=type}}}),buttons,window};
}
function take(f){vm.runInContext(source,f.context);clock+=301;return vm.runInContext(source,f.context)}
let f=fixture(true),r=take(f);
assert.equal(r.voice,2);assert.equal(f.buttons[0].value,'2');assert.ok(f.buttons[0].innerHTML.includes('暖语 · Serena'));assert.equal(r.speech,'三号玩家跟注25分');
f.buttons[0].value='3';f.buttons[0].onchange();r=vm.runInContext(source,f.context);assert.equal(r.voice,3);assert.equal(r.speech,'');assert.equal(f.buttons.length,2);
f.buttons[1].onclick();r=vm.runInContext(source,f.context);assert.equal(r.audition,true);assert.ok(r.speech.includes("跟注"));assert.equal(vm.runInContext(source,f.context).speech,"");
f.window.__weizhuoSoundMuted=true;assert.equal(vm.runInContext(source,f.context).quiet,true);
f=fixture(false);vm.runInContext(source,f.context);assert.equal(f.buttons.length,0);
f.context.location.hostname='192.168.1.23';assert.equal(vm.runInContext(source,f.context),false);
console.log('原生音色桥接通过：男女映射、切换、单次取消息、静音、普通玩家及远程页面不展示。');

f=fixture(true);vm.runInContext(source,f.context);const choices=[];for(const id of [3,0,1,2]){f.buttons[0].value=String(id);f.buttons[0].onchange();choices.push(vm.runInContext(source,f.context).voice)}assert.deepEqual(choices,[3,0,1,2]);
f.window.__weizhuoSpeechQueue=[{text:'弃牌',at:Date.now()},{text:'结算',at:Date.now()}];assert.equal(take(f).speech,'弃牌');assert.equal(take(f).speech,'结算');
console.log('四音色及逐条队列检查通过。');

f=fixture(true);const blocked=source.replace("if(!window.__weizhuoVoiceTest&&true&&queue.length)","if(!window.__weizhuoVoiceTest&&false&&queue.length)").replace("window.__weizhuoVoiceTest===true&&true","window.__weizhuoVoiceTest===true&&false");assert.equal(vm.runInContext(blocked,f.context).speech,'');assert.equal(f.window.__weizhuoSpeechQueue.length,1);assert.equal(take(f).speech,'三号玩家跟注25分');
f.buttons[1].onclick();assert.equal(vm.runInContext(blocked,f.context).audition,false);assert.equal(f.window.__weizhuoVoiceTest,true);assert.equal(vm.runInContext(source,f.context).audition,true);

f=fixture(true);let rings=0;f.window.__weizhuoBeforeSpeech=()=>rings++;
assert.equal(vm.runInContext(blocked,f.context).speech,'');assert.equal(rings,0,'busy native player does not ring or dequeue');
assert.equal(vm.runInContext(source,f.context).speech,'');assert.equal(rings,1);clock+=100;
assert.equal(vm.runInContext(source,f.context).speech,'');assert.equal(rings,1,'ring is issued only once');clock+=201;
assert.equal(vm.runInContext(source,f.context).speech,'三号玩家跟注25分');
f.window.__weizhuoSpeechQueue=[{text:'等上一句结束',at:clock-31000}];assert.equal(take(f).speech,'等上一句结束','normal waiting longer than 30sec is retained');

// A changed network opens a clear service-return reminder once, never every poll.
f=fixture(true);const back={hidden:true,style:{},setAttribute(){}},toggle={setAttribute(){}};
f.context.document.getElementById=()=>({shadowRoot:{getElementById:id=>id==='back'?back:toggle}});
const changed=source.replace('const networkNotice=""','const networkNotice="网络已变化：重启服务并重新扫码加入"');
vm.runInContext(changed,f.context);assert.equal(back.hidden,false);assert.ok(back.textContent.includes('重新扫码'));
back.hidden=true;vm.runInContext(changed,f.context);assert.equal(back.hidden,true,'same warning does not reopen on every poll');
const restarted=changed.replace('网络已变化：重启服务并重新扫码加入','服务已重启：重新分享二维码，玩家重新扫码加入');
vm.runInContext(restarted,f.context);assert.equal(back.hidden,false);assert.ok(back.textContent.includes('服务已重启'));

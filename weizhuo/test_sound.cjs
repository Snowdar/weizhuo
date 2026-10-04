const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const context=vm.createContext({});vm.runInContext(fs.readFileSync('static/app.js','utf8').split("import {casualRoom")[0].replace(/^export /gm,''),context);
const events=(a,b)=>JSON.parse(JSON.stringify(context.roomSoundEvents(a,b)));
const s={room:'A',version:1,isHost:true,me:'a',game:'mahjong',players:[{id:'a',name:'甲'},{id:'b',name:'乙'}],transactions:[]};
const r={seq:1,time:'12:00',kind:'给分',changes:[{id:'a',name:'甲',delta:-3},{id:'b',name:'乙',delta:3}]};
const next={...s,version:2,transactions:[r]};
assert.equal(events(null,next).length,0,'refresh/entry silent');
assert.equal(events(s,{...next,isHost:false}).length,0,'guest never speaks');
assert.equal(events(s,next)[0].text,'甲给了乙3分');
assert.equal(events(next,next).length,0,'repeat poll silent');
assert.equal(events(next,{...s,version:3}).length,0,'undo silent');
assert.equal(events(next,{...s,version:1}).length,0,'old state silent');
assert.equal(events(s,{...next,room:'B'}).length,0,'room entry silent');
assert.equal(events(s,{...next,transactions:[{...r,kind:'索取确认'}]})[0].text,'乙收了甲的3分');
assert.equal(events(s,{...s,version:2,paymentRequests:[{id:'x',payer:'a',requester:'b',status:'pending',amount:1}]}).length,1);
assert.equal(events(s,{...s,version:2,paymentRequests:[{id:'x',payer:'b',requester:'a',status:'pending',amount:1}]}).length,1,'host outgoing request is narrated');
console.log('声音事件检查通过：房主限定、首次静默、重复/撤回去重、成交方向、个人请求。');
const memory=new Map(),window={__weizhuoNativeSpeech:true,__weizhuoSpeechQueue:[]};
const playback=vm.createContext({Date,Math,Set,JSON,window,document:{hidden:false,addEventListener(){}},storage:{getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v)}});
vm.runInContext(fs.readFileSync('static/app.js','utf8').split('import {casualRoom')[0].replace(/^export /gm,''),playback);
const make=()=>vm.runInContext("new RoomSound(storage,'test')",playback);
const first=make(),second=make();first.unlocked=second.unlocked=true;
first.consume(s);second.consume(s);first.consume(next);second.consume(next);
assert.equal(window.__weizhuoSpeechQueue.length,1,'two host tabs elect one speaker');
first.consume(next);assert.equal(window.__weizhuoSpeechQueue.length,1,'repeated poll does not requeue');
first.consume({...s,version:3});first.consume({...next,version:4});assert.equal(window.__weizhuoSpeechQueue.length,1,'undo then identical replay is suppressed');
first.toggle();assert.equal(window.__weizhuoSpeechQueue.length,0,'switching to effects clears queued narration');
first.consume({...next,version:5,transactions:[r,{...r,seq:2,time:'12:01'}]});assert.equal(window.__weizhuoSpeechQueue.length,0,'effects mode never speaks');
const guest=make();guest.unlocked=true;guest.consume({...s,isHost:false});guest.consume({...next,isHost:false});assert.equal(window.__weizhuoSpeechQueue.length,0,'guest has no playback');
console.log('播放检查通过：同设备多标签选主、轮询/撤回去重、模式切换清队列、普通玩家静音。');

const poker={...s,game:'holdem',hand:1,phase:'playing',turn:'a',bets:[],log:[{time:'12:00',text:'开始'}],players:[{id:'a',name:'甲',active:true,seen:false},{id:'b',name:'乙',active:true,seen:false}]};
const bet={seq:1,playerId:'a',playerName:'甲',amount:20,kind:'跟注',time:'12:01'};
assert.ok(events(poker,{...poker,version:2,bets:[bet]}).some(e=>e.text==='甲跟注20分'));
assert.ok(events(poker,{...poker,game:'zhajinhua',version:2,bets:[{...bet,cardState:'暗'}]}).some(e=>e.text==='甲闷注20分'));
assert.ok(events(poker,{...poker,version:2,players:[{...poker.players[0],seen:true},poker.players[1]]}).some(e=>e.text==='甲看牌'));
const folded={...poker,version:2,players:[{...poker.players[0],active:false},poker.players[1]],log:[{time:'12:01',text:'甲 弃牌'},...poker.log]};
assert.ok(events(poker,folded).some(e=>e.text==='甲弃牌'));
assert.equal(events(poker,{...folded,log:[{time:'12:01',text:'甲 比牌出局'},...poker.log]}).filter(e=>e.text==='甲弃牌').length,0,'comparison loss is not a fold');
assert.ok(events(poker,{...poker,version:2,log:[{time:'12:01',text:'甲 过牌'},...poker.log]}).some(e=>e.text==='甲过牌'));
assert.equal(events(poker,{...poker,version:2,hand:2,bets:[bet]}).filter(e=>e.kind==='action').length,0,'new hand has no old action narration');
assert.equal(events(folded,{...folded,version:3}).filter(e=>e.kind==='action').length,0,'repeat public action silent');
console.log('操作播报检查通过：跟注金额、闷注、看牌、弃牌、过牌、比牌出局区分、跨局及轮询静默。');

const numbered={...poker,players:[{...poker.players[0],name:'Snow',playerNumber:7},{...poker.players[1],name:'小乙',playerNumber:3}]};
const numberedBet={...bet,playerName:'Snow'};
const speechEvents=events(numbered,{...numbered,version:2,bets:[numberedBet]});
assert.equal(speechEvents.find(e=>e.kind==='action').speech,'7号玩家跟注20分');
assert.ok(speechEvents.every(e=>!e.speech.includes('Snow')),'all voices use player number without nickname');
assert.ok(speechEvents.some(e=>e.text.includes('Snow')),'visual records keep names');
assert.equal(context.spokenPlayer(numbered,'b'),'3号玩家');
assert.equal(context.spokenPlayer({...numbered,players:[...numbered.players].reverse()},'a'),'7号玩家','number follows the player, not current table position');
console.log('编号播报通过：英文昵称使用稳定编号，所有音色只读稳定编号，视觉记录保留昵称。');

const structured={...poker,handActions:[]};
for(const action of ['下注','跟注','加注','闷注','全下'])for(let i=0;i<20;i++){
 const row={playerId:'a',playerName:'甲',action,amount:20,time:'12:'+i};
 const e=events(structured,{...structured,version:2,handActions:[row]}).find(e=>e.kind==='action');
 assert.equal(e.speech,`1号玩家${action}20分`,'amount actions retain their precise UI verb for every event variant');
}
const actionRows=[{hand:1,playerId:'a',playerName:'甲',action:'弃牌',time:'12:02'}];
const settled={...structured,version:3,phase:'finished',turn:null,handActions:actionRows,result:{awards:[{playerId:'b',name:'乙',amount:40}]}};
const sequence=events(structured,settled);
assert.ok(sequence[0].text.includes('弃牌'));assert.ok(sequence.at(-1).text.includes('结算'),'fold then settlement keep order');
assert.equal(events(settled,{...settled,version:4}).length,0);
const begun={...structured,version:2,hand:2,phase:'dealing',dealPending:'hole'};
assert.ok(events({...structured,phase:'lobby'},begun).some(e=>e.id==='start:2'));
assert.ok(events(begun,{...begun,version:3,phase:'playing',dealPending:null,turn:'a'}).some(e=>e.text==='底牌已发好'));
const longActions=Array.from({length:5},(_,i)=>({...actionRows[0],action:'加注',amount:i+1,time:'12:0'+i}));
window.__weizhuoSpeechQueue=[];memory.clear();const full=make();full.unlocked=true;full.consume(structured);full.consume({...structured,version:2,handActions:longActions});
assert.equal(window.__weizhuoSpeechQueue.length,5,'never truncate to the last three actions');
console.log('完整播报回归通过：弃牌随后结算、开局、发牌完成、连续五条不截断。');

assert.equal(events(settled,{...structured,version:4,log:[{time:'12:03',text:'房主撤回了上一次动作：摊牌结算'},...structured.log]}).length,0,'undoing settlement does not replay a turn or old actions');

{
 const before={room:'r',isHost:true,version:1,game:'holdem',hand:1,phase:'dealing',dealPending:'flop',players:[],log:[]};
 const after={...before,version:3,dealPending:'turn',log:[{time:'12:00:02',text:'翻牌已发好'}]};
 assert.ok(events(before,after).some(e=>e.text==='翻牌已发好'));
}

const scoredNumbered={...s,players:numbered.players};
for(const kind of ['给分','索取确认']){
 const row={...r,kind,changes:[{id:'a',name:'Snow',delta:-60},{id:'b',name:'小乙',delta:60}]};
 const e=events(scoredNumbered,{...scoredNumbered,version:2,transactions:[row]})[0];
 assert.ok(e.speech.includes('7号玩家')&&e.speech.includes('3号玩家')&&e.speech.includes('60分'));
 assert.ok(!e.speech.includes('Snow')&&!e.speech.includes('小乙'));
}
const numberedResult=events({...numbered,handActions:[]},{...numbered,version:2,phase:'finished',handActions:[],turn:null,result:{awards:[{playerId:'b',name:'小乙',amount:60}]}});
assert.equal(numberedResult.at(-1).speech,'本局已结算，3号玩家获得60分');

{
 const spoken=[];
 for(let seq=0;seq<30;seq++){
  const row={...r,seq,changes:[{id:'a',name:'甲',delta:-250},{id:'b',name:'乙',delta:125},{id:'c',name:'丙',delta:125}]};
  const before={...s,players:[...s.players,{id:'c',name:'丙',playerNumber:3}]};
  spoken.push(events(before,{...before,version:2,transactions:[row]})[0].speech);
 }
 assert.ok(spoken.some(text=>text==='1号玩家向2号玩家、3号玩家各给出125分'),'natural alternate keeps actors, each amount and direction');
 assert.ok(spoken.some(text=>text==='1号玩家给了2号玩家、3号玩家各125分'));
}

// Audio feed is separate from personal action cards and includes other players.
const request={id:'outside',payer:'b',requester:'c',status:'pending',amount:20};
const hostState={...s,players:[...s.players,{id:'c',name:'丙',playerNumber:3}],soundRequests:[],paymentRequests:[]};
const pending={...hostState,version:2,soundRequests:[request]};
assert.equal(events(hostState,pending)[0].speech,'3号玩家向2号玩家请求收取20分，请确认');
assert.equal(events(pending,{...pending,version:3}).length,0,'pending poll never repeats');
const accepted={...pending,version:3,soundRequests:[{...request,status:'accepted'}],transactions:[{...r,kind:'索取确认',changes:[{id:'b',name:'乙',delta:-20},{id:'c',name:'丙',delta:20}]}]};
assert.equal(events(pending,accepted).length,1,'approval narrates the receipt once');
assert.deepEqual(events(hostState,accepted).map(e=>e.kind),['reminder','score'],'fast accept preserves request then receipt');
assert.equal(events(hostState,{...pending,isHost:false}).length,0,'only host broadcasts');

// Browser speech gets a real FIFO; subsequent polling does not chime over speech.
const utterances=[],tones=[],timers=[];
const browserWindow={speechSynthesis:{getVoices:()=>[{localService:true,lang:'zh-CN'}],speak:u=>utterances.push(u),cancel(){}}};
const browserContext=vm.createContext({Date,Math,Set,JSON,window:browserWindow,document:{hidden:false,addEventListener(){}},storage:{getItem:()=>null,setItem(){}},setTimeout:fn=>timers.push(fn),SpeechSynthesisUtterance:class {constructor(text){this.text=text}}});
vm.runInContext(fs.readFileSync('static/app.js','utf8').split('import {casualRoom')[0].replace(/^export /gm,''),browserContext);
const fifo=vm.runInContext("new RoomSound(storage,'fifo')",browserContext);fifo.tone=v=>tones.push(v);
fifo.speak('请求',false);fifo.speak('确认',true);fifo.speak('给分',true);
assert.equal(tones.length,1);assert.equal(utterances.length,0);
timers.shift()();assert.equal(utterances[0].text,'请求');assert.equal(tones.length,1,'no new ring while first line speaks');
utterances[0].onend();const pendingTimers=timers.length;utterances[0].onend();assert.equal(timers.length,pendingTimers,'duplicate completion cannot start two lines');timers.shift()();assert.equal(utterances[1].text,'确认');
utterances[1].onend();timers.shift()();assert.equal(utterances[2].text,'给分');
fifo.speak('旧待播');fifo.toggle();utterances[2].onend();assert.equal(timers.length,0,'canceled completion cannot resume old queue');
console.log('自由积分请求发送／成交、快速确认顺序和逐句铃声／语音 FIFO 通过。');

(async()=>{
 const source=fs.readFileSync('static/app.js','utf8');
 const prefix=source.split('import {casualRoom')[0].replace(/^export /gm,'');
 const helper=source.slice(source.indexOf('async function fetchWithTimeout('),source.indexOf('function setNetworkStatus('));
 const wav=new ArrayBuffer(20);let jsonReads=0,ok=true;
 const c=vm.createContext({AbortController,setTimeout,clearTimeout,Promise,fetch:async()=>({ok,status:ok?200:403,json:async()=>{jsonReads++;if(ok)throw Error('WAV must not be JSON');return {error:'拒绝'}},arrayBuffer:async()=>wav})});
 vm.runInContext(helper,c);
 const result=await c.fetchWithTimeout('/api/voice',{},1000,'arrayBuffer');assert.equal(await result.arrayBuffer(),wav);assert.equal(jsonReads,0);
 ok=false;const denied=await c.fetchWithTimeout('/api/voice',{},1000,'arrayBuffer');assert.equal((await denied.json()).error,'拒绝');assert.equal(jsonReads,1);
 const fetched=[],sources=[],delays=[],errors=[];
 const context=vm.createContext({Date,Math,Set,JSON,Promise,window:{speechSynthesis:{cancel(){}}},document:{hidden:false,addEventListener(){},querySelectorAll:()=>[]},storage:{getItem:()=>null,setItem(){}},base:'/',room:'ROOM',token:'HOST',toast:t=>errors.push(t),setTimeout:fn=>delays.push(fn),fetchWithTimeout:async(url,options,timeout,type)=>{assert.equal(type,'arrayBuffer');fetched.push(JSON.parse(options.body));return {ok:true,arrayBuffer:async()=>wav}}});
 vm.runInContext(prefix,context);const local=vm.runInContext("new RoomSound(storage,'local')",context);local.localVoice=3;local.tone=()=>{};
 local.context={destination:{},decodeAudioData:async()=>({}),createBufferSource:()=>{const s={connect(){},start(){s.started=true},stop(){s.stopped=true}};sources.push(s);return s}};
 local.speak('请求');local.speak('确认');local.speak('成交');assert.equal(delays.length,1);
 delays.shift()();await new Promise(setImmediate);assert.deepEqual(fetched.map(x=>x.text),['请求']);assert.equal(sources[0].started,true);
 sources[0].onended();sources[0].onended();assert.equal(delays.length,1);delays.shift()();await new Promise(setImmediate);
 assert.deepEqual(fetched.map(x=>x.text),['请求','确认']);assert.equal(fetched[0].voice,3);assert.equal(fetched[0].token,'HOST');
 local.clearNarration();sources[1].onended();assert.equal(sources[1].stopped,true);assert.equal(delays.length,0);assert.deepEqual(errors,[]);
 console.log('桌面 WAV 实际读取与离线 FIFO 通过：不解析为 JSON，播放完成后取下一条，静音取消，无系统补读。');
})().catch(error=>{console.error(error);process.exitCode=1});

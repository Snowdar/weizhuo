// All announcers share numbered-player text; names remain in visual records.
export function spokenPlayer(s,id){
 const i=s.players.findIndex(p=>p.id===id),p=s.players[i];
 const number=p?.playerNumber||(i>=0?i+1:null);
 return number?number+'号玩家':'玩家';
}
function spokenVariant(id,choices){let hash=0;for(const c of id)hash=(hash*31+c.charCodeAt(0))>>>0;return choices[hash%choices.length]}
// One room host speaks; snapshots establish a silent baseline, never a backlog.
export function roomSoundEvents(before,after){
 if(!before||before.room!==after.room||!after.isHost||after.version<=before.version)return [];
 const priorLogs=new Set((before.log||[]).map(r=>JSON.stringify(r)));
 if((after.log||[]).some(r=>r.text?.startsWith('房主撤回了上一次动作：')&&!priorLogs.has(JSON.stringify(r))))return [];
 const events=[],name=id=>after.players.find(p=>p.id===id)?.name||'玩家',say=(id,label)=>spokenPlayer(after,id,label);
 // Created and accepted between two polls must still announce request before receipt.
 const requests=new Set((before.soundRequests||before.paymentRequests||[]).map(r=>r.id));
 for(const r of after.soundRequests||after.paymentRequests||[])if(['pending','accepted'].includes(r.status)&&!requests.has(r.id))events.push({id:'request:'+r.id,kind:'reminder',text:`${name(r.requester)}向${name(r.payer)}请求收取${r.amount}分，请确认`,speech:`${say(r.requester)}向${say(r.payer)}请求收取${r.amount}分，请确认`});
 const old=before.transactions||[],rows=after.transactions||[];
 if(old.every((r,i)=>JSON.stringify(r)===JSON.stringify(rows[i])))for(const r of rows.slice(old.length)){
  const from=r.changes.filter(c=>c.delta<0),to=r.changes.filter(c=>c.delta>0);
  if(!from.length&&!to.length)continue;
  const text=r.kind==='索取确认'&&from.length&&to.length?`${to.map(c=>c.name).join('、')}收了${from.map(c=>c.name).join('、')}的${to[0].delta}分`:from.length&&to.length?`${from.map(c=>c.name).join('、')}给了${to.map(c=>c.name).join('、')}${to.length>1?'各':''}${to[0].delta}分`:`积分已更新，${r.changes.map(c=>c.name+(c.delta>0?'增加':'减少')+Math.abs(c.delta)+'分').join('，')}`;
  const voice=c=>say(c.id,c.name);let speech=r.kind==='索取确认'&&from.length&&to.length?`${to.map(voice).join('、')}收了${from.map(voice).join('、')}的${to[0].delta}分`:from.length&&to.length?`${from.map(voice).join('、')}给了${to.map(voice).join('、')}${to.length>1?'各':''}${to[0].delta}分`:`积分已更新，${r.changes.map(c=>voice(c)+(c.delta>0?'增加':'减少')+Math.abs(c.delta)+'分').join('，')}`;
  const eventId='score:'+JSON.stringify(r);
  if(from.length&&to.length){const alternate=r.kind==='索取确认'?`${to.map(voice).join('、')}从${from.map(voice).join('、')}收取${to[0].delta}分`:`${from.map(voice).join('、')}向${to.map(voice).join('、')}${to.length>1?'各':''}给出${to[0].delta}分`;speech=spokenVariant(eventId,[speech,alternate])}
  events.push({id:eventId,kind:'score',text,speech});
 }
 // Structured bets carry the exact paid amount; flags carry public card actions.
 if(after.game!=='mahjong'&&before.hand===after.hand){
  const previous=new Map(before.players.map(p=>[p.id,p]));
  const oldActions=before.handActions||[],actions=after.handActions||[];
  const structured=Array.isArray(before.handActions)&&Array.isArray(after.handActions);
  if(structured&&oldActions.every((r,i)=>JSON.stringify(r)===JSON.stringify(actions[i])))for(const [index,a] of actions.slice(oldActions.length).entries()){
   const id=`action:${after.hand}:row:${oldActions.length+index}:${JSON.stringify(a)}`;
   const amount=Number(a.amount)>0?`${a.amount}分`:'';
   const who=say(a.playerId,a.playerName);
   const text=`${a.playerName}${a.action}${amount}`;
   // Keep scoring action names identical to the UI in every voice and variant.
   const options=a.action==='弃牌'?[`${who}弃牌`,`${who}选择弃牌`]:a.action==='看牌'?[`${who}看牌`,`${who}已看牌`]:a.action==='过牌'?[`${who}过牌`,`${who}选择过牌`]:[`${who}${a.action}${amount}`];
   events.push({id,kind:'action',text,speech:spokenVariant(id,options)});
  }
  if(!structured){
  const oldBets=before.bets||[],bets=after.bets||[];
  if(oldBets.every((row,i)=>JSON.stringify(row)===JSON.stringify(bets[i])))for(const b of bets.slice(oldBets.length)){
   if(b.amount<=0||/底注|盲注|退还/.test(b.kind))continue;
   const verb=after.game==='zhajinhua'&&b.kind==='跟注'&&b.cardState==='暗'?'闷注':b.kind;
   events.push({id:`action:${after.hand}:bet:${JSON.stringify(b)}`,kind:'action',text:`${b.playerName}${verb}${b.amount}分`,speech:`${say(b.playerId,b.playerName)}${verb}${b.amount}分`});
  }
  const oldLog=(before.log||[]).map(x=>JSON.stringify(x)),logs=after.log||[];
  const stop=logs.findIndex(x=>oldLog.includes(JSON.stringify(x))),freshLogs=stop<0?(oldLog.length?[]:logs):logs.slice(0,stop);
  for(const p of after.players){const old=previous.get(p.id);if(!old)continue;
   if(!old.seen&&p.seen)events.push({id:`action:${after.hand}:seen:${p.id}`,kind:'action',text:`${p.name}看牌`,speech:`${say(p.id)}看牌`});
   if(old.active&&!p.active&&freshLogs.some(x=>x.text===`${p.name} 弃牌`||x.text===`房主为 ${p.name} 补记弃牌`))events.push({id:`action:${after.hand}:fold:${p.id}`,kind:'action',text:`${p.name}弃牌`,speech:`${say(p.id)}弃牌`});
  }
  for(const row of freshLogs.reverse())if(after.players.some(p=>row.text===`${p.name} 过牌`))events.push({id:`action:${after.hand}:check:${JSON.stringify(row)}`,kind:'action',text:row.text.replace(' 过牌','过牌'),speech:say(after.players.find(p=>row.text===`${p.name} 过牌`).id)+'过牌'});
 }
 }
 let text='',speech='';
 if(after.game!=='mahjong'){
  if(after.hand>before.hand&&['playing','dealing'].includes(after.phase))events.push({id:`start:${after.hand}`,kind:'reminder',text:'本局开始',speech:spokenVariant(String(after.hand),['新的一局开始了','本局开始，祝大家玩得开心'])});
  const completed=(after.log||[]).filter(r=>!priorLogs.has(JSON.stringify(r))&&/^(底牌|翻牌|转牌|河牌)已发好$/.test(r.text||'')).reverse();
  if(completed.length&&after.phase!=='lobby')for(const row of completed){
   const stage=row.text.replace('已发好','');
   events.push({id:`deal:${after.hand}:${JSON.stringify(row)}`,kind:'reminder',text:row.text,speech:spokenVariant(String(after.version),[stage+'已发好',stage+'发牌完成'])});
  }else if(before.phase==='dealing'&&after.phase!=='dealing'&&before.hand===after.hand&&after.phase!=='lobby'){
   const stage={hole:'底牌',flop:'翻牌',turn:'转牌',river:'河牌'}[before.dealPending]||'本轮牌';
   events.push({id:`deal:${after.hand}:${before.dealPending}`,kind:'reminder',text:stage+'已发好',speech:stage+'已发好'});
  }
  if(after.phase==='finished'&&before.phase!=='finished'){const r=after.result;text=r?.awards?.length?'本局已结算，'+r.awards.map(a=>a.name+'获得'+a.amount+'分').join('，'):r?.winner?'本局已结算，'+r.winner+'获得'+r.amount+'分':'本局已结算'}
  else if(after.phase==='dealing'&&(before.phase!=='dealing'||before.dealPending!==after.dealPending))text=({hole:'请助手发底牌',flop:'请助手烧一张牌，发三张翻牌',turn:'请助手烧一张牌，发一张转牌',river:'请助手烧一张牌，发河牌'}[after.dealPending]||'等待发牌协助');
  else if(after.phase==='showdown'&&before.phase!=='showdown')text='请选择赢家并结算';
  else if(after.phase==='playing'&&after.turn&&(after.turn!==before.turn||before.phase!=='playing'))text=`轮到${name(after.turn)}行动`;
  else if(['lobby','finished'].includes(after.phase)&&after.readyCount===after.players.length&&before.readyCount!==after.readyCount&&after.players.length>1)text='所有玩家已准备，可以开始';
 }
 if(text){speech=text;if(after.phase==='playing'&&after.turn)speech=spokenVariant('turn:'+after.version,[`轮到${say(after.turn)}行动`,`现在请${say(after.turn)}行动`]);else if(after.phase==='finished'){const r=after.result;speech=r?.awards?.length?'本局已结算，'+r.awards.map(a=>say(a.playerId,a.name)+'获得'+a.amount+'分').join('，'):r?.winner?'本局已结算，'+say(r.winnerId,r.winner)+'获得'+r.amount+'分':'本局已结算'}events.push({id:'stage:'+after.version,kind:'reminder',text,speech})}
 return events;
}
export class RoomSound {
 constructor(storage,scope){this.storage=storage;this.scope=scope;this.mode=storage.getItem('weizhuo-sound-v1'+scope)||'voice';this.previous=null;this.seen=new Set();this.unlocked=false;this.context=null;this.browserQueue=[];this.browserCurrent=false;this.browserTicket=0;this.localVoice=Number(storage.getItem('weizhuo-announcer'+scope)||0);this.audioSource=null;this.owner=String(Math.random());this.lastAt=0;
  document.addEventListener('pointerdown',()=>this.unlock(),{passive:true});
  window.__weizhuoBeforeSpeech=score=>this.tone(score);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)this.clearNarration()});
 }
 unlock(){this.unlocked=true;try{if(!this.context)this.context=new(window.AudioContext||window.webkitAudioContext)();this.context.resume().catch(()=>{})}catch{}}
 toggle(){this.mode={voice:'effects',effects:'off',off:'voice'}[this.mode];this.storage.setItem('weizhuo-sound-v1'+this.scope,this.mode);window.__weizhuoSoundMuted=this.mode!=='voice';if(this.mode!=='voice')this.clearNarration();return this.label()}
 label(){return {voice:'声音：房主播报',effects:'声音：仅提示音',off:'声音：关闭'}[this.mode]}
 consume(state){window.__weizhuoSoundMuted=this.mode!=='voice'||!state.isHost;const events=roomSoundEvents(this.previous,state);this.previous=state;
  if(!state.isHost){this.clearNarration();return}
  if(this.mode==='off'||!this.unlocked||document.hidden)return;
  // Same host in multiple tabs on this device: a short renewable speaker lease.
  const key='weizhuo-speaker-v1'+this.scope+state.room;
  try{const lease=JSON.parse(this.storage.getItem(key)||'null');if(lease&&lease.owner!==this.owner&&Date.now()-lease.at<2500)return;this.storage.setItem(key,JSON.stringify({owner:this.owner,at:Date.now()}))}catch{}
  const fresh=events.filter(e=>!this.seen.has(state.room+e.id));for(const e of fresh)this.seen.add(state.room+e.id);
  if(this.seen.size>500)this.seen=new Set([...this.seen].slice(-250));
  if(!fresh.length)return;
  if(this.mode==='voice')fresh.forEach(e=>this.speak(e.speech||e.text,e.kind==='score'));
  else this.tone(fresh.some(e=>e.kind==='score'));
 }
 tone(score){const c=this.context;if(!c||c.state!=='running')return;for(const [i,f]of(score?[660,880]:[880,660]).entries()){const o=c.createOscillator(),g=c.createGain(),t=c.currentTime+i*.11;o.type='sine';o.frequency.value=f;g.gain.setValueAtTime(0,t);g.gain.linearRampToValueAtTime(.20,t+.01);g.gain.exponentialRampToValueAtTime(.001,t+.13);o.connect(g);g.connect(c.destination);o.start(t);o.stop(t+.14)}}
 clearNarration(){this.browserTicket++;this.browserQueue=[];this.browserCurrent=false;if(this.audioSource){try{this.audioSource.stop()}catch{}this.audioSource=null}window.speechSynthesis?.cancel();window.__weizhuoSpeechQueue=[]}
 speak(text,score=false){if(window.__weizhuoNativeSpeech){const q=window.__weizhuoSpeechQueue||(window.__weizhuoSpeechQueue=[]);if(q.length<128)q.push({text,score,at:Date.now()});return}
  if(!this.localVoice&&(!window.speechSynthesis||typeof SpeechSynthesisUtterance==='undefined'))return;
  if(this.browserQueue.length<128)this.browserQueue.push({text,score,at:Date.now()});this.pumpBrowser();
 }
 localStatus(status){this.playbackStatus=status;document.querySelectorAll('[data-desktop-audition]').forEach(button=>button.textContent='试听播报 · '+status)}
 async playLocal(item){
  this.browserCurrent=true;this.localStatus('正在准备');const ticket=this.browserTicket;try{this.tone(item.score)}catch{};
  try{
   await new Promise(resolve=>setTimeout(resolve,300));
   if(ticket!==this.browserTicket||document.hidden||this.mode!=='voice')return;
   const response=await fetchWithTimeout(base+'api/voice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room,token,text:item.text,voice:this.localVoice})},30000,'arrayBuffer');
   if(!response.ok){const error=await response.json();throw Error(error.error||'播报失败')}
   const buffer=await this.context.decodeAudioData(await response.arrayBuffer());
   if(ticket!==this.browserTicket||document.hidden||this.mode!=='voice')return;
   const source=this.context.createBufferSource();source.buffer=buffer;source.connect(this.context.destination);this.audioSource=source;
   let finished=false;source.onended=()=>{if(finished||ticket!==this.browserTicket)return;finished=true;this.audioSource=null;this.browserCurrent=false;this.localStatus('播放完成');this.pumpBrowser()};source.start();this.localStatus('正在播放');
  }catch(error){if(ticket===this.browserTicket){this.browserCurrent=false;this.localStatus('播放失败');toast(error.message);this.pumpBrowser()}}
 }
 pumpBrowser(){
  if(this.browserCurrent||document.hidden||this.mode!=='voice')return;
  while(this.browserQueue.length&&Date.now()-this.browserQueue[0].at>120000)this.browserQueue.shift();
  const item=this.browserQueue.shift();if(!item)return;
  if(this.localVoice){this.playLocal(item);return}
  // Browser engines differ in queue behavior; own one active utterance explicitly.
  const synth=window.speechSynthesis,voice=synth.getVoices().find(v=>v.localService&&/^zh/i.test(v.lang));if(!voice)return;
  this.browserCurrent=true;const ticket=this.browserTicket;try{this.tone(item.score)}catch{};
  setTimeout(()=>{if(ticket!==this.browserTicket||document.hidden||this.mode!=='voice')return;
   const u=new SpeechSynthesisUtterance(item.text);u.lang='zh-CN';u.voice=voice;u.rate=1;
   let finished=false;u.onend=u.onerror=()=>{if(finished||ticket!==this.browserTicket)return;finished=true;this.browserCurrent=false;this.pumpBrowser()};try{synth.speak(u)}catch{u.onerror()};
  },300);
 }

}

import {casualRoom,bindCasual,captureCasualDraft,newFreeRecords,animateFreeScores} from './tabletop.js';
import {holdemConfig,getHoldemConfig,holdemRoom,playerHandHistory,bindHoldem,holdemViewportSize,nativeKeyboardViewport,tableKeyboardLayout,newHoldemBets,animateHoldemBets,newHoldemAwards,animateHoldemAwards} from './holdem.js';
import {gameCatalog,bindGameCatalog,gameExplanation,hallHeading} from './games.js';
import {mahjongConfig} from './mahjong.js';
import {bindRoomTools,roomHeader,esc,configFields,defaults,activity,poolLedger,gameActions,playerInfo,rules,resultView} from './zhajinhua.js';
function nextScoreValue(value,direction,min,max,step=1){const lower=min===''?-Infinity:Number(min),upper=max===''?Infinity:Number(max),current=value===''?(Number.isFinite(lower)?lower:0):Number(value);return Math.min(upper,Math.max(lower,(Number.isFinite(current)?current:0)+direction*step))}
function scoreInputHasShortcuts(input){return ['holdemRaiseTo','casualAmount','tableGiveAmount','allAmount','poolDepositAmount','proxyAmount'].includes(input.id)}
function enhanceScoreInputs(root=document){root.querySelectorAll('input[type="number"]').forEach(input=>{input.setAttribute('inputmode','numeric');input.setAttribute('enterkeyhint','done');if(!scoreInputHasShortcuts(input)||input.closest('.score-stepper')||input.readOnly)return;const box=document.createElement('div');box.className='score-stepper';const label=input.getAttribute('aria-label')||document.querySelector(`label[for="${input.id}"]`)?.textContent||'积分';input.before(box);const buttons=[[-1,'−1','减少'],[1,'+1','增加']].map(([direction,text,verb])=>{const b=document.createElement('button');b.type='button';b.textContent=text;b.className='score-step-button';b.setAttribute('aria-label',verb+label);b.onclick=()=>{if(input.disabled)return;input.value=String(nextScoreValue(input.value,direction,input.min,input.max,1));input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));sync()};return b});box.append(buttons[0],input,buttons[1]);const jumps=[[-1,'−5','减少5分'],[1,'+5','增加5分']].map(([direction,text,verb])=>{const b=document.createElement('button');b.type='button';b.textContent=text;b.className='score-step-button';b.setAttribute('aria-label',verb);b.onclick=()=>{if(input.disabled)return;input.value=String(nextScoreValue(input.value,direction,input.min,input.max,5));input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));sync()};return b});box.prepend(jumps[0]);box.append(jumps[1]);alignScoreControls(box);function sync(){buttons[0].disabled=input.disabled||(input.min!==''&&Number(input.value)<=Number(input.min));buttons[1].disabled=input.disabled||(input.max!==''&&Number(input.value)>=Number(input.max));jumps[0].disabled=buttons[0].disabled;jumps[1].disabled=buttons[1].disabled}input.addEventListener('input',sync);input.addEventListener('change',sync);sync()})}
const scoreInputObserver=new MutationObserver(records=>{for(const r of records)for(const node of r.addedNodes)if(node.nodeType===1&&node.querySelector?.('input[type="number"]'))enhanceScoreInputs(node)});
// One amount row everywhere; inline layout wins over old per-game compact grids.
// The original input and button handlers remain intact.
function alignScoreControls(box){
 const input=box.querySelector('input');
 for(const [key,value] of Object.entries({display:'grid','grid-template-columns':'clamp(30px,12%,44px) clamp(30px,12%,44px) minmax(0,1fr) clamp(30px,12%,44px) clamp(30px,12%,44px)',gap:'6px',width:'100%','min-width':'0','align-items':'stretch'}))box.style.setProperty(key,value,'important');
 for(const child of box.children)for(const [key,value] of Object.entries({'grid-column':'auto','grid-row':'1',width:'100%','min-width':'0',height:'44px','min-height':'44px','max-height':'44px',margin:'0',padding:child===input?'4px 2px':'0','box-sizing':'border-box','font-size':child===input?'20px':'17px'}))child.style.setProperty(key,value,'important');
}
scoreInputObserver.observe(document.body,{childList:true,subtree:true});
const $=s=>document.querySelector(s),base=location.pathname.startsWith('/test')?'/test/':'/',qs=new URLSearchParams(location.search),device=base==='/test/'?qs.get('device'):null;
// Set the published repository URL in index.html; never advertise a placeholder repository.
const projectUrl=$('meta[name="weizhuo-project-url"]')?.content.trim(),projectLink=$('#projectSourceLink');
if(projectUrl&&projectLink){try{const url=new URL(projectUrl);if(url.protocol==='https:'&&!url.username&&!url.password){projectLink.href=url.href;projectLink.textContent='GitHub: '+url.href;projectLink.hidden=false}}catch{}}
const storage={getItem(k){try{return (device?sessionStorage:localStorage).getItem(k)}catch{return null}},setItem(k,v){try{(device?sessionStorage:localStorage).setItem(k,v)}catch{}}},key='weizhuo-v2'+base+(device||'');
const roomSound=new RoomSound(storage,base+(device||''));
let identities;try{identities=JSON.parse(storage.getItem(key)||'{}')}catch{identities={}}
const deviceStorageKey='weizhuo-device-v1'+base+(device||'');
const nicknameStorageKey='weizhuo-nickname-v1'+base+(device||'');let defaultNickname=storage.getItem(nicknameStorageKey)||'';
let deviceKey=storage.getItem(deviceStorageKey)||(device?Array.from(crypto.getRandomValues(new Uint8Array(32)),x=>x.toString(16).padStart(2,'0')).join(''):'');
async function recoverDeviceRooms(){
 const before=JSON.stringify(identities);
 const out=await request('api/device',{deviceKey,bindings:Object.entries(identities).map(([room,x])=>({room,token:x.token}))});
 deviceKey=out.deviceKey;storage.setItem(deviceStorageKey,deviceKey);if(typeof out.nickname==='string'){defaultNickname=out.nickname;storage.setItem(nicknameStorageKey,defaultNickname)}
 for(const x of out.rooms)remember(x.room,x.token,x.name,x.isHost,{game:x.game,gameName:x.gameName,phase:x.phase,hand:x.hand,playerName:x.playerName});
 return before!==JSON.stringify(identities);
}
let activityFollowing=true, stateGeneration=0, holdemActingKey='', holdemBetSnapshot=null,casualSnapshot=null;
let room=qs.get('room')?.toUpperCase()||null,token='',state=null,bootstrap,last='',busy=false,view='home',removed=false,createdRoom=null,selectedGame='zhajinhua';
const hash=new URLSearchParams(location.hash.slice(1));let incoming=hash.get('host')||hash.get('player'),incomingDevice=hash.get('device');
let keyboardRenderDeferred=false;
let tableViewportFrame=0,keyboardBaseline=window.innerHeight,keyboardWidth=window.innerWidth;
let keyboardDock=null;
const editableSelector='input:not([type=checkbox]):not([type=radio]),textarea,[contenteditable=true]';
function keyboardSessionActive(){return !!(document.activeElement?.matches(editableSelector)||window.__weizhuoKeyboard?.visible)}
function flushKeyboardRender(force=false){
 if(!keyboardRenderDeferred||(!force&&keyboardSessionActive()))return;
 keyboardRenderDeferred=false;renderRoom();scheduleTableFit();
}
function restoreKeyboardEditor(){
 if(!keyboardDock)return;
 const {pane,styles}=keyboardDock;keyboardDock=null;
 for(const [key,[value,priority]] of Object.entries(styles)){if(value)pane.style.setProperty(key,value,priority);else pane.style.removeProperty(key)}
 pane.removeAttribute('data-keyboard-docked');
}
// Preserve the original form, stacking context, width and responder. Only dock its
// lower edge; never show a popover, reparent a node or call focus during keyboard presentation.
function fitTableViewport(){
 if(!document.documentElement.classList.contains('table-viewport'))return;
 const root=document.documentElement,windowSize={width:window.innerWidth,height:window.innerHeight},editable=document.activeElement?.matches(editableSelector),native=window.__weizhuoKeyboard,visual=nativeKeyboardViewport(windowSize,window.visualViewport,native,editable||!!keyboardDock),size=holdemViewportSize(windowSize,visual);
 if(windowSize.width!==keyboardWidth){keyboardWidth=windowSize.width;keyboardBaseline=windowSize.height}else if(!editable&&!native?.visible)keyboardBaseline=Math.max(keyboardBaseline,windowSize.height);
 const keyboard=tableKeyboardLayout(windowSize,visual,editable,keyboardBaseline);
 const editing=!!native?.visible||keyboard.active;
 root.style.setProperty('--keyboard-bottom',keyboard.bottom+'px');
 if(!editing){restoreKeyboardEditor();if(!editable)for(const [key,value] of Object.entries(size))root.style.setProperty('--table-viewport-'+key,value+'px');return}
 const pane=document.activeElement?.closest('.seat-action-focus,.casual-popover')||keyboardDock?.pane;
 if(!pane)return;
 if(keyboardDock?.pane!==pane){restoreKeyboardEditor();const styles={};for(const key of ['top','bottom','max-height','transform'])styles[key]=[pane.style.getPropertyValue(key),pane.style.getPropertyPriority(key)];keyboardDock={pane,styles};pane.setAttribute('data-keyboard-docked','')}
 const parent=pane.offsetParent?.getBoundingClientRect()||{bottom:windowSize.height,top:0};
 const top=size.top+size.height,safe=parseFloat(getComputedStyle(root).getPropertyValue('--content-safe-top'))||0;
 pane.style.setProperty('top','auto','important');
 // Cancel vertical centering: bottom must describe the visible lower edge.
 pane.style.setProperty('transform',pane.classList.contains('seat-action-focus')?'translateX(-50%)':'none','important');
 pane.style.setProperty('bottom',Math.max(8,parent.bottom-top+8)+'px','important');
 pane.style.setProperty('max-height',Math.max(80,top-Math.max(safe+8,parent.top)-16)+'px','important');
}
function lockTableViewport(locked){if(!locked)restoreKeyboardEditor();document.documentElement.classList.toggle('table-viewport',locked);if(locked){fitTableViewport();if(window.scrollX||window.scrollY)window.scrollTo(0,0)}else {document.documentElement.classList.remove('input-keyboard');for(const key of ['width','height','top','left'])document.documentElement.style.removeProperty('--table-viewport-'+key)}}
function scheduleTableFit(){cancelAnimationFrame(tableViewportFrame);tableViewportFrame=requestAnimationFrame(fitTableViewport)}
document.addEventListener('focusin',scheduleTableFit);
document.addEventListener('focusout',()=>{scheduleTableFit();setTimeout(()=>flushKeyboardRender(),0)});
window.addEventListener('resize',scheduleTableFit);window.addEventListener('orientationchange',scheduleTableFit);
window.addEventListener('weizhuokeyboard',()=>{scheduleTableFit();if(!window.__weizhuoKeyboard?.visible)setTimeout(()=>flushKeyboardRender(true),0)});
window.visualViewport?.addEventListener('resize',scheduleTableFit);window.visualViewport?.addEventListener('scroll',scheduleTableFit);
document.addEventListener('contextmenu',e=>{if(!e.target.closest('dialog .sentence-records .simple-score-row'))e.preventDefault()});
const tableScrollRegions='.holdem-steps,.simple-player-list,.simple-free-view .poker-surface,.simple-record-window,.sentence-records';
const tableTouchAllowed='dialog,.table-dock,.free-trade-feed,.seat-history-popover,.seat-action-focus,.activity-stream,.seat-bet-details,.profile-options,.seat-name,.room-meta-line,.room-top h1,'+tableScrollRegions;
let tableScrollActive=false,tableScrollTouching=false,tableScrollDeferred=false,tableScrollTimer=0;
function finishTableScroll(){clearTimeout(tableScrollTimer);tableScrollTimer=setTimeout(()=>{if(tableScrollTouching)return;tableScrollActive=false;if(tableScrollDeferred){tableScrollDeferred=false;if(state?.game==='mahjong'&&document.querySelector('.casual-layout'))renderCasualRoom()}},180)}
document.addEventListener('touchstart',e=>{if(!e.target.closest(tableScrollRegions))return;clearTimeout(tableScrollTimer);tableScrollTouching=true;tableScrollActive=true},{passive:true});
document.addEventListener('touchend',e=>{if(e.touches.length)return;tableScrollTouching=false;if(tableScrollActive)finishTableScroll()},{passive:true});
document.addEventListener('touchcancel',()=>{tableScrollTouching=false;if(tableScrollActive)finishTableScroll()},{passive:true});
document.addEventListener('scroll',e=>{if(tableScrollActive&&e.target.closest?.(tableScrollRegions)&&!tableScrollTouching)finishTableScroll()},{capture:true,passive:true});
document.addEventListener('touchmove',e=>{if(document.documentElement.classList.contains('table-viewport')&&e.touches.length===1&&!e.target.closest(tableTouchAllowed))e.preventDefault()},{passive:false});
function toast(msg){$('#toast').textContent=String(msg).replaceAll('索取','索要');$('#toast').style.display='block';clearTimeout(window.tt);window.tt=setTimeout(()=>$('#toast').style.display='none',4500)}
function remember(code,value,name,isHost,details={}){const before=JSON.stringify(identities[code]);identities[code]={...identities[code],token:value,name:name||identities[code]?.name||'游戏房间',...(isHost===undefined?{}:{isHost}),...details};if(JSON.stringify(identities[code])!==before)storage.setItem(key,JSON.stringify(identities))}
function forget(){delete identities[room];storage.setItem(key,JSON.stringify(identities));token=''}
function roomUrl(code){const p=new URLSearchParams();if(code)p.set('room',code);if(device)p.set('device',device);return base+(p.size?'?'+p.toString():'')}
function navigate(code){lockTableViewport(false);holdemActingKey='';holdemBetSnapshot=null;document.querySelector('.table-chip-effects')?.remove();document.body.classList.remove('holdem-table','table-immersive','editing-seats','casual-table','theme-free','theme-three-card');syncCompareDialog(null);room=code;token=identities[code]?.token||'';state=null;last='';removed=false;history.pushState(null,'',roomUrl(code));if(code)poll();else{view='home';renderHome();refreshKnownRooms()}}
// Bound connection and response-body waiting; never automatically resend mutations.
async function fetchWithTimeout(url, options={}, timeoutMs=8000, responseType='json') {
 const controller=new AbortController();let timer;
 const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Error('连接超时：请检查网络和服务电脑是否休眠'))},timeoutMs)});
 try{return await Promise.race([deadline,(async()=>{const response=await fetch(url,{...options,signal:controller.signal});const body=await (responseType==='arrayBuffer'&&response.ok?response.arrayBuffer():response.json());return {ok:response.ok,status:response.status,json:async()=>body,arrayBuffer:async()=>body}})()])}
 catch(error){if(error.name==='TypeError')throw Error('无法连接服务：请检查网络和服务电脑是否休眠');throw error}
 finally{clearTimeout(timer)}
}
function setNetworkStatus(message,kind='error'){let banner=$('#networkNotice');if(!banner){banner=document.createElement('div');banner.id='networkNotice';banner.setAttribute('role','status');banner.setAttribute('aria-live','polite');document.body.append(banner)}banner.textContent=String(message).replaceAll('索取','索要');banner.dataset.kind=kind;banner.hidden=!message}
async function request(path,data){const r=await fetchWithTimeout(base+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,...(deviceKey?{deviceKey}:{})})});const out=await r.json();if(!r.ok)throw Error(out.error||'操作失败');return out}
async function act(action,data={},onConfirmed){if(busy)return false;busy=true;setNetworkStatus('正在提交…','pending');try{const out=await request('api/action',{action,room,token,requestId:globalThis.crypto?.randomUUID?.()||Date.now()+':'+Math.random(),...(state?.game==='holdem'&&!['ready','autoReady','rename','renameRoom','join'].includes(action)?{expectedVersion:state.version}:{}),...data});stateGeneration++;onConfirmed?.();if(out.token){token=out.token;remember(room,token,state.name);try{await recoverDeviceRooms()}catch{}}if(action==='leave'||action==='destroy'){forget();navigate(null);toast(action==='destroy'?'房间已销毁':'已离开房间');return true}last='';await poll();if(out.message)toast(out.message.replaceAll('索取','收取').replaceAll('索要','收取').replaceAll('赠送','给出'));return true}catch(e){toast(e.message+'；若结果不明，请先核对记录再操作');setNetworkStatus(e.message);return false}finally{busy=false;if($('#networkNotice')?.dataset?.kind==='pending')setNetworkStatus('')}}
const pollFlights=new Map();
async function poll(){if(!room)return;const key=JSON.stringify([room,token,stateGeneration]);if(pollFlights.has(key))return pollFlights.get(key);const flight=readRoomState();pollFlights.set(key,flight);try{return await flight}finally{if(pollFlights.get(key)===flight)pollFlights.delete(key)}}
async function readRoomState(){if(!room)return;const selected=room,selectedToken=token,generation=stateGeneration;const slow=setTimeout(()=>{if(selected===room&&selectedToken===token&&generation===stateGeneration&&!busy)setNetworkStatus('同步较慢，正在连接… · 请检查 Wi-Fi／热点连接及服务设备','pending')},2500);try{const r=await fetchWithTimeout(base+'api/state?room='+encodeURIComponent(room)+'&token='+encodeURIComponent(token));const s=await r.json();if(selected!==room||selectedToken!==token||generation!==stateGeneration)return;if(!r.ok){if(r.status===404){lockTableViewport(false);document.body.classList.remove('holdem-table','table-immersive','editing-seats','casual-table','theme-free','theme-three-card');syncCompareDialog(null);if(token)forget();$('#connection').textContent='房间不可用';$('#app').innerHTML=`<div class="join card"><h1>${esc(s.error)}</h1><p class="muted">房间只在房主销毁后关闭。你可以回到首页创建或加入其他房间。</p><button class="primary wide" id="home">返回首页</button></div>`;$('#home').onclick=()=>navigate(null);return}throw Error(s.error)}if(state?.room===s.room&&s.version<state.version)return;const priorState=state;roomSound.consume(s);state=s;$('#connection').textContent='● 已连接 · 每秒同步';if(!busy)setNetworkStatus('');if(s.me||s.isHost){remember(room,token,s.name,s.isHost,{game:s.game,gameName:s.gameName,phase:s.phase,hand:s.hand,playerName:s.players.find(p=>p.id===s.me)?.name})}else if(token){forget();removed=true}const signature=JSON.stringify(s);if(signature!==last){if(document.activeElement?.id==='joinName'&&last)return;last=signature;if(keyboardSessionActive()&&['holdem','zhajinhua','mahjong'].includes(s.game)&&priorState?.room===s.room){keyboardRenderDeferred=true}else{keyboardRenderDeferred=false;renderRoom()}}syncCompareDialog(state,act)}catch(e){if(selected!==room||selectedToken!==token)return;$('#connection').textContent='○ 连接中断 · 正在重试';if(!busy)setNetworkStatus('连接中断，正在重试 · 请检查 Wi-Fi／热点连接及服务设备')}finally{clearTimeout(slow)}}
function getConfig(form){const f=new FormData(form);return {...Object.fromEntries(Object.keys(defaults).map(k=>[k,Number(f.get(k))])) ,dealerMode:f.get('dealerMode')||'rotate',designatedDealer:state?.config?.designatedDealer||''}}
function selectedGameName(){return bootstrap?.games.find(g=>g.id===selectedGame)?.name||'炸金花'}
function homeHeader(){return `<div class="top"><div><div class="eyebrow">LOCAL GAME NIGHT · ${base==='/test/'?'测试空间':'线下游戏大厅'}</div><h1>把朋友，围成一桌。</h1><p class="muted">线下游戏，线上记分，娱乐为主，远离赌博。</p></div></div>`}
function rememberedRooms(known){return known.length?`<div class="card my-rooms"><div class="panel-heading hall-section-heading">${hallHeading('我参与的房间','rooms')}<small>${known.length} 间</small></div>${known.map(([code,x])=>`<button class="remembered wide" data-room="${esc(code)}"><span><b>${esc(x.name)}</b><small>${esc(x.gameName||bootstrap.games.find(g=>g.id===x.game)?.name||'游戏房间')} · ${x.isHost?'房主':'玩家'} · ${esc({lobby:'等待准备',finished:'本局已结算',playing:'对局进行中',dealing:'等待发牌',showdown:'等待摊牌',comparing:'等待比牌确认'}[x.phase]||'等待同步')} · ${esc(code)}</small></span><span>返回房间 →</span></button>`).join('')}<p class="rules">返回大厅保留身份和座位，真正退出请在房间内使用“离开房间”。</p></div>`:''}
function hallTools(){const local=bootstrap.isServiceDevice===true||(bootstrap.isServiceDevice===undefined&&['localhost','127.0.0.1','::1'].includes(location.hostname));return `<div class="card hall-tools"><div>${hallHeading(local?'我的身份与管理':'我的身份','identity')}<p class="rules">先保存个人身份牌，换浏览器也能找回房间。</p></div><div class="hall-tool-actions"><button id="hallIdentity" type="button">我的身份牌</button>${local?`<a class="admin-entry" href="${base}admin/">管理员入口 →</a>`:''}</div></div>`}
async function refreshKnownRooms(){let changed=false;try{changed=await recoverDeviceRooms()}catch{}const snapshots=Object.entries(identities);await Promise.all(snapshots.map(async([code,x])=>{try{const r=await fetchWithTimeout(base+'api/state?room='+encodeURIComponent(code)+'&token='+encodeURIComponent(x.token));const s=await r.json();if(identities[code]?.token!==x.token)return;if(r.status===404||(r.ok&&!s.me&&!s.isHost)){delete identities[code];changed=true}else if(r.ok&&(x.isHost!==s.isHost||x.name!==s.name||x.game!==s.game||x.phase!==s.phase||x.hand!==s.hand)){remember(code,x.token,s.name,s.isHost,{game:s.game,gameName:s.gameName,phase:s.phase,hand:s.hand,playerName:s.players.find(p=>p.id===s.me)?.name});changed=true}}catch{}}));if(changed){storage.setItem(key,JSON.stringify(identities));if(!room&&view==='home'&&!$('#roomCode')?.value)renderHome()}}
function invitationFields(url,id){return `<label for="${id}">房间邀请链接</label><input class="invitation-link" id="${id}" value="${esc(url)}" readonly aria-label="房间邀请链接">`}
function renderHome(){holdemActingKey='';holdemBetSnapshot=null;document.querySelector('.table-chip-effects')?.remove();lockTableViewport(false);document.body.classList.remove('in-room','holdem-table','table-immersive','casual-table','theme-free','theme-three-card');last='';$('#connection').textContent='● 本机服务';const known=Object.entries(identities);let content='';
if(view==='create'){content=`<div class="card"><button id="backHome" class="quiet">← 返回游戏大厅</button><div class="eyebrow" style="margin-top:20px">已选择 · ${esc(selectedGameName())}</div><h2>${selectedGame==='mahjong'?'开一间房，随时记分。':'先定规则，再开一间房。'}</h2><form id="create"><div class="settings"><div><label for="nickname">你的昵称</label><input id="nickname" name="nickname" maxlength="10" value="${esc(defaultNickname)}" required placeholder="你也是房主和玩家"></div><div><label for="roomName">房间名称</label><input id="roomName" name="name" maxlength="24" required value="${selectedGame==='mahjong'?'自由积分桌':'朋友的'+esc(selectedGameName())+'桌'}"></div></div>${selectedGame==='mahjong'?mahjongConfig():selectedGame==='holdem'?holdemConfig():configFields(defaults)}<div class="notice">${selectedGame==='mahjong'?'房间会一直保存，直到你主动销毁。朋友加入后即可随时给出、结算，无需准备或开始。':'房间会一直保存，直到你主动销毁。每局结束后，所有玩家重新准备再开下一把。'}</div><button class="primary wide">创建房间</button></form></div>`}
else if(view==='created'&&createdRoom){content=`<div class="card room-created"><div class="eyebrow">房间创建成功 · ${esc(bootstrap.games.find(g=>g.id===createdRoom.game)?.name||createdRoom.game)}</div><h2>${esc(createdRoom.name)}</h2><p class="rules">房间码 <b>${createdRoom.code}</b> · 你已成为房主并入座</p><img src="${base}join-qr.png?room=${createdRoom.code}" alt="当前房间邀请二维码" width="220" height="220"><p class="muted">朋友先连接同一 Wi-Fi，或连接服务设备开启的热点 Wi-Fi，再扫码或打开链接加入。</p>${invitationFields(createdRoom.invitation,'createdLink')}<button id="copyRoom" class="wide">复制房间邀请链接</button><div class="row success-actions"><button id="enterCreated" class="primary">进入房间</button><button id="backHome">返回大厅</button></div><p class="rules">房间会一直保存；返回大厅后，可从“我参与的房间”再次进入。</p></div>`}
else content=`${hallTools()}${rememberedRooms(known)}${gameCatalog(bootstrap.games,base)}<div class="card">${hallHeading('加入房间','join')}<p class="rules hall-section-intro">朋友已开好房？输入房间码加入。</p><form id="joinCode"><label for="roomCode">房间码</label><div class="row"><input id="roomCode" name="room" maxlength="6" placeholder="输入 6 位房间码" required><button class="primary">进入房间</button></div></form></div>`;
const entry=view==='home'?`<aside><div class="card entry">${hallHeading('扫码加入大厅','entry')}<img src="${base}entry-qr.png" alt="游戏大厅入口二维码" width="220" height="220"><p class="rules">玩家 A 用微信扫码，选择创建或加入房间。创建后，用房间邀请链接邀请其他玩家。</p><button id="copyEntry" class="wide">复制大厅链接</button>${bootstrap.isServiceDevice?'<button id="networkCheck" class="wide">检查局域网连接</button>':''}<p class="rules">仅需局域网，无需互联网<br>连接同一 Wi-Fi 或服务设备热点 Wi-Fi<br>${bootstrap.serviceDevice==='phone'?'保持手机应用在前台，避免锁屏':bootstrap.serviceDevice==='computer'?'保持电脑开机，避免休眠':'保持服务设备运行'}<br>积分只在各自房间内使用。</p></div></aside>`:'';
$('#app').innerHTML=(view==='created'?'':homeHeader())+`<div class="${view==='home'?'layout':'creation-layout'}"><section>${content}</section>${entry}</div>`;
$('#networkCheck')&&($('#networkCheck').onclick=showNetworkCheck);$('#hallIdentity')&&($('#hallIdentity').onclick=showHallIdentity);bindGameCatalog(game=>{selectedGame=game;view='create';renderHome()},game=>{const info=gameExplanation(game);formDialog(info.title,`<p class="muted">${esc(info.text)}</p>`,'知道了',async()=>true);const dialog=document.querySelector('dialog');dialog.addEventListener('click',e=>{const r=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom))dialog.close()})});$('#backHome')&&($('#backHome').onclick=()=>{view='home';renderHome();refreshKnownRooms()});$('#joinCode')&&($('#joinCode').onsubmit=e=>{e.preventDefault();const code=new FormData(e.target).get('room').trim().toUpperCase();if(!/^[A-F0-9]{6}$/.test(code)){toast('请输入 6 位房间码');return}navigate(code)});document.querySelectorAll('[data-room]').forEach(b=>b.onclick=()=>navigate(b.dataset.room));$('#copyEntry')&&($('#copyEntry').onclick=()=>copy(bootstrap.entry));$('#copyRoom')&&($('#copyRoom').onclick=()=>copy(createdRoom.invitation));$('#enterCreated')&&($('#enterCreated').onclick=()=>navigate(createdRoom.code));document.querySelectorAll('.invitation-link').forEach(x=>x.onclick=()=>x.select());
$('#create')&&($('#create').onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;const btn=e.target.querySelector('button');btn.disabled=true;try{const f=new FormData(e.target),out=await request('api/rooms',{game:selectedGame,name:f.get('name'),nickname:f.get('nickname'),config:selectedGame==='mahjong'?{initial:Number(f.get('initial')),poolEnabled:f.has('poolEnabled')}:selectedGame==='holdem'?getHoldemConfig(e.target):getConfig(e.target)});remember(out.room,out.token,f.get('name'),true);try{await recoverDeviceRooms()}catch{}const url=new URL(bootstrap.entry);url.searchParams.set('room',out.room);createdRoom={code:out.room,name:f.get('name'),game:selectedGame,invitation:url.href};view='created';renderHome();window.scrollTo(0,0)}catch(err){toast(err.message);btn.disabled=false}finally{busy=false}})
}
async function showNetworkCheck(){
 formDialog('局域网连接检查','<p id="networkResult" role="status">正在检查本机服务和邀请地址…</p><div id="networkPeer"></div>','完成',async()=>true);
 const dialog=$('dialog'),result=dialog.querySelector('#networkResult'),peer=dialog.querySelector('#networkPeer');
 try{
  const check=await request('api/network-check',{});if(!dialog.open)return;
  const basics=`本机服务：${check.loopback?'正常':'未通过'}；邀请 IP 自测：${check.lan?'正常':'未通过'}。`;
  result.textContent=basics+' 自测通过不代表其他设备可以连接。';
  peer.innerHTML=`<p>请另一台设备连接同一 Wi-Fi／本机热点，再扫码验证（3 分钟内有效）。</p><div style="text-align:center"><img src="${base}network-check-qr.png?check=${encodeURIComponent(check.check)}" alt="局域网连接验证二维码" width="220" height="220" style="max-width:100%;height:auto"></div><p class="rules">扫码打不开：检查是否连接相同网络，排查访客 Wi-Fi、AP／客户端隔离、防火墙与 VPN；可换服务设备热点再试。尚不能仅凭失败确定是哪项原因。</p>`;
  while(dialog.open){
   await new Promise(resolve=>setTimeout(resolve,2000));if(!dialog.open)return;
   const response=await fetchWithTimeout(base+'api/network-check?check='+encodeURIComponent(check.check));
   const state=await response.json();if(!dialog.open)return;
   if(!response.ok)throw Error(state.error||'检查失败');
   if(state.peer){result.textContent=basics+' 已确认另一台设备访问成功，当前链路可用；不代表所有设备均能连接。';return}
   result.textContent=basics+` 尚未收到另一台设备验证（剩余 ${state.expiresIn} 秒）。`;
  }
 }catch(error){if(dialog.open)result.textContent='检查未完成：'+error.message+'。请核对当前网络，换网后重启服务并重新扫码。'}
}

function renderRoom(){const s=state,me=s.players.find(p=>p.id===s.me),between=['lobby','finished'].includes(s.phase),phase={lobby:'等待准备',finished:'本局已结算',playing:'对局进行中',comparing:'等待比牌确认',showdown:'摊牌结算'}[s.phase];document.body.classList.add('in-room');lockTableViewport(!!(me||s.isHost));document.body.classList.toggle('holdem-table',!!(me||s.isHost));
if(!me&&!s.isHost){$('#app').innerHTML=`<div class="join card"><div class="eyebrow">房间 ${s.room} · ${esc(s.gameName)}</div><h1>${esc(s.name)}</h1><p class="muted">${removed?'你已离开或被房主移出，可重新申请加入。':`已有 ${s.players.length} 位玩家 · ${s.game==='mahjong'?'随时记分':phase}`}</p><form id="join"><label for="joinName">你的昵称</label><input id="joinName" name="name" maxlength="10" value="${esc(defaultNickname)}" required placeholder="大家怎么称呼你"><button class="primary wide" ${!between?'disabled':''}>${between?'加入房间':'本局进行中 · 结束后再加入'}</button></form><p class="rules">之前已入座？同一浏览器会自动恢复。换浏览器时请扫描你保存的个人身份二维码，找回原玩家和积分。</p><button type="button" id="restoreIdentity" class="wide">恢复原身份</button><button id="home" class="wide">返回游戏大厅</button></div>`;$('#restoreIdentity').onclick=()=>formDialog('恢复原身份','<p class="rules">请在相册中打开你保存的个人身份二维码，长按识别；或打开之前保存的身份恢复链接，即可回到原玩家和积分。</p>','知道了',async()=>true);$('#join').onsubmit=e=>{e.preventDefault();act('join',{name:new FormData(e.target).get('name')})};$('#home').onclick=()=>navigate(null);return}
if(s.game==='mahjong'||s.game==='zhajinhua'){renderCasualRoom();return}
if(s.game==='holdem'){renderHoldemRoom();return}
}

function closeTableMenu(){const menu=$('.table-detail-menu');if(!menu)return;menu.classList.remove('menu-open');menu.querySelector('.table-menu-toggle').setAttribute('aria-expanded','false');menu.querySelector('.table-detail-tools').hidden=true}
function bindTableMenu(){const menu=$('.table-detail-menu');if(!menu)return;if(state?.isHost){const sound=document.createElement('button');sound.type='button';sound.dataset.hostSound='true';sound.textContent=roomSound.label();sound.onclick=()=>{roomSound.unlock();sound.textContent=roomSound.toggle();toast(sound.textContent)};menu.querySelector('.table-detail-tools').append(sound);if(bootstrap?.voiceChoices?.length&&!window.__weizhuoNativeSpeech){
 const names=['清晰 · 系统','松朗 · 男声','悦然 · 女声','暖语 · Serena'],select=document.createElement('select');select.setAttribute('aria-label','播报音色');select.dataset.desktopVoice='true';
 if(!storage.getItem('weizhuo-announcer'+roomSound.scope)&&bootstrap.voiceChoices.includes(2))roomSound.localVoice=2;else if(!bootstrap.voiceChoices.includes(roomSound.localVoice))roomSound.localVoice=0;
 for(const id of bootstrap.voiceChoices){const option=document.createElement('option');option.value=id;option.textContent=names[id];select.append(option)}select.value=roomSound.localVoice;
 select.onchange=()=>{roomSound.clearNarration();roomSound.localVoice=Number(select.value);storage.setItem('weizhuo-announcer'+roomSound.scope,String(roomSound.localVoice))};
 const audition=document.createElement('button');audition.type='button';audition.dataset.desktopAudition='true';audition.textContent='试听播报'+(roomSound.playbackStatus?' · '+roomSound.playbackStatus:'');audition.onclick=()=>{roomSound.unlock();roomSound.clearNarration();roomSound.speak('三号玩家跟注二十分。三号玩家弃牌。本局已结算。')};menu.querySelector('.table-detail-tools').append(select,audition)
 }};const toggle=menu.querySelector('.table-menu-toggle'),panel=menu.querySelector('.table-detail-tools');toggle.onclick=()=>{const open=!menu.classList.contains('menu-open');menu.classList.toggle('menu-open',open);toggle.setAttribute('aria-expanded',String(open));panel.hidden=!open};menu.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();closeTableMenu();toggle.focus()}};panel.querySelectorAll('button').forEach(b=>b.addEventListener('click',closeTableMenu))}
function dismissTableMenuOutside(e){const menu=$('.table-detail-menu');if(menu?.classList.contains('menu-open')&&!menu.contains(e.target))closeTableMenu()}
document.addEventListener('pointerdown',dismissTableMenuOutside,true);document.addEventListener('click',dismissTableMenuOutside,true);
async function saveRuleFavorite(name,text){formDialog('收藏规则',`<label for="favoriteName">收藏名称</label><input id="favoriteName" name="name" maxlength="30" value="${esc(name)}" required><p class="rules">保存到你的个人身份，恢复身份后仍可查看。</p>`,'收藏',async f=>{try{const out=await request('api/device',{ruleFavorite:{action:'save',name:new FormData(f).get('name'),text}});if(!Array.isArray(out.ruleFavorites))throw Error('规则收藏需要更新后台服务');toast('规则已收藏');return true}catch(e){toast(e.message);return false}})}
async function showRuleFavorites(onSelect,onReturn){try{const out=await request('api/device',{});if(!Array.isArray(out.ruleFavorites))throw Error('规则收藏需要更新后台服务');const favorites=out.ruleFavorites;formDialog('我的规则收藏',`<p class="rules">绑定个人身份，可复制到其他房间。</p><div class="rule-favorites">${favorites.map(x=>`<section class="rule-favorite"><h3>${esc(x.name)}</h3><textarea readonly aria-label="${esc(x.name)}规则" rows="4">${esc(x.text)}</textarea><div class="favorite-actions"><button type="button" data-rule-copy="${x.id}">复制规则</button>${onSelect?`<button type="button" class="primary" data-rule-use="${x.id}">填入规则</button>`:''}<button type="button" data-rule-remove="${x.id}">取消收藏</button></div></section>`).join('')||'<p class="rules">还没有收藏，可在房间的规则中收藏。</p>'}</div>`,'关闭',async()=>true);let selected=false;const libraryDialog=$('dialog');if(onReturn)libraryDialog.addEventListener('close',()=>{if(!selected)onReturn()},{once:true});document.querySelectorAll('[data-rule-copy]').forEach(b=>b.onclick=()=>copy(favorites.find(x=>x.id===b.dataset.ruleCopy).text,'规则'));document.querySelectorAll('[data-rule-use]').forEach(b=>b.onclick=()=>{selected=true;onSelect(favorites.find(x=>x.id===b.dataset.ruleUse).text)});document.querySelectorAll('[data-rule-remove]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const result=await request('api/device',{ruleFavorite:{action:'remove',id:b.dataset.ruleRemove}});if(!Array.isArray(result.ruleFavorites))throw Error('规则收藏需要更新后台服务');b.closest('.rule-favorite').remove();toast('已取消收藏')}catch(e){toast(e.message);b.disabled=false}})}catch(e){toast(e.message)}}

function renderHoldemRoom(){
 restoreKeyboardEditor();
 const s=state,newBets=newHoldemBets(holdemBetSnapshot,s),newAwards=newHoldemAwards(holdemBetSnapshot,s);holdemBetSnapshot=s;const input=$('#holdemRaiseTo'),focused=document.activeElement?.id===input?.id;
 const draft=input?{value:input.value,edited:input.dataset.edited,turn:input.dataset.turn,street:input.dataset.street,hand:input.dataset.hand}:null;
 lockTableViewport(true);document.body.classList.add('in-room','holdem-table');document.body.classList.toggle('table-immersive',storage.getItem('weizhuo-immersive-v1'+base)==='1');$('#app').innerHTML=holdemRoom(s);const updateImmersive=()=>{const enabled=document.body.classList.contains('table-immersive');$('#tableImmersive').setAttribute('aria-pressed',String(enabled));$('#tableImmersive').setAttribute('aria-label',enabled?'退出沉浸牌桌':'沉浸牌桌')};bindHoldem(s,{renderTable:renderRoom,act,formDialog,confirmAction,copy,showIdentity,navigate,toggleImmersive:()=>{document.body.classList.toggle('table-immersive');storage.setItem('weizhuo-immersive-v1'+base,document.body.classList.contains('table-immersive')?'1':'0');updateImmersive()}});updateImmersive();bindTableMenu();

 const playerHistory=$('dialog[open] [data-player-history]');if(playerHistory){const old=playerHistory.querySelector('.seat-bet-details'),top=old?.scrollTop||0;playerHistory.innerHTML=playerHandHistory(s,playerHistory.dataset.playerHistory);const list=playerHistory.querySelector('.seat-bet-details');if(list)list.scrollTop=top}
 const liveActivity=$('dialog[open] .table-live-activity');if(liveActivity){const old=liveActivity.querySelector('.activity-stream'),following=!old||old.scrollHeight-old.clientHeight-old.scrollTop<32,top=old?.scrollTop||0;liveActivity.innerHTML=activity(s);const stream=liveActivity.querySelector('.activity-stream'),latest=liveActivity.querySelector('#latestActivity');if(stream){stream.scrollTop=following?stream.scrollHeight:top;if(latest)latest.onclick=()=>stream.scrollTop=stream.scrollHeight}}
 const amount=$('#holdemRaiseTo');if(amount){if(draft?.edited==='1'&&draft.turn===s.turn&&draft.street===s.street&&draft.hand===String(s.hand)){amount.value=draft.value;amount.dataset.edited='1';if(focused)amount.focus({preventScroll:true})}amount.dataset.turn=s.turn;amount.dataset.street=s.street;amount.dataset.hand=s.hand;amount.oninput=()=>amount.dataset.edited='1'}
 animateHoldemBets(newBets,base+'assets/holdem-chip-stack-v1.webp');animateHoldemAwards(newAwards,base+'assets/holdem-chip-stack-v1.webp');
}
function renderCasualRoom(){
 restoreKeyboardEditor();
 if(tableScrollActive&&state?.game==='mahjong'&&document.querySelector('.casual-layout')){tableScrollDeferred=true;return}
 const playerLeft=$('.simple-player-list')?.scrollLeft||0;
 const recordWindow=$('.simple-record-window'),recordTop=recordWindow?.scrollTop||0,followRecords=!recordWindow||recordWindow.scrollHeight-recordWindow.clientHeight-recordTop<24;
 const s=state,simple=s.game==='mahjong'&&(s.players.length>10||storage.getItem('weizhuo-free-view-v1'+base+':'+deviceKey)!=='table'),simpleScroll=$('.simple-free-view .poker-surface')?.scrollTop||0,freeRecords=newFreeRecords(casualSnapshot,s),detailFocus=document.activeElement?.id;captureCasualDraft();const amount=$('#casualAmount'),draft=amount?{value:amount.value,hand:amount.dataset.hand,turn:amount.dataset.turn,edited:amount.dataset.edited}:null,focused=document.activeElement?.id==='casualAmount',bets=s.game==='zhajinhua'?newHoldemBets(casualSnapshot,s):[],awards=s.game==='zhajinhua'&&casualSnapshot?.room===s.room&&casualSnapshot.hand===s.hand&&!casualSnapshot.result&&s.result?[{playerId:s.result.winnerId,amount:s.result.amount}]:[];casualSnapshot=s;
 lockTableViewport(true);document.body.classList.add('in-room','holdem-table','casual-table');document.body.classList.toggle('theme-free',s.game==='mahjong');document.body.classList.toggle('theme-three-card',s.game==='zhajinhua');document.body.classList.toggle('table-immersive',!simple&&storage.getItem('weizhuo-immersive-v1'+base)==='1');$('#app').innerHTML=casualRoom(s,simple);const simpleSurface=$('.simple-free-view .poker-surface');if(simpleSurface)simpleSurface.scrollTop=simpleScroll;const restoreRecords=()=>{const players=$('.simple-player-list');if(players)players.scrollLeft=playerLeft;const records=$('.simple-record-window');if(records)records.scrollTop=followRecords?records.scrollHeight:recordTop};restoreRecords();requestAnimationFrame(restoreRecords);
 const syncImmersive=()=>{$('#tableImmersive').setAttribute('aria-pressed',String(document.body.classList.contains('table-immersive')))};
 bindCasual(s,{act,formDialog,confirmAction,copy,saveRuleFavorite,showRuleFavorites,getConfig,showIdentity,navigate,renderTable:renderCasualRoom,toggleFreeView:()=>{storage.setItem('weizhuo-free-view-v1'+base+':'+deviceKey,simple?'table':'simple');renderCasualRoom()},toggleImmersive:()=>{document.body.classList.toggle('table-immersive');storage.setItem('weizhuo-immersive-v1'+base,document.body.classList.contains('table-immersive')?'1':'0');syncImmersive()}});syncImmersive();bindTableMenu();
 const input=$('#casualAmount');if(input){if(draft?.edited==='1'&&draft.hand===String(s.hand)&&draft.turn===s.turn){input.value=draft.value;input.dataset.edited='1';if(focused)input.focus({preventScroll:true})}input.dataset.hand=s.hand;input.dataset.turn=s.turn;input.oninput=()=>input.dataset.edited='1'}
 if(['tableGiveAmount','tableGiveNote'].includes(detailFocus))document.getElementById(detailFocus)?.focus({preventScroll:true});
 const live=$('dialog[open] .table-live-activity');if(live){const old=live.querySelector('.activity-stream'),top=old?.scrollTop||0,follow=!old||old.scrollHeight-old.clientHeight-old.scrollTop<32;live.innerHTML=activity(s);const stream=live.querySelector('.activity-stream');if(stream)stream.scrollTop=follow?stream.scrollHeight:top}
 requestAnimationFrame(()=>{animateFreeScores(freeRecords);animateHoldemBets([...bets,...freeRecords.filter(r=>r.kind==='押分到牌桌').map(r=>({playerId:r.changes[0].id,amount:-r.changes[0].delta}))],base+'assets/holdem-chip-stack-v1.webp');animateHoldemAwards([...awards,...freeRecords.filter(r=>r.kind==='奖池分配').flatMap(r=>r.changes.map(c=>({playerId:c.id,amount:c.delta})))],base+'assets/holdem-chip-stack-v1.webp')});
}

function showHallIdentity(){
 if(!deviceKey){toast('身份尚未生成，请检查连接后刷新');return}
 const url=new URL(bootstrap.entry);url.hash=new URLSearchParams({device:deviceKey}).toString();
 formDialog('我的个人身份牌',`<label for="defaultNickname">个人默认昵称</label><div class="row nickname-edit"><input id="defaultNickname" name="nickname" maxlength="10" value="${esc(defaultNickname)}" placeholder="设置常用昵称" autocomplete="nickname"><button type="button" id="saveNickname" class="primary" disabled>保存昵称</button></div><p class="rules">创建或加入房间时自动填写，重名依次补 A、B、C；已有房间昵称不变。</p><button type="button" id="hallRuleFavorites" class="wide">我的规则收藏</button><div class="invite-qr"><h3>个人身份二维码</h3><img src="${base}device-identity-qr.png?key=${encodeURIComponent(deviceKey)}" alt="个人身份恢复二维码" width="220" height="220"><p class="rules">请截图保存到相册。识别此二维码可恢复身份、昵称及关联房间。</p><button type="button" id="copyHallIdentity" class="wide">复制个人身份恢复链接</button><p class="notice">仅自己保管，请勿作为房间邀请转发。</p></div>`,'关闭',async()=>true);
 const field=$('#defaultNickname'),save=$('#saveNickname');let saving=false;
 const update=()=>save.disabled=saving||field.value.trim()===defaultNickname;field.oninput=update;
 save.onclick=async()=>{saving=true;field.disabled=true;update();try{const out=await request('api/device',{nickname:field.value.trim()});if(typeof out.nickname!=='string')throw Error('服务正在更新，请稍后重试');defaultNickname=out.nickname;field.value=defaultNickname;storage.setItem(nicknameStorageKey,defaultNickname);toast('默认昵称已保存')}catch(e){toast(e.message)}finally{saving=false;field.disabled=false;update()}};
 $('dialog form').onsubmit=e=>{e.preventDefault();if(!save.disabled)save.click()};

 $('#hallRuleFavorites').onclick=()=>showRuleFavorites();
 $('#copyHallIdentity').onclick=()=>copy(url.href,'个人身份恢复链接');
}
function showIdentity(){
 const me=state.players.find(p=>p.id===state.me),url=new URL(state.invitation);
 url.hash=new URLSearchParams({[state.isHost?'host':'player']:token}).toString();
 formDialog('我的身份二维码',`<div class="invite-qr"><h3>${esc(me?.name||'房主')} · ${esc(room)}</h3><img src="${base}identity-qr.png?room=${encodeURIComponent(room)}&token=${encodeURIComponent(token)}" alt="我的身份二维码" width="220" height="220"><p class="rules">请截图保存。关闭网页后重新扫码，可找回原玩家和积分；换浏览器也能恢复。</p><button type="button" id="copyIdentityLink" class="wide">复制身份恢复链接</button><p class="rules">这是你个人的身份二维码，请自己保存，不要作为房间邀请转发。</p></div>`,'完成',async()=>true);
 $('#copyIdentityLink').onclick=()=>copy(url.href,'身份恢复链接');
}
async function copy(url,label='邀请链接'){try{await navigator.clipboard.writeText(url);toast(label+'已复制')}catch{formDialog('复制'+label,`<label for="copyUrl">长按或全选复制</label><input id="copyUrl" value="${esc(url)}" readonly>`,'完成',async()=>true)}}
function formDialog(title,body,button,submit){const old=$('dialog');old?.remove();const dialog=document.createElement('dialog');dialog.innerHTML=`<form><div class="dialog-heading"><h2 id="dialogTitle" tabindex="-1">${esc(title)}</h2><button type="button" class="quiet" id="closeDialog" aria-label="关闭">✕</button></div>${body}<div class="row dialog-footer" style="margin-top:20px"><button type="button" id="cancelDialog">取消</button><button class="primary">${button}</button></div></form>`;dialog.setAttribute('aria-labelledby','dialogTitle');document.body.append(dialog);dialog.addEventListener('close',()=>{const sheet=$('.table-action-sheet');if(sheet&&!sheet.hidden)$('#closeTableActions')?.focus({preventScroll:true})});dialog.showModal();$('#dialogTitle').focus({preventScroll:true});$('#closeDialog').onclick=$('#cancelDialog').onclick=()=>dialog.close();if(['关闭','完成','知道了'].includes(button))dialog.querySelector('.dialog-footer').remove();dialog.querySelector('form').onsubmit=async e=>{e.preventDefault();const ok=await submit(e.target);if(ok)dialog.close()}}
function confirmAction(title,text,button,submit){formDialog(title,`<p class="muted" style="margin-top:14px">${text}</p>`,button,submit)}
window.addEventListener('popstate',()=>{lockTableViewport(false);holdemActingKey='';holdemBetSnapshot=null;document.querySelector('.table-chip-effects')?.remove();syncCompareDialog(null);room=new URLSearchParams(location.search).get('room');token=identities[room]?.token||'';last='';if(room)poll();else{view='home';renderHome();refreshKnownRooms()}});
async function init(){try{const r=await fetchWithTimeout(base+'api/bootstrap');bootstrap=await r.json();const versionLabel=$('#appVersion');if(versionLabel){versionLabel.textContent=bootstrap.appVersion?'版本 '+bootstrap.appVersion:'';versionLabel.hidden=!bootstrap.appVersion}if(incomingDevice){if(!/^[A-Za-z0-9_-]{32,128}$/.test(incomingDevice)){toast('个人身份凭证格式不正确')}else{deviceKey=incomingDevice;storage.setItem(deviceStorageKey,deviceKey);identities={};storage.setItem(key,'{}');room=null;token='';incoming=null;history.replaceState(null,'',roomUrl(null));toast('个人身份已恢复，正在找回房间')} }const suffix=base==='/test/'?':test':'';let oldToken;try{oldToken=sessionStorage.getItem('hostToken'+suffix)||(base==='/test/'?sessionStorage.getItem('testPlayerToken'):null)||localStorage.getItem('playerToken'+suffix)}catch{};if(!incomingDevice&&oldToken&&bootstrap.legacyRoom&&!identities[bootstrap.legacyRoom]&&!device)remember(bootstrap.legacyRoom,oldToken,'原有炸金花房间');if(incoming){room=room||bootstrap.legacyRoom;if(room){remember(room,incoming);history.replaceState(null,'',roomUrl(room));incoming=null}}try{await recoverDeviceRooms()}catch{}if(room){token=identities[room]?.token||'';await poll();try{await recoverDeviceRooms()}catch{}}else{renderHome();refreshKnownRooms()}}catch(e){setNetworkStatus(e.message);$('#app').innerHTML='<div class="card"><p>无法连接服务，请检查网络或唤醒运行服务的设备。</p><button id="retryConnection" class="primary">重新连接</button></div>';$('#retryConnection').onclick=()=>{setNetworkStatus('正在连接…','pending');init()}}}
// Internet reachability does not determine whether an offline LAN host is reachable.
let backgroundPolling=false;init();setInterval(async()=>{if(!backgroundPolling&&!document.hidden&&room&&(!document.querySelector('dialog[open]')||document.querySelector('#compareResultDialog[open],dialog[open] [data-player-history],dialog[open] .table-live-activity'))){backgroundPolling=true;try{await poll()}finally{backgroundPolling=false}}},1000);
window.addEventListener('online',()=>room?poll():init());window.addEventListener('offline',()=>room?poll():init());document.addEventListener('visibilitychange',()=>{if(!document.hidden&&room)poll()});

window.addEventListener('resize',()=>{const stream=document.querySelector('.activity-stream');if(stream&&activityFollowing)stream.scrollTop=stream.scrollHeight});

function dismissCompareDialog(dialog) {
  if (dialog?.open) dialog.close();
  dialog?.remove();
}

// Keep the host's pending comparison visible while state continues to sync.
function syncCompareDialog(state, act) {
  const current = document.getElementById('compareResultDialog');
  const pending = !document.body?.classList?.contains('casual-table') && state?.isHost && state.game !== 'mahjong' && state.phase === 'comparing' && state.pending;
  if (!pending) { dismissCompareDialog(current); return; }
  const signature = JSON.stringify([state.room, state.hand, state.round, pending]);
  if (current?.dataset.comparison === signature) return;
  // Finish an already open settings/confirmation dialog before prompting.
  if (document.querySelector('dialog[open]:not(#compareResultDialog)')) return;
  dismissCompareDialog(current);
  const actor = state.players.find(p => p.id === pending.actor);
  const target = state.players.find(p => p.id === pending.target);
  if (!actor || !target) return;
  const dialog = document.createElement('dialog');
  dialog.id = 'compareResultDialog';
  dialog.dataset.comparison = signature;
  dialog.setAttribute('aria-labelledby', 'compareResultTitle');
  dialog.innerHTML = `<form><h2 id="compareResultTitle">房主确认比牌赢家</h2><p class="muted compare-pair">${esc(actor.name)} 发起与 ${esc(target.name)} 的比牌。</p><p class="rules">请核对线下手牌后选择赢家。确认后败者退出本局；平牌时发起者出局，请选择 ${esc(target.name)}。</p><div class="compare-choices">${[actor, target].map(p => `<label><input type="radio" name="winner" value="${esc(p.id)}" required><span>${esc(p.name)} 获胜</span></label>`).join('')}</div><p class="compare-error" role="alert"></p><button class="primary wide" type="submit">确认赢家并继续牌局</button></form>`;
  // Escape must not silently dismiss an unresolved comparison.
  dialog.addEventListener('cancel', e => e.preventDefault());
  dialog.querySelector('form').onsubmit = async e => {
    e.preventDefault();
    const winner = new FormData(e.target).get('winner');
    if (![pending.actor, pending.target].includes(winner)) return;
    const controls = [...dialog.querySelectorAll('input,button')];
    controls.forEach(x => x.disabled = true);
    // Close as soon as the server accepts the result; refreshing can be slow.
    const ok = await act('resolve', {id: winner}, () => dismissCompareDialog(dialog));
    if (ok) dismissCompareDialog(dialog);
    else if (dialog.isConnected) {
      controls.forEach(x => x.disabled = false);
      dialog.querySelector('.compare-error').textContent = '确认未成功，请检查连接或最新牌局状态后重试。';
    }
  };
  document.body.append(dialog);
  dialog.showModal();
}

const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const headerSource=fs.readFileSync('static/zhajinhua.js','utf8').split('\n').filter(line=>line.startsWith('let profileMenuOpen')||line.startsWith('export const headerIcon')||line.startsWith('export function roomHeader')).join('\n').replace(/^export /gm,'');
const escapeSource=fs.readFileSync('static/zhajinhua.js','utf8').split('\n').find(line=>line.startsWith('export const esc')).replace('export ','');
function load(file,extra={}){
 const ctx=vm.createContext({console,...extra});
 const source=fs.readFileSync(file,'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
 vm.runInContext(escapeSource+'\n'+headerSource+'\nconst activity=()=>"";\n'+source,ctx);return ctx;
}
const ui=load('static/holdem.js');
const state={game:'holdem',name:'测试桌',room:'ABC123',me:'a',hostPlayer:'a',dealer:'a',smallBlindPlayer:'a',bigBlindPlayer:'b',isHost:true,isController:true,hand:1,phase:'playing',street:'preflop',currentBet:50,pot:70,readyCount:0,config:{smallBlind:5,bigBlind:10},players:[{id:'a',name:'甲',score:80,spent:20,streetSpent:20,active:true},{id:'b',name:'乙<img>',score:0,spent:50,streetSpent:50,active:true,allIn:true}],turn:'a',actionOptions:{canCheck:false,toCall:30,callDue:30,minRaiseTo:80,maxRaiseTo:100,canRaise:false,canAllIn:false},pots:[{id:'0',amount:40,eligible:['a','b']},{id:'1',amount:30,eligible:['b']}],bets:[],returns:[],history:[],canUndo:false};
let html=ui.holdemRoom(state);
assert.match(html,/跟注 30/);
assert.match(html,/本轮总投入（含已投入 20）/);
assert.match(html,/data-holdem-action="allIn" disabled/);
assert.match(html,/乙&lt;img&gt;/);
assert.doesNotMatch(html,/乙<img>/);
html=ui.holdemRoom({...state,phase:'showdown',turn:null});
const showdown={...state,phase:'showdown',turn:null};
assert.match(html,/id="settleTable"/);
assert.doesNotMatch(ui.holdemRoom({...state,isController:false}),/id="settleTable"|id="recordPlayer"|id="confirmDeal"|id="holdemUndo"/);
assert.doesNotMatch(html,/openPlayerActions|openHelperActions|table-action-sheet/);
assert.match(html,/tableConsole/);
assert.doesNotMatch(html,/type="checkbox"|pot-winners/);
assert.match(html,/table-settlement-center/);
assert.equal(ui.settlementReady(showdown),false);
assert.equal(ui.toggleSettlementWinner(showdown,'a'),true);
assert.equal(ui.settlementReady(showdown),true,'single eligible side pool is preselected');
assert.match(ui.tableSeats(showdown),/settlement-winner/);
assert.equal(ui.toggleSettlementWinner(showdown,'b'),true,'tied winners can be selected');
assert.equal(ui.settlementSelection(showdown).winners['0'].length,2);
ui.settlementSelection(showdown).index=1;
assert.equal(ui.toggleSettlementWinner(showdown,'a'),false,'ineligible side pool player cannot be chosen');
assert.equal(ui.settlementSelection({...showdown,version:999}).winners['0'].length,2,'poll preserves choices');
assert.equal(ui.settlementSelection({...showdown,hand:2}).winners['0'].length,0,'new hand resets choices');
ui.settlementSelection({...state,phase:'lobby'});
html=ui.holdemRoom({...state,phase:'dealing',dealPending:'flop'});
assert.match(html,/烧一张 · 发三张翻牌/);
assert.match(html,/翻牌已发好/);
const bet={seq:1,playerId:'a',amount:10,kind:'跟注'};
assert.equal(ui.newHoldemBets(null,{...state,bets:[bet]}).length,0,'entry must not replay old bets');
assert.equal(ui.newHoldemBets({...state,bets:[]},{...state,bets:[bet]}).length,1);
assert.equal(ui.newHoldemBets({...state,bets:[bet]},{...state,bets:[bet]}).length,0,'poll must not replay');
assert.equal(ui.newHoldemBets({...state,bets:[bet]},{...state,bets:[]}).length,0,'undo must not animate');
assert.equal(ui.newHoldemBets({...state,bets:[]},{...state,bets:[{...bet,amount:-10}]}).length,0,'refund is not a new wager');
assert.equal(ui.newHoldemBets({...state,bets:[bet]},{...state,hand:2,bets:[bet]}).length,1,'new hand blinds should animate');
const layout={width:390,height:844};
let viewport=ui.holdemViewportSize(layout);assert.equal(viewport.width,390);assert.equal(viewport.height,844);
viewport=ui.holdemViewportSize(layout,{width:390,height:430,offsetTop:180,offsetLeft:0,scale:1});assert.equal(viewport.height,430);assert.equal(viewport.top,180);assert.ok(viewport.top+viewport.height<=layout.height);
viewport=ui.holdemViewportSize(layout,{width:195,height:422,scale:2,offsetTop:100});assert.equal(viewport.height,844);assert.equal(viewport.top,0,'pinch zoom must not collapse the table layout');
viewport=ui.holdemViewportSize({width:844,height:390},{width:844,height:390,scale:1});assert.equal(viewport.width,844);assert.equal(viewport.height,390);
const ownView=ui.tableSeats({...state,me:'b'}).split('</button>')[0];
assert.match(ownView,/乙&lt;img&gt; · 我/);assert.match(ownView,/self-seat/);
assert.equal(ui.firstRecipient({...state,phase:'dealing',dealPending:'hole'}),'b','heads-up BB receives first');
assert.equal(ui.firstRecipient({...state,phase:'dealing',dealPending:'hole',players:[...state.players,{id:'c'}]}),'a','multiway SB receives first');
assert.match(ui.holdemRoom({...state,phase:'dealing',dealPending:'hole'}),/先收牌/);
assert.doesNotMatch(ui.holdemRoom({...state,phase:'lobby'}),/id="holdemReady"/,'host starts without ready');
assert.match(ui.holdemRoom({...state,phase:'lobby',me:'b',isHost:false,isController:false}),/id="holdemReady"/);
assert.doesNotMatch(ui.holdemRoom({...state,turn:'b'}),/id="holdemRaise"/,'waiting player has no betting panel');
assert.match(ui.holdemRoom(state),/seat-action-player/);
assert.match(ui.tableSeats({...state,players:state.players.map((p,i)=>({...p,playerNumber:i+7}))}),/seat-number">7<\/span>/);
assert.match(ui.tableSeats({...state,players:[{...state.players[1],playerNumber:8},{...state.players[0],playerNumber:7}]}).split('</button>')[0],/seat-number">7<\/span>/,'the same player keeps the number after reordering');
const ledger=ui.playerHandHistory({...state,bets:[{seq:1,playerId:'a',amount:5,kind:'小盲',street:'preflop',time:'12:00:01'},{seq:2,playerId:'b',amount:10,kind:'大盲',street:'preflop'},{seq:3,playerId:'a',amount:20,kind:'加注',street:'flop',time:'12:00:04'},{seq:4,playerId:'a',amount:-5,kind:'退还未跟注',street:'flop'}]},'a');
assert.match(ledger,/翻牌前/);assert.match(ledger,/翻牌/);assert.match(ledger,/投入 20/);assert.match(ledger,/退还 5/);assert.match(ledger,/12:00:04/);assert.doesNotMatch(ledger,/大盲/,'exclude other players wagers');
assert.match(ui.playerHandHistory(state,'a'),/本局暂无下注记录/);
for(const [width,height,cardWidth,cardHeight] of [[320,568,62,64],[390,844,74.1,74],[844,390,78,48]]){
 const positions=ui.holdemSeatPositions(10,width,height);assert.equal(positions.length,10);assert.ok(positions[0].y>=(width>height?70:80),'self stays on the lower rail with landscape progress clearance');
 for(let i=0;i<positions.length;i++)for(let j=i+1;j<positions.length;j++)assert.ok(Math.abs(positions[i].x-positions[j].x)*width/100>=cardWidth||Math.abs(positions[i].y-positions[j].y)*height/100>=cardHeight,`seat overlap ${width}x${height}: ${i},${j}`);
}
for(const [w,h] of [[320,568],[390,844],[844,390]])for(let count=2;count<=10;count++){
 const ps=ui.holdemSeatPositions(count,w,h);
 if(count>2){assert.ok(ps[1].x>50,"next player is on the right: counterclockwise from self");assert.ok(ps[count-1].x<50,"previous player is on the left")}
 const area=ps.reduce((sum,p,i)=>{const next=ps[(i+1)%count];return sum+p.x*next.y-next.x*p.y},0);
 if(count>2)assert.ok(area<0,"seat/action order is counterclockwise in screen coordinates");
 for(let i=1;i<count;i++){assert.ok(Math.abs(ps[i].x+ps[count-i].x-100)<.03,'mirror x');assert.ok(Math.abs(ps[i].y-ps[count-i].y)<.03,'mirror y')}
}
for(const [w,h,cw,ch] of [[320,568,62,64],[390,844,74.1,74],[520,827,84,74],[844,390,78,48]]){
 const ps=ui.holdemSeatPositions(10,w,h,{width:cw,height:ch}),portrait=h>=w,edgeX=portrait?16:48,edgeY=portrait?48:16;
 for(const p of ps){assert.ok(p.x*w/100-cw/2>=edgeX+5.9);assert.ok(p.x*w/100+cw/2<=w-edgeX-5.9);assert.ok(p.y*h/100-ch/2>=(portrait?edgeY-8:edgeY)+5.9);assert.ok(p.y*h/100+ch/2<=h-edgeY-5.9)}
 assert.ok(Math.abs(ps[0].y+ps[5].y-(100-(portrait?8/h*100:0)))<.03,'upper rail uses the 8px optical adjustment');
}
const result=ui.holdemResult({amount:101,awards:[{potId:'0',name:'甲',amount:51},{potId:'0',name:'乙',amount:50}],returns:[{name:'甲',amount:3}],scores:[{name:'甲',delta:4}]},1);
assert.match(result,/合计派奖 101 分/);assert.match(result,/未跟注部分退还 3 分/);assert.match(result,/<b>\+4<\/b>/);
const tiles=[['holdem','规则计分','德州扑克 盲注'],['mahjong','自由记分','自由记分 适合麻将、桌游、聚会小游戏等']].map(([game,category,search])=>({dataset:{game,category,search},wrapper:{hidden:false},closest(){return this.wrapper}}));
const filters=['all','规则计分','自由记分'].map(gameFilter=>({dataset:{gameFilter},setAttribute(){}}));
const help={dataset:{gameHelp:'mahjong'}},search={value:''},empty={hidden:true};
const catalog=load('static/games.js',{document:{querySelector:q=>q==='#gameSearch'?search:empty,querySelectorAll:q=>q==='[data-game]'?tiles:q==='[data-game-filter]'?filters:[help]}});
let chosen=[],explained=[];catalog.bindGameCatalog(x=>chosen.push(x),x=>explained.push(x));
search.value='麻将';search.oninput();assert.equal(tiles[0].wrapper.hidden,true);assert.equal(tiles[1].wrapper.hidden,false);
let stopped=false;help.onclick({stopPropagation(){stopped=true}});assert.equal(stopped,true);assert.deepEqual(chosen,[]);assert.deepEqual(explained,['mahjong']);
search.value='';filters[2].onclick();assert.equal(tiles[0].hidden,true);assert.equal(tiles[1].hidden,false);tiles[1].onclick();assert.deepEqual(chosen,['mahjong']);
assert.match(catalog.gameExplanation('mahjong').text,/不判断游戏规则或胜负/);
console.log('通过：德州操作、边池资格、底部座位、视口适配、面板时机、下注动画去重、目录筛选与独立说明。');

for(const anchor of [{left:8,top:220,width:62,height:64},{left:250,top:220,width:62,height:64},{left:129,top:470,width:62,height:64},{left:129,top:50,width:62,height:64}]){const panel={width:176,height:140},p=ui.seatHistoryPosition(anchor,{width:320,height:568},panel);assert.ok(p.left>=8&&p.top>=8&&p.left+176<=312&&p.top+140<=560);assert.ok(p.left+176<=anchor.left||p.left>=anchor.left+anchor.width||p.top+140<=anchor.top||p.top>=anchor.top+anchor.height,'history should not cover its anchor card')}

const awardsState={...state,phase:'finished',result:{awards:[{playerId:'a',amount:25},{playerId:'a',amount:15},{playerId:'b',amount:10}]}};
assert.equal(ui.newHoldemAwards(null,awardsState).length,0,'joining does not replay payout');
assert.equal(ui.newHoldemAwards(state,awardsState)[0].amount,40,'combine side pots by winner');
assert.equal(ui.newHoldemAwards(awardsState,awardsState).length,0,'poll does not replay payout');
assert.equal(ui.newHoldemAwards(state,{...awardsState,hand:2}).length,0,'different hand does not replay payout');
const synced={...showdown,winnerSelection:{activePot:'1',winners:{'0':['a'],'1':['b']}},isController:false};
assert.equal(ui.settlementSelection(synced).index,1);assert.match(ui.holdemRoom(synced),/房主正在确认赢家/);assert.match(ui.tableSeats(synced),/待确认赢家/);assert.doesNotMatch(ui.holdemRoom(synced),/id="settleTable"|data-settlement-step/);

const foldedShowdown={...showdown,winnerSelection:null,players:state.players.map(p=>({...p,active:p.id==='a'})),pots:[{id:'0',amount:70,eligible:['a']}]};
assert.match(ui.tableSeats(foldedShowdown),/settlement-ineligible.*folded/);assert.match(ui.tableSeats(foldedShowdown),/已弃牌/);assert.equal(ui.toggleSettlementWinner(foldedShowdown,'b'),false);
assert.match(ui.holdemRoom({...state,isController:false,phase:'dealing',dealPending:'hole'}),/等待助手发牌/);

assert.doesNotMatch(ui.holdemRoom(state),/id="tableAutoReady"/,'host only starts');
assert.match(ui.holdemRoom({...state,isHost:false,isController:false,me:'b'}),/id="tableAutoReady"[^>]*aria-pressed="false"/);
assert.match(ui.holdemRoom({...state,isHost:false,isController:false,me:'b',players:state.players.map(p=>({...p,autoReady:true}))}),/id="tableAutoReady"[^>]*aria-pressed="true"/);

assert.equal(ui.potChipCount(0,10),0);assert.equal(ui.potChipCount(15,10),1);assert.equal(ui.potChipCount(80,10),2);assert.equal(ui.potChipCount(200,10),3);assert.equal(ui.potChipCount(500,10),4);assert.equal(ui.potChipCount(1500,10),5);assert.equal(ui.potChipCount(1000000,10),6);assert.equal(ui.potChipCount(200,20),2,'denomination follows room blind scale');
assert.match(ui.holdemRoom({...state,pot:500}),/data-chip-count="4"/);

const readyTable={...state,phase:'lobby',players:state.players.map(p=>({...p,score:100,ready:p.id==='b'}))};
assert.match(ui.holdemRoom(readyTable),/2 \/ 2 位玩家已准备/,'host is implicitly ready');
assert.match(ui.holdemRoom({...readyTable,players:readyTable.players.map(p=>({...p,ready:false}))}),/1 \/ 2 位玩家已准备/,'host counts once while guest is waiting');

const casual=load('static/tabletop.js',{potChipPile:ui.potChipPile,pokerActionFeed:ui.pokerActionFeed,fitPokerActionFeed:ui.fitPokerActionFeed});
const z={...state,game:'zhajinhua',phase:'lobby',config:{ante:10,floor:0,minBet:10,maxBet:100,minCompare:1,maxRounds:7,allowBlindCompare:0},level:10,round:1,players:state.players.map((p,i)=>({...p,score:1000,playerNumber:i+1,ready:i===1,seen:i===1})),log:[]};
assert.match(casual.casualRoom(z),/2 \/ 2 位玩家已准备/);
assert.doesNotMatch(casual.casualRoom(z),/id="casualReady"/);
assert.equal(casual.tablePlayers({...z,me:'b'})[0].id,'b');
assert.equal(casual.compareCandidates({...z,players:z.players.map(p=>({...p,seen:false})),me:'b'}).length,1);
assert.equal(casual.compareCandidates({...z,players:z.players.map(p=>({...p,seen:p.id==='a'}))}).length,0,'seen cannot challenge blind when disabled');
assert.equal(casual.winnerCandidates({...z,phase:'showdown',players:z.players.map(p=>({...p,active:p.id==='b'}))})[0].id,'b');
const free={...z,game:'mahjong',transactions:[{kind:'给分',actor:'甲',time:'12:00',note:'结果',changes:[{id:'a',name:'甲',delta:-10},{id:'b',name:'乙',delta:10}]}]};
assert.match(casual.casualRoom(free),/点玩家给出/);assert.doesNotMatch(casual.casualRoom(free),/casualReady|casualBet|casualAutoReady/);
assert.doesNotMatch(casual.freeRecords(free,'b'),/-10 分/);assert.match(casual.freeRecords(free,'b'),/record-from">甲<\/span> <span class="record-action record-give">给了<\/span> <span class="record-name record-to">乙/);assert.match(casual.freeRecords(free,'b'),/10 分/);

assert.doesNotMatch(casual.casualSeats(free),/点击给出|自由积分/,'free cards omit repeated instructions');

assert.equal(casual.newFreeRecords(null,free).length,0);
assert.equal(casual.newFreeRecords({...free,transactions:[]},free).length,1);
assert.equal(casual.newFreeRecords(free,{...free,transactions:[]}).length,0,'undo does not replay score effects');

const playingZ={...z,phase:'playing',turn:'a'};
assert.match(casual.pokerActions(playingZ),/>闷注<\/button>/);
assert.match(casual.pokerActions({...playingZ,players:z.players.map(p=>({...p,seen:true}))}),/>跟注<\/button>/);
assert.doesNotMatch(casual.pokerActions(playingZ),/data-casual-action="seen"|data-casual-action="fold"/);
assert.equal(casual.pokerActions({...playingZ,turn:'b'}),'');
const waitingActions=casual.pokerBasics({...playingZ,turn:'b'});
assert.match(waitingActions,/data-casual-action="seen"/);
assert.match(waitingActions,/data-casual-action="fold" disabled/);
assert.doesNotMatch(waitingActions,/casualBet|casualCompare/);
const selectingZ={...playingZ,phase:'comparing',pending:{actor:'a',target:'b'},winnerSelection:'b'};
assert.match(casual.casualRoom(selectingZ),/selecting-players/);
assert.match(casual.selectionNotice(selectingZ),/请选择获胜玩家/);
assert.match(casual.casualSeats(selectingZ),/selection-medal/);
assert.doesNotMatch(casual.casualSeats(selectingZ),/ acting/);
assert.match(casual.selectionNotice({...selectingZ,isHost:false}),/等待房主选择赢家/);
assert.equal(ui.tableKeyboardLayout({width:393,height:852},{width:393,height:500,offsetTop:0,scale:1},true,852).active,true);
assert.equal(ui.tableKeyboardLayout({width:393,height:852},{width:393,height:500,offsetTop:40,scale:1},true,852).bottom,312);
assert.equal(ui.tableKeyboardLayout({width:393,height:852},{width:393,height:500,scale:2},true,852).active,false);
assert.equal(ui.tableKeyboardLayout({width:393,height:852},{width:393,height:500,scale:1},false,852).active,false);
assert.equal(ui.tableKeyboardLayout({width:393,height:500},{width:393,height:500,scale:1},true,852).active,true);

assert.doesNotMatch(casual.casualRoom({...free,config:{initial:0,poolEnabled:false}}),/牌桌奖池，押分与分配|点奖池押分|<small>奖金池/);
assert.match(casual.casualRoom({...free,config:{initial:0,poolEnabled:false}}),/点玩家给出 \/ 收取/);
assert.match(casual.casualRoom({...free,config:{initial:0,poolEnabled:true}}),/牌桌奖池，押分与分配/);

const pendingFree={...free,paymentRequests:[{id:'req-a',requester:'a',payer:'b',amount:1,status:'pending',time:'12:00'}]};
assert.match(casual.collectionPrompt(pendingFree),/等待确认/);
assert.match(casual.collectionPrompt(pendingFree),/data-request-cancel="req-a"/);
assert.match(casual.collectionPrompt({...pendingFree,me:'b'}),/data-request-accept="req-a"/);
assert.equal(casual.collectionPrompt({...pendingFree,paymentRequests:[{...pendingFree.paymentRequests[0],status:'cancelled'}]}),'');
assert.match(casual.collectionPrompt({...pendingFree,paymentRequests:[...pendingFree.paymentRequests,{...pendingFree.paymentRequests[0],id:'req-b'}]}),/全部 2 笔/);

// Unrelated requests never enter a player's list, prompt or badge (including hosts).
const personalState={...pendingFree,isHost:true,paymentRequests:[...pendingFree.paymentRequests,{id:'unrelated',requester:'c',payer:'d',amount:99,status:'pending'}]};
assert.equal(casual.personalRequests(personalState).length,1);
assert.doesNotMatch(casual.collectionList(personalState),/unrelated|99 分/);
assert.doesNotMatch(casual.collectionPrompt(personalState),/全部 2 笔/);
assert.match(casual.casualRoom(personalState,true),/我的收取请求 · 1/);
assert.equal(casual.personalRequests({...personalState,me:null}).length,0);

const negativePoker={...z,phase:'playing',turn:'a',round:1,level:10,config:{...z.config,minBet:10,maxBet:100,minCompare:1,allowNegative:1},players:z.players.map(p=>({...p,active:true,score:-50,spent:10}))};
assert.doesNotMatch(casual.pokerActions(negativePoker),/disabled/);
assert.match(casual.pokerActions({...negativePoker,config:{...negativePoker.config,allowNegative:0}}),/disabled/);

const simpleFreeHtml=casual.casualRoom({...free,config:{initial:0,poolEnabled:false}},true);
assert.match(simpleFreeHtml,/simple-free-view/);
assert.match(simpleFreeHtml,/simple-player-list/);
assert.match(simpleFreeHtml,/simple-score-records/);
assert.doesNotMatch(simpleFreeHtml,/id="freePool"/,'disabled pool has no empty placeholder');
const pooledSimple=casual.casualRoom({...free,config:{initial:0,poolEnabled:true}},true);
assert.ok(pooledSimple.indexOf('simple-player-list')<pooledSimple.indexOf('simple-pool-section'));
assert.ok(pooledSimple.indexOf('simple-pool-section')<pooledSimple.indexOf('simple-score-records'));
assert.match(pooledSimple,/data-simple-section="pool" open/);
assert.match(pooledSimple,/data-simple-section="records" open/);
assert.match(casual.casualRoom({...free,players:Array.from({length:12},(_,i)=>({...free.players[0],id:'p'+i}))},true),/data-rows="2"/);
assert.match(simpleFreeHtml,/切换为牌桌视图/);
assert.doesNotMatch(simpleFreeHtml,/free-trade-feed/);
assert.doesNotMatch(casual.casualRoom(z,true),/simple-free-view/);

// Confirmed collection reads requester -> action -> payer; giving reads payer -> action -> recipient.
const exchangeRecords={...free,transactions:[{kind:'给分',actor:'A',time:'10:00',changes:[{name:'A<',delta:-2},{name:'B',delta:2}]},{kind:'索取确认',actor:'B',time:'10:01',changes:[{name:'A<',delta:-3},{name:'B',delta:3}]}]};
const ledgerHtml=casual.casualRoom(exchangeRecords,true),tableLedger=casual.freeTradeFeed(exchangeRecords);
for(const html of [ledgerHtml,tableLedger]){
 assert.match(html,/record-from">A&lt;<\/span> <span class="record-action record-give">给了<\/span> <span class="record-name record-to">B/);
 assert.match(html,/record-from">B<\/span> <span class="record-action record-collect">收了<\/span> <span class="record-name record-to">A&lt;/);
 assert.match(html,/record-score">3 分/);
 assert.ok(html.indexOf('10:00')<html.indexOf('10:01'));
}
assert.match(ledgerHtml,/simple-record-window.*aria-label="最近记分记录"/);

// Exercise actual touch handlers: scrolling regions must bypass the page lock,
// and a deferred render resumes only after the finger and momentum have stopped.
const touchSource=fs.readFileSync('static/app.js','utf8');
const touchHandlers={},touchTimers=new Map();let touchTimerId=0,touchRenders=0;
const touchContext=vm.createContext({document:{addEventListener:(type,fn)=>touchHandlers[type]=fn,documentElement:{classList:{contains:()=>true}},querySelector:()=>({})},state:{game:'mahjong'},renderCasualRoom:()=>touchRenders++,setTimeout:fn=>{touchTimers.set(++touchTimerId,fn);return touchTimerId},clearTimeout:id=>touchTimers.delete(id)});
vm.runInContext(touchSource.slice(touchSource.indexOf('const tableScrollRegions='),touchSource.indexOf('function toast(')),touchContext);
function touchEvent(region){return {target:{closest:selector=>region&&selector.split(',').includes(region)?{}:null},touches:[{}],prevented:false,preventDefault(){this.prevented=true}}}
for(const region of ['.simple-player-list','.simple-free-view .poker-surface','.simple-record-window','.sentence-records']){const e=touchEvent(region);touchHandlers.touchmove(e);assert.equal(e.prevented,false,region+' allows native touch panning')}
const outsideTouch=touchEvent(null);touchHandlers.touchmove(outsideTouch);assert.equal(outsideTouch.prevented,true,'table background still cannot scroll the whole page');
const recordTouch=touchEvent('.simple-record-window');touchHandlers.touchstart(recordTouch);vm.runInContext('tableScrollDeferred=true',touchContext);assert.equal(vm.runInContext('tableScrollActive',touchContext),true);
touchHandlers.touchend({touches:[]});const firstIdle=touchTimerId;touchHandlers.scroll(recordTouch);assert.equal(touchTimers.has(firstIdle),false,'momentum extends the render deferral');touchTimers.get(touchTimerId)();assert.equal(touchRenders,1);assert.equal(vm.runInContext('tableScrollActive',touchContext),false);
touchHandlers.touchstart(recordTouch);vm.runInContext('tableScrollDeferred=true',touchContext);touchHandlers.touchcancel();touchTimers.get(touchTimerId)();assert.equal(touchRenders,2,'cancelled gesture releases deferred render');
vm.runInContext(touchSource.split('\n').find(line=>line.startsWith("document.addEventListener('contextmenu'")),touchContext);
const buttonMenu=touchEvent('button');touchHandlers.contextmenu(buttonMenu);assert.equal(buttonMenu.prevented,true,'button long press cannot open copy/context menu');
const ledgerMenu=touchEvent('dialog .sentence-records .simple-score-row');touchHandlers.contextmenu(ledgerMenu);assert.equal(ledgerMenu.prevented,false,'full ledger text retains native selection/context menu');
const tableRecordMenu=touchEvent('.simple-score-row');touchHandlers.contextmenu(tableRecordMenu);assert.equal(tableRecordMenu.prevented,true,'table records cannot open long-press copy');

// Clock text is not an ordering key: midnight and same-second events stay stable.
const chronologySource=fs.readFileSync('static/zhajinhua.js','utf8').split('\n').find(line=>line.startsWith('export const activityChronology')).replace('export ','');
const chronologyContext=vm.createContext({});
vm.runInContext(chronologySource+'\nthis.chronology=activityChronology',chronologyContext);
const newestFirst=[{time:'00:00:01',text:'最新'},{time:'00:00:01',text:'同秒较早'},{time:'23:59:59',text:'昨日'}];
assert.equal(chronologyContext.chronology(newestFirst).map(x=>x.text).join(','),'昨日,同秒较早,最新');
assert.equal(newestFirst[0].text,'最新','display ordering must not mutate persisted state');

const actionsHtml=ui.pokerActionFeed({...state,handActions:[{hand:0,playerName:'旧局',action:'弃牌',time:'23:59:59'},{hand:1,playerName:'乙<img>',action:'加注',amount:20,time:'00:00:01'},{hand:1,playerName:'甲',action:'弃牌',time:'00:00:01'}]});
assert.doesNotMatch(actionsHtml,/旧局|乙<img>/);assert.match(actionsHtml,/乙&lt;img&gt;.*加注.*20 分/);assert.ok(actionsHtml.indexOf('加注')<actionsHtml.indexOf('弃牌'));assert.match(ui.pokerActionFeed(state),/hidden/);

const dynamic=vm.createContext({console});vm.runInContext(fs.readFileSync('static/zhajinhua.js','utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,''),dynamic);
const colored=dynamic.activityMarkup({text:'Snow 跟注 20 分'}, {players:[{name:'Snow'}]});
assert.match(colored,/activity-player.*Snow/);assert.match(colored,/activity-action.*跟注/);
const archived=dynamic.activityMarkup({text:'旧名 弃牌',parts:[{kind:'player',text:'旧名'},{kind:'text',text:' '},{kind:'action',text:'弃牌'}]}, {players:[{name:'新名'}]});
assert.match(archived,/activity-player.*旧名/);assert.match(archived,/activity-danger/);
assert.match(dynamic.activityMarkup({text:'<img> 加注',parts:[{kind:'player',text:'<img>'},{kind:'text',text:' '},{kind:'action',text:'加注'}]}, {players:[]}),/&lt;img&gt;/);
// Auto advance centers the new stage; polls retain manual inspection of the track.
let stageLeft=0,scrollCalls=[];const currentStage={textContent:'翻牌',offsetLeft:270,clientWidth:90,setAttribute(){}};
const stageTrack={clientWidth:270,get scrollLeft(){return stageLeft},set scrollLeft(v){stageLeft=v},querySelector(){return currentStage},querySelectorAll(){return [currentStage]},scrollTo(v){scrollCalls.push(v.left);stageLeft=v.left}};
ui.document={querySelector(){return stageTrack}};ui.window={matchMedia(){return {matches:true}}};
ui.fitHoldemProgress('bar-test');assert.equal(scrollCalls.at(-1),180);
stageLeft=90;stageTrack.onscroll();ui.fitHoldemProgress('bar-test');assert.equal(stageLeft,90,'poll does not erase manual progress browsing');
currentStage.textContent='转牌';currentStage.offsetLeft=360;ui.fitHoldemProgress('bar-test');assert.equal(scrollCalls.at(-1),270,'next stage moves to the right and is centered');

// Dense seats cannot squeeze a central turn panel; toolbar and own seat stay clear.
const panelStyle={setProperty(k,v){this[k]=v}},panel={style:panelStyle,getBoundingClientRect:()=>({height:240})};
const decisionLayout={getBoundingClientRect:()=>({top:0,bottom:568,width:320}),classList:{contains:()=>false},querySelectorAll:()=>[{getBoundingClientRect:()=>({width:36,height:36,bottom:100})}]};
const decisionSurface={closest:()=>decisionLayout,getBoundingClientRect:()=>({top:105,height:429,width:320}),querySelector:()=>null};
ui.fitCentralActionPanel(decisionSurface,panel,462);
assert.equal(panelStyle.width,'288px');assert.equal(panelStyle.maxWidth,'288px');
const panelCenter=parseFloat(panelStyle['--seat-action-top']);assert.ok(panelCenter-120>=112);assert.ok(panelCenter+120<=452);
console.log('中央操作布局通过：密集座位保持可读宽度，避开流程和本人卡片。');

const desktopLayout={...decisionLayout,getBoundingClientRect:()=>({top:0,bottom:800,height:800,width:1280})};
ui.fitCentralActionPanel({...decisionSurface,closest:()=>desktopLayout,getBoundingClientRect:()=>({top:0,height:800,width:1280})},panel,720);
assert.equal(panelStyle.width,'740px');
// If seat avoidance would crop submit buttons, use the remaining table area.
ui.fitCentralActionPanel(decisionSurface,panel,278);
const expandedCenter=parseFloat(panelStyle['--seat-action-top']);
assert.ok(expandedCenter-120>=112&&expandedCenter+120<=552);
assert.ok(expandedCenter+120>268,'complete actions take priority over the old seat cutoff');


const keyboardNative={visible:true,width:393,height:852,top:490};
assert.equal(ui.nativeKeyboardViewport({width:393,height:852},{width:393,height:852,scale:1},keyboardNative,true).height,490);
assert.equal(ui.nativeKeyboardViewport({width:393,height:852},{width:393,height:500,offsetTop:40,scale:1},keyboardNative,true).height,490,'native keyboard boundary ignores WebKit focus pan');
assert.equal(ui.nativeKeyboardViewport({width:393,height:852},{width:393,height:852,scale:2},keyboardNative,true).height,490,'native keyboard geometry wins over stale scale');

// Rail projection must follow the photo, including native surface offsets and cover crops.
for(const scene of [
 {width:1024,height:1536,left:.105,right:.895,top:.055,bottom:.91},
 {width:1024,height:1536,left:.145,right:.855,top:.067,bottom:.902},
 {width:852,height:1846,left:.16,right:.84,top:.163,bottom:.855}
])for(const [width,height] of [[393,852],[320,568],[852,393],[1280,720]]){
 const box={left:16,top:128,width,height},area={left:16,top:174,width,height:height-46};
 const rail=ui.projectTableRail(box,area,scene,false);
 assert.ok(Math.abs(rail.top+46-height*scene.top)<.001,'scene coordinates compensate surface offset');
 assert.ok(Math.abs(rail.bottom+46-height*scene.bottom)<.001);
 assert.ok(Math.abs(rail.left+rail.right-width)<.001,'horizontal scene center stays symmetric');
}
const coverRail=ui.projectTableRail({left:0,top:0,width:393,height:600},{left:0,top:0}, {width:852,height:1846,left:.16,right:.84,top:.163,bottom:.855},true);
assert.ok(coverRail.top<100,'cover crop changes the rail, rather than treating the photo as stretched');
for(const [width,height] of [[393,852],[320,568],[852,393],[1280,720]]){
 const portrait=height>=width,rail=portrait?{left:width*.14,right:width*.86,top:height*.16,bottom:height*.84}:{left:width*.12,right:width*.88,top:height*.18,bottom:height*.82};
 const ps=ui.holdemSeatPositions(2,width,height,{width:62,height:64},rail);
 assert.ok(Math.abs(ps[0].y*height/100-rail.bottom)<.03,'bottom card center straddles the scene rail');
 assert.ok(Math.abs(ps[1].y*height/100-rail.top)<.03,'top card center straddles the scene rail');
 assert.ok(Math.abs(ps[0].x-ps[1].x)<.03,'top and bottom seats share the same axis');
}
console.log('牌桌背景投影回归通过：三种场景、全屏偏移、cover 裁切与上下桌沿对称。');

// Reproduce a three-player feed: no upper-middle seat, plus a label above the pot box.
{
const box={left:0,top:0,right:393,bottom:852,width:393,height:852};
const rect=(left,top,width,height)=>({left,top,right:left+width,bottom:top+height,width,height});
const feedRows=Array.from({length:8},()=>({hidden:false})),feed={hidden:false,style:{},children:feedRows};
const potLabel={getBoundingClientRect:()=>rect(140,330,110,18)};
const pot={getBoundingClientRect:()=>rect(120,355,150,75),children:[potLabel]};
const stage={getBoundingClientRect:()=>rect(60,10,270,36)};
const layout={style:{setProperty(){}},getBoundingClientRect:()=>box,querySelector:()=>null,querySelectorAll:()=>[stage],classList:{contains:()=>false}};
const surface={getBoundingClientRect:()=>box,closest:()=>layout,querySelector:q=>q==='.poker-action-feed'?feed:pot,querySelectorAll:()=>[rect(270,220,85,70),rect(38,220,85,70),rect(150,710,85,70)].map(r=>({getBoundingClientRect:()=>r}))};
ui.document={documentElement:{classList:{contains:()=>false}},body:{classList:{contains:()=>false}}};
ui.getComputedStyle=()=>({backgroundSize:'100% 100%',getPropertyValue:k=>({'--scene-width':1024,'--scene-height':1536,'--scene-left':.11,'--scene-right':.89,'--scene-top':.075,'--scene-bottom':.88}[k]||'')});
ui.fitPokerActionFeed(surface);
assert.equal(parseFloat(feed.style.left),393/2,'feed block shares the scene center');
assert.equal(feed.style.transform,'translateX(-50%)');
assert.ok(parseFloat(feed.style.top)>120,'three-player feed starts on felt, not the upper wood rail');
assert.ok(parseFloat(feed.style.top)+feedRows.filter(r=>!r.hidden).length*19<330,'floating pot label is also a blocker');
console.log('三人记录回归通过：记录居中在桌布上，避让独立定位的奖池文字。');

}
{
 const box={left:0,top:0,width:393,height:852},scene={width:1024,height:1536,left:.105,right:.895,top:.055,bottom:.91};
 const rail=ui.projectTableRail(box,box,scene),seats=ui.holdemSeatPositions(10,393,852,{width:62,height:64},rail),cx=(rail.left+rail.right)/2;
 assert.ok(rail.radiusY>rail.radiusX,'a tall stretched photo has an elliptical cap');
 for(const p of seats){const x=p.x/100*393,y=p.y/100*852,top=rail.top+rail.radiusY,bottom=rail.bottom-rail.radiusY;
  if(y<top||y>bottom){const cy=y<top?top:bottom;assert.ok(Math.abs((x-cx)**2/rail.radiusX**2+(y-cy)**2/rail.radiusY**2-1)<.001,'card center follows the projected elliptical rail');}
  else assert.ok(Math.min(Math.abs(x-rail.left),Math.abs(x-rail.right))<.03,'card center follows the straight rail');
 }
}
console.log('多人桌沿回归通过：长屏弧线跟随场景缩放，卡片中心落在实际椭圆桌沿。');

// Produce synthetic narration from the real room event generator, never private rooms.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ctx=vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8').split('import {casualRoom')[0].replace(/^export /gm,''),ctx);
const players=Array.from({length:20},(_,i)=>({id:'p'+i,name:'测试'+i,playerNumber:i+1,active:true,seen:false}));
const base={room:'voice-test',version:1,isHost:true,me:'p0',game:'mahjong',players,transactions:[],paymentRequests:[],log:[],bets:[],handActions:[],hand:1,phase:'playing',turn:'p0'};
const sentences=new Set();
function emit(before,after){for(const event of ctx.roomSoundEvents(before,after))if(event.speech)sentences.add(event.speech)}
for(let i=0;i<40;i++){
 const amount=[1,20,125,1280,10005,1000000][i%6];
 for(const kind of ['给分','索取确认','调整积分']){
  const changes=kind==='调整积分'?[{id:'p0',name:'测试0',delta:amount}]:[{id:'p0',name:'测试0',delta:-amount},{id:'p1',name:'测试1',delta:amount}];
  emit(base,{...base,version:i+2,transactions:[{seq:i,time:'12:00',kind,changes}]});
  emit(base,{...base,version:i+2,transactions:[{seq:i,time:'12:00',kind,changes:[{id:'p0',name:'测试0',delta:-2*amount},{id:'p1',name:'测试1',delta:amount},{id:'p2',name:'测试2',delta:amount}]}]});
 }
 emit(base,{...base,version:i+2,soundRequests:[{id:'r'+i,payer:'p'+(i+3)%20,requester:'p'+(i+1)%20,status:'pending',amount}]});
 for(const game of ['holdem','zhajinhua'])for(const action of ['下注','跟注','加注','闷注','全下','比牌','弃牌','看牌','过牌'])
  emit({...base,game},{...base,game,version:i+2,handActions:[{playerId:'p'+i%20,playerName:'测试',action,amount:['弃牌','看牌','过牌'].includes(action)?0:amount,time:'12:00'}]});
}
for(let version=2;version<10;version++)for(const [stage,word] of [['hole','底牌'],['flop','翻牌'],['turn','转牌'],['river','河牌']]){
 const poker={...base,game:'holdem'};
 emit(poker,{...poker,version,phase:'dealing',dealPending:stage});
 emit({...poker,phase:'dealing',dealPending:stage},{...poker,version,turn:'p1',log:[{text:word+'已发好',time:'12:00'}]});
 emit({...poker,phase:'lobby'},{...poker,version,hand:2,phase:'dealing',dealPending:stage});
 emit(poker,{...poker,version,phase:'showdown'});
 emit(poker,{...poker,version,turn:'p'+version});
 emit(poker,{...poker,version,phase:'finished',result:{awards:[{playerId:'p0',name:'测试0',amount:125},{playerId:'p1',name:'测试1',amount:250}]}});
}
process.stdout.write(JSON.stringify([...sentences],null,2));

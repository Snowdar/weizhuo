"""Room lifecycle, identities and action transactions."""
import secrets, threading, copy, hashlib, re, json, time
from .games import GAMES, FRESH, GAME_NAMES
from .games.zhajinhua import fresh, fail

class Rooms:
    def __init__(self,repository):self.repo=repository;self.lock=threading.RLock()
    def room(self,code):
        s=self.repo.get(str(code or '').upper())
        if not s:fail('房间不存在，请检查房间码')
        if s.get('destroyedAt'):fail('这个房间已被房主销毁')
        return s
    def device_rooms(self,secret,bindings=None):
        if not isinstance(secret,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',secret):fail('设备凭证不正确')
        device=hashlib.sha256(secret.encode()).hexdigest()
        with self.lock:
            # Existing room tokens prove ownership when migrating old devices.
            for binding in (bindings or [])[:100]:
                if not isinstance(binding,dict):continue
                code=str(binding.get('room','')).upper();token=str(binding.get('token',''))
                s=self.repo.get(code)
                if not s or s.get('destroyedAt'):continue
                host,p=GAMES[s['game']](s).identity(token)
                if host or p:self.repo.bind_device(device,code,token)
            out=[]
            for code,token in self.repo.device_rooms(device):
                s=self.repo.get(code)
                if not s or s.get('destroyedAt'):continue
                host,p=GAMES[s['game']](s).identity(token)
                if host or p:out.append(dict(room=code,token=token,name=s['name'],isHost=host,game=s['game'],gameName=GAME_NAMES[s['game']],phase=s['phase'],hand=s['hand'],playerName=p['name'] if p else '房主'))
            return out
    def device_nickname(self,secret,nickname=None):
        if not isinstance(secret,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',secret):fail('设备凭证不正确')
        if nickname is not None:
            if not isinstance(nickname,str):fail('默认昵称格式不正确')
            nickname=nickname.strip()
            if len(nickname)>10:fail('默认昵称最多 10 个字')
        with self.lock:
            return self.repo.device_nickname(hashlib.sha256(secret.encode()).hexdigest(),nickname)

    def device_rule_favorites(self,secret,change=None):
        if not isinstance(secret,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,128}',secret):fail('设备凭证不正确')
        device=hashlib.sha256(secret.encode()).hexdigest()
        with self.lock, self.repo.connect() as db:
            if change is not None:
                if not isinstance(change,dict):fail('规则收藏格式不正确')
                if change.get('action')=='save':
                    name,text=change.get('name'),change.get('text')
                    if not isinstance(name,str) or not name.strip() or len(name.strip())>30:fail('收藏名称需为 1–30 个字')
                    if not isinstance(text,str) or not text.strip() or len(text.strip())>2000:fail('规则需为 1–2000 个字')
                    name,text=name.strip(),text.strip()
                    old=db.execute('SELECT id FROM device_rule_favorites WHERE device=? AND text=?',(device,text)).fetchone()
                    if old:
                        db.execute('UPDATE device_rule_favorites SET name=? WHERE device=? AND id=?',(name,device,old[0]))
                    else:
                        if db.execute('SELECT COUNT(*) FROM device_rule_favorites WHERE device=?',(device,)).fetchone()[0]>=50:fail('最多收藏 50 条规则')
                        db.execute('INSERT INTO device_rule_favorites VALUES (?,?,?,?,?)',(device,secrets.token_hex(12),name,text,time.time()))
                elif change.get('action')=='remove':
                    if not isinstance(change.get('id'),str):fail('收藏编号不正确')
                    db.execute('DELETE FROM device_rule_favorites WHERE device=? AND id=?',(device,change['id']))
                else:fail('规则收藏操作不正确')
            return [dict(id=x[0],name=x[1],text=x[2]) for x in db.execute('SELECT id,name,text FROM device_rule_favorites WHERE device=? ORDER BY created_at DESC,id',(device,))]

    def admin_rooms(self):
        with self.lock, self.repo.connect() as db:
            saved=[json.loads(row[0]) for row in db.execute('SELECT data FROM rooms')]
            return [dict(room=s['room'],name=s['name'],game=s['game'],phase=s['phase'],hand=s['hand'],pot=s['pot'],version=s['version'],players=len(s['players']),host=next((p['name'] for p in s['players'] if p['id']==s.get('hostPlayer')),'未入座'),createdAt=s.get('createdAt',0)) for s in sorted(saved,key=lambda s:s.get('createdAt',0),reverse=True) if not s.get('destroyedAt')]

    def admin_clear(self,code,version,confirmation):
        if confirmation!=code:fail('请确认清理房间')
        out=self.admin_clear_many([dict(room=code,version=version)],True)
        return {**out,'room':code}

    def admin_clear_many(self,items,confirmed):
        with self.lock:
            if confirmed is not True:fail('请确认清理所选房间')
            if not isinstance(items,list) or not 1<=len(items)<=200:fail('请选择 1–200 个房间')
            saved=[];codes=set()
            for item in items:
                if not isinstance(item,dict):fail('房间选择不正确')
                code,version=item.get('room'),item.get('version')
                if not isinstance(code,str) or code in codes:fail('房间选择不正确或重复')
                codes.add(code);s=self.room(code)
                if isinstance(version,bool) or not isinstance(version,int) or version!=s['version']:fail('房间已发生变化，请刷新列表后重新确认')
                saved.append(s)
            # Validate the entire selection, then back up before one atomic transaction.
            folder=self.repo.path.parent/'backups';folder.mkdir(parents=True,exist_ok=True)
            backup=folder/('admin-cleanup-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4)+'.sqlite3')
            import sqlite3
            with self.repo.connect() as src, sqlite3.connect(backup) as dst:src.backup(dst)
            backup.chmod(0o600)
            with self.repo.connect() as db:
                for s in saved:
                    s['destroyedAt']=time.time();s['version']+=1
                    self.repo.save(s,connection=db)
            return dict(message=f'已清理 {len(saved)} 个房间，清理前已保存备份',rooms=[s['room'] for s in saved])

    def create(self,d):
        with self.lock:
            if d.get('game') not in GAMES:fail('请选择支持的游戏')
            name=str(d.get('name','')).strip()
            if not 1<=len(name)<=24:fail('房间名称需要 1–24 个字')
            while True:
                s=FRESH[d['game']](name=name,config=d.get('config',{}))
                if not self.repo.get(s['room']):break
            e=GAMES[s['game']](s)
            e.action(dict(action='hostSeat',token=s['host'],name=d.get('nickname')))
            e.log('房间已创建，朋友加入后可随时给分、结算' if s['game']=='mahjong' else '房间已创建，邀请朋友加入后，每人准备即可开局')
            self.repo.save(s)
            return dict(room=s['room'],token=s['host'])
    def execute(self,code,d):
        with self.lock:
            s=self.room(code);rid=d.get('requestId')
            if rid and (not isinstance(rid,str) or len(rid)>100):fail('请求编号不正确')
            key=str(d.get('token',''))+':'+str(rid)
            if rid and key in s['requests']:return s['requests'][key]
            # Loaded state is a private transaction copy; failed actions never commit.
            engine=GAMES[s['game']](s); action=d.get('action'); remove_hand=None
            if s['game']=='holdem' and 'expectedVersion' in d:
                v=d['expectedVersion']
                if isinstance(v,bool) or not isinstance(v,int) or v!=s['version']:fail('房间状态已更新，请核对当前流程后重试')
            if action=='undo':
                host,_=engine.identity(d.get('token',''))
                if not host and not (s['game']=='holdem' and engine.controller(d.get('token',''))):fail('只有房主或德州扑克发牌协助者可撤回动作')
                if not s.get('undo'):fail('没有可撤回的动作')
                player_names={p['id']:p['name'] for p in s['players']}
                auto_ready={p['id']:p['autoReady'] for p in s['players'] if 'autoReady' in p} if s['game'] in ('holdem','zhajinhua') else {}
                entry=s['undo'].pop()
                if s.get('result') and not entry['state'].get('result'):remove_hand=s['hand']
                retained={k:s[k] for k in ('requests','version','log','undo','name')}
                if 'scoringRules' in s:retained['scoringRules']=s['scoringRules']
                s.clear();s.update(entry['state']);s.update(retained)
                for player in s['players']:
                    if player['id'] in player_names:player['name']=player_names[player['id']]
                    if player['id'] in auto_ready:
                        player['autoReady']=auto_ready[player['id']]
                        if s['phase'] in ('lobby','finished') and player['id']!=s.get('hostPlayer') and player['autoReady']:
                            player['ready']=player['score']>0 if s['game']=='holdem' else bool(s['config'].get('allowNegative',0) or player['score']-s['config']['ante']>=s['config']['floor'])
                engine.log('房主撤回了上一次动作：'+entry['label'])
                result={}
            else:
                reversible=action in ('seen','call','raise','fold','hostFold','adjust','compare','resolve','settle','cancel','config','actFor') and s['phase'] in ('playing','comparing','showdown')
                if s['game']=='holdem':reversible=action in ('check','call','bet','raise','allIn','fold','deal','actFor','settle','cancel') and s['phase'] in ('playing','dealing','showdown')
                if s['game']=='mahjong':reversible=action in ('transfer','transferAll','manualSettle','adjust','config','depositPool','allocatePool') or (action=='resolveTransfer' and d.get('accepted') is True)
                before=copy.deepcopy({k:v for k,v in s.items() if k not in ('requests','version','log','undo','name')}) if reversible else None
                result=engine.action({**d,'room':s['room']}) or {}
                if reversible:
                    labels={'check':'过牌','bet':'下注','allIn':'全下','deal':'确认发牌','actFor':'协助代记','depositPool':'牌桌押分','allocatePool':'分配奖池','resolveTransfer':'确认索取','transfer':'给分','transferAll':'全场赠送','manualSettle':'手动结算','adjust':'调整积分','seen':'看牌','call':'跟注','raise':'加注','hostFold':'房主补记弃牌','fold':'弃牌','compare':'发起比牌','resolve':'确认比牌赢家','settle':'摊牌结算','cancel':'撤销本局','config':'调整规则'}
                    s.setdefault('undo',[]).append(dict(state=before,label=labels[action]))
                    s['undo']=s['undo'][-100:]
                elif action not in ('rename','renameRoom','selectWinner','autoReady','editScoringRules'):
                    # A new hand or lobby membership/score changes form an undo boundary.
                    s['undo']=[]
            s['version']+=1
            if rid:
                s['requests'][key]=result
                while len(s['requests'])>200:del s['requests'][next(iter(s['requests']))]
            self.repo.save(s,remove_hand=remove_hand);return result
    def public(self,code,token,invitation):
        with self.lock:
            s=self.room(code);host,p=GAMES[s['game']](s).identity(token)
            out={k:v for k,v in s.items() if k not in ('host','players','requests','undo')}
            out['players']=[{**{k:v for k,v in x.items() if k!='token'},'isHost':x['id']==s.get('hostPlayer')} for x in s['players']]
            out.update(canUndo=(host or (s['game']=='holdem' and GAMES[s['game']](s).controller(token))) and bool(s.get('undo')),undoLabel=s['undo'][-1]['label'] if (host or (s['game']=='holdem' and GAMES[s['game']](s).controller(token))) and s.get('undo') else None,isHost=host,me=p['id'] if p else None,invitation=invitation,gameName=GAME_NAMES[s['game']],readyCount=sum(bool(x.get('ready')) for x in s['players']),history=self.repo.histories(code),architectureVersion=2)
            if s['game']=='mahjong':
                out['paymentRequests']=[r for r in s.get('paymentRequests',[]) if p and p['id'] in (r['requester'],r['payer'])]
                # Host-only audio feed is separate from personal, actionable requests.
                if host:out['soundRequests']=[{k:r[k] for k in ('id','requester','payer','amount','status','time') if k in r} for r in s.get('paymentRequests',[])]
            if s['game']=='holdem':
                e=GAMES['holdem'](s)
                out['isController']=e.controller(token)
                out['actionOptions']=e.options(e.player(s['turn'])) if s['turn'] else None
                out['pots']=e.build_pots() if s['phase']=='showdown' or (s['phase'] not in ('lobby','finished') and any(p.get('allIn') for p in s['players'])) else s.get('pots',[]) if s['phase']=='finished' else []
            return out

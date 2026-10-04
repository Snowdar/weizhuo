import secrets, time

DEFAULT = dict(initial=1000, ante=10, minBet=10, maxBet=100, minRaise=0, floor=0, minCompare=1, maxRounds=7)
LEGACY_DEFAULT = dict(initial=1000, ante=5, base=10, maxBet=200, cap=500, floor=0, allowNegative=0, minCompare=2, maxRounds=10)
RULE_OPTIONS = dict(seenRaisesFloor=0, allowBlindCompare=1, allowNegative=1)
BETWEEN = ('lobby', 'finished')

def fail(msg): raise ValueError(msg)
def integer(v,label,lo,hi):
    if isinstance(v,bool) or not isinstance(v,int) or not lo<=v<=hi: fail(f'{label}必须是 {lo} 到 {hi} 之间的整数')
    return v

def validate_config(data):
    if not isinstance(data,dict): fail('规则格式不正确')
    c={k:integer(data.get(k,v),k,-100000 if k=='floor' else 0 if k in ('minRaise','maxRounds') else 1,100000) for k,v in DEFAULT.items()}
    c.update({k:integer(data.get(k,v),k,0,1) for k,v in RULE_OPTIONS.items()})
    mode=data.get('dealerMode','rotate')
    if mode not in ('rotate','winner','fixed'):fail('庄家模式不正确')
    c.update(dealerMode=mode,designatedDealer=str(data.get('designatedDealer','')))
    if 'base' in data:
        c['base']=integer(data['base'],'暗牌起跟分',1,100000)
        c['minBet']=c['base']
    if 'cap' in data:c['cap']=integer(data['cap'],'每局封顶',1,100000)
    if not c['floor']<c['initial'] or c['minBet']>c['maxBet']:fail('积分下界应低于初始积分，单次押注下限不能超过上限')
    if 'cap' in c and (c['maxBet']>c['cap'] or c['ante']+c['minBet']*2>c['cap']):fail('旧版每局封顶不足以支付底注和跟注')
    return c

def fresh(code=None, config=None, name='炸金花房间'):
    return dict(room=code or secrets.token_hex(3).upper(), name=name, game='zhajinhua', createdAt=time.time(), destroyedAt=None, version=0, host=secrets.token_urlsafe(24), config=validate_config(config or {}), players=[], hostPlayer=None, phase='lobby', hand=0, dealer=None, turn=None, level=10, pot=0, round=1, acted=[], pending=None, log=[], bets=[], result=None, requests={})

class Engine:
    def __init__(self,state):
        self.s=state
        used=set()
        number=max(state.get('nextPlayerNumber',1),max((p.get('playerNumber',0) for p in state['players']),default=0)+1)
        for p in state['players']:
            n=p.get('playerNumber')
            if not isinstance(n,int) or n<1 or n in used:
                p['playerNumber']=number;number+=1
            used.add(p['playerNumber'])
        state['nextPlayerNumber']=number
    def log(self, msg, names=()):
        import re
        players={p['name'] for p in self.s['players']}|set(names)
        actions={'弃牌','看牌','跟注','闷注','加注','下注','全下','过牌','比牌','结算','准备','开始','发牌','更名','撤回','撤销','加入','离开','移除','调整积分','收取','给分'}
        tokens=sorted(players|actions,key=len,reverse=True)
        parts=[];at=0
        for match in re.finditer('|'.join(re.escape(x) for x in tokens if x),msg) if tokens else ():
            if match.start()>at:parts.append(dict(text=msg[at:match.start()],kind='text'))
            token=match.group();parts.append(dict(text=token,kind='player' if token in players else 'action'));at=match.end()
        if at<len(msg):parts.append(dict(text=msg[at:],kind='text'))
        self.s['log'].insert(0, dict(time=time.strftime('%H:%M:%S'), text=msg, parts=parts))
        self.s['log'] = self.s['log'][:150]

    def record_action(self, p, action, amount=None):
        records=self.s.setdefault('handActions',[])
        records.append(dict(hand=self.s['hand'],playerId=p['id'],playerName=p['name'],action=action,amount=amount,time=time.strftime('%H:%M:%S')))
        self.s['handActions']=records[-150:]

    def player(self, pid):
        return next((p for p in self.s['players'] if p['id']==pid), None)
    def live(self): return [p for p in self.s['players'] if p['active']]
    def charge(self, p, amount, kind='投入'):
        c=self.s['config']
        if not c.get('allowNegative',0) and p['score']-amount<c['floor']: fail('积分下界不足以支付本次投入，可选择弃牌，或由房主调整投入限制')
        if c.get('cap') is not None and p['spent']+amount>c['cap']: fail('本次投入将超过每局封顶，可选择弃牌，或由房主调整投入限制')
        p['score']-=amount; p['spent']+=amount; self.s['pot']+=amount
        bets=self.s.setdefault('bets',[])
        bets.append(dict(seq=len(bets)+1,playerId=p['id'],playerName=p['name'],amount=amount,kind=kind,cardState='明' if p['seen'] else '暗',round=self.s['round'],time=time.strftime('%H:%M:%S')))

    def settle(self, pid, reason):
        p=self.player(pid)
        if not p or not p['active']: fail('请选择本局仍在场的赢家')
        amount=self.s['pot']; p['score']+=amount
        self.s['lastWinner']=p['id']
        self.s['result']=dict(winnerId=p['id'],winner=p['name'], amount=amount, reason=reason, bets=list(self.s.get('bets',[])), scores=[dict(name=x['name'], delta=x['score']-x['start']) for x in self.s['players']])
        self.log(f"第 {self.s['hand']} 局结束：{p['name']} 获得底池 {amount} 分（{reason}）")
        for x in self.s['players']: x['ready']=bool(x.get('autoReady') and x['id']!=self.s.get('hostPlayer') and (self.s['config'].get('allowNegative',0) or x['score']-self.s['config']['ante']>=self.s['config']['floor']))
        self.s['winnerSelection']=None
        self.s['phase']='finished'; self.s['turn']=None; self.s['pot']=0; self.s['pending']=None

    def enforce_limits(self):
        if self.s['phase']!='playing': return
        c=self.s['config']
        if c['maxRounds'] and self.s['round']>c['maxRounds']:
            self.s['round']=c['maxRounds']
            for p in self.live():p['seen']=True
            self.s['phase']='showdown'; self.s['turn']=None
            self.log('行动轮数已用完，请强制摊牌并确认赢家')

    def advance(self, pid):
        remaining=self.live()
        if len(remaining)==1: self.settle(remaining[0]['id'], '其他玩家弃牌 / 比牌出局'); return
        if pid not in self.s['acted']: self.s['acted'].append(pid)
        if all(p['id'] in self.s['acted'] for p in remaining):
            self.s['round']+=1; self.s['acted']=[]
        self.enforce_limits()
        if self.s['phase']=='showdown': return
        ids=[p['id'] for p in self.s['players']]; idx=ids.index(pid)
        for n in range(1,len(ids)+1):
            q=self.player(ids[(idx+n)%len(ids)])
            if q['active']: self.s['turn']=q['id']; break

    def identity(self, token):
        owner=secrets.compare_digest(str(token),self.s['host'])
        p=next((x for x in self.s['players'] if secrets.compare_digest(str(token),x['token'])),None)
        if owner: p=self.player(self.s.get('hostPlayer'))
        return owner or bool(p and p['id']==self.s.get('hostPlayer')),p

    def action(self, d):
        a=d.get('action'); token=d.get('token','')
        host,p=self.identity(token)
        if a=='actFor':
            if not host:fail('此操作需要房主权限')
            q=self.player(d.get('playerId'));op=d.get('operation')
            if not q or op not in ('seen','call','fold','compare'):fail('代记动作不正确')
            return self.action({**d,'action':op,'token':q['token']})
        if a=='selectWinner':
            if not host:fail('此操作需要房主权限')
            q=self.player(d.get('id'))
            eligible=[self.s['pending']['actor'],self.s['pending']['target']] if self.s['phase']=='comparing' else [x['id'] for x in self.live()] if self.s['phase']=='showdown' else []
            if not q or q['id'] not in eligible:fail('请选择可获胜的在场玩家')
            self.s['winnerSelection']=q['id'];return {}
        if a=='autoReady':
            if not p or host:fail('自动准备仅供非房主玩家使用')
            enabled=d.get('enabled')
            if not isinstance(enabled,bool):fail('自动准备状态不正确')
            p['autoReady']=enabled
            if self.s['phase'] in BETWEEN:p['ready']=bool(enabled and (self.s['config'].get('allowNegative',0) or p['score']-self.s['config']['ante']>=self.s['config']['floor']))
            return {}
        if a=='renameRoom':
            if not host:fail('只有房主可修改房间名')
            name=str(d.get('name','')).strip()
            if not 1<=len(name)<=24:fail('房间名称需要 1–24 个字')
            old=self.s['name'];self.s['name']=name
            self.log(f'房主将房间名从 {old} 改为 {name}');return {}
        if a=='rename':
            if not p:fail('请先入座')
            name=str(d.get('name','')).strip()
            if not 1<=len(name)<=10:fail('昵称需要 1–10 个字')
            if any(x['id']!=p['id'] and x['name']==name for x in self.s['players']):fail('昵称已被使用')
            old=p['name'];p['name']=name;self.log(f'{old} 更名为 {name}',names=(old,name));return {}
        if a=='seating':
            if not host:fail('此操作需要房主权限')
            if self.s['phase'] not in BETWEEN:fail('请在局间调整座位')
            ids=d.get('ids');current=[x['id'] for x in self.s['players']]
            if not isinstance(ids,list) or len(ids)!=len(current) or any(not isinstance(i,str) for i in ids) or set(ids)!=set(current):fail('座位名单已变化，请重新调整')
            if 'config' in d:
                c=validate_config(d['config'])
                if c['designatedDealer'] and c['designatedDealer'] not in current:fail('指定庄家已不在房间')
                self.s['config']=c
            self.s['players']=[self.player(i) for i in ids]
            for x in self.s['players']:x['ready']=False
            self.log('房主调整了座位顺序：'+' → '.join(x['name'] for x in self.s['players']));return {}
        if a=='hostFold':
            if not host:fail('此操作需要房主权限')
            q=self.player(d.get('id'))
            if self.s['phase'] not in ('playing','comparing','showdown') or not q or not q['active']:fail('该玩家当前不能弃牌')
            q['active']=False;self.record_action(q,'弃牌');self.log(f"房主为 {q['name']} 补记弃牌")
            pending=self.s.get('pending')
            if pending and q['id'] in (pending['actor'],pending['target']):
                self.s.update(pending=None,phase='playing',winnerSelection=None);self.advance(pending['actor'])
            elif len(self.live())==1:self.settle(self.live()[0]['id'],'房主补记弃牌')
            elif self.s['phase']=='playing':
                if self.s['turn']==q['id']:self.advance(q['id'])
                elif all(x['id'] in self.s['acted'] for x in self.live()):
                    self.s['round']+=1;self.s['acted']=[];self.enforce_limits()
            return {}
        if a=='ready':
            if not p: fail('请先加入房间')
            if self.s['phase'] not in ('lobby','finished'): fail('请在本局结束后准备')
            c=self.s.get('pendingConfig',self.s['config'])
            value=d.get('ready',True)
            if not isinstance(value,bool): fail('准备状态不正确')
            if value and not c.get('allowNegative',0) and p['score']-c['ante']<c['floor']: fail('积分不足底注，请房主调整积分后再准备')
            p['ready']=value
            if not value:p['autoReady']=False
            self.log(f"{p['name']} {'已准备' if value else '取消准备'}"); return {}
        if a=='leave':
            if not p: fail('请先加入房间')
            if host: fail('房主请返回首页或销毁房间')
            if self.s['phase'] not in ('lobby','finished'): fail('请在本局结束后离开')
            self.s['players'].remove(p); self.log(f"{p['name']} 离开房间"); return {}
        if a=='destroy':
            if not host: fail('只有房主可销毁房间')
            if self.s['phase'] not in ('lobby','finished'): fail('请先结算或撤销本局，再销毁房间')
            self.s['destroyedAt']=time.time(); self.log('房主销毁了房间'); return {}
        if a=='hostSeat':
            if not host: fail('此操作需要房主权限')
            if self.player(self.s.get('hostPlayer')): fail('房主已经入座')
            if d.get('id'):
                q=self.player(d['id'])
                if not q: fail('玩家不存在')
            else:
                result=self.action(dict(action='join',name=d.get('name'),room=self.s['room']))
                q=next(x for x in self.s['players'] if x['token']==result['token'])
            self.s['hostPlayer']=q['id']; self.log(f"{q['name']} 作为房主参与牌局"); return {}
        if a=='join':
            if self.s['phase'] not in ('lobby','finished'): fail('本局进行中，请下一局再加入')
            if str(d.get('room','')).upper()!=self.s['room']: fail('房间码不正确')
            name=str(d.get('name','')).strip()
            if not 1<=len(name)<=10: fail('昵称需要 1–10 个字')
            requested_name=name
            used={x['name'] for x in self.s['players']}
            if name in used:
                name=next(name[:9]+letter for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if name[:9]+letter not in used)
            limit=20 if self.s['game']=='mahjong' else 10
            if len(self.s['players'])>=limit: fail(f'一桌最多 {limit} 人')
            p=dict(id=secrets.token_hex(8), token=secrets.token_urlsafe(24), name=name, score=self.s.get('pendingConfig',self.s['config'])['initial'], spent=0, active=False, seen=False, ready=False, start=self.s.get('pendingConfig',self.s['config'])['initial'])
            p['playerNumber']=self.s.get('nextPlayerNumber',1);self.s['nextPlayerNumber']=p['playerNumber']+1
            self.s['players'].append(p); self.log(f'{name} 加入牌桌'); return {'token':p['token'],**({'message':f'房间内昵称重复，已使用 {name}'} if name!=requested_name else {})}
        if a in ('config','start','settle','resolve','remove','adjust','cancel','reset'):
            if not host: fail('此操作需要房主权限')
            if a=='config':
                options=d.get('config',{})
                if not isinstance(options,dict):fail('规则格式不正确')
                c=validate_config({**{k:self.s['config'].get(k,v) for k,v in RULE_OPTIONS.items()},'dealerMode':self.s['config'].get('dealerMode','rotate'),'designatedDealer':self.s['config'].get('designatedDealer',''),**options})
                if c['designatedDealer'] and not self.player(c['designatedDealer']):fail('指定庄家已不在房间')
                self.s['config']=c; self.s.pop('pendingConfig',None)
                if self.s['phase'] in BETWEEN:
                    for x in self.s['players']: x['ready']=False
                if self.s['phase'] in ('playing','comparing'):
                    self.s['level']=max(c['minBet'],((self.s['level']+c['base']-1)//c['base'])*c['base']) if 'base' in c else max(c['minBet'],self.s['level'])
                    self.enforce_limits()
                self.log('房主更新了规则，即时生效（已投入积分不重算，初始积分仅用于新玩家）')
                return {'message':'设置已保存并立即生效；现有积分与已投入积分不重算'}
            elif a=='start':
                if self.s['phase'] not in ('lobby','finished'): fail('已有进行中的牌局')
                config=self.s.get('pendingConfig',self.s['config'])
                if len(self.s['players']) < 2: fail('至少需要 2 位玩家')
                if not all(x['id']==self.s.get('hostPlayer') or x.get('ready') for x in self.s['players']): fail('所有在座玩家都准备后才能开局')
                eligible=[x for x in self.s['players'] if config.get('allowNegative',0) or x['score']-config['ante']>=config['floor']]
                if len(eligible)!=len(self.s['players']): fail('有玩家积分不足底注，请先调整积分')
                if len(eligible)<2: fail('至少需要 2 位能够支付底注的玩家')
                self.s['config']=config; self.s.pop('pendingConfig',None)
                ids=[x['id'] for x in self.s['players']]; old=ids.index(self.s['dealer']) if self.s['dealer'] in ids else -1
                dealer=next(ids[(old+n)%len(ids)] for n in range(1,len(ids)+1) if self.player(ids[(old+n)%len(ids)]) in eligible)
                mode=config.get('dealerMode','rotate')
                if mode=='fixed':dealer=config.get('designatedDealer') if config.get('designatedDealer') in ids else ids[0]
                elif mode=='winner':dealer=self.s.get('lastWinner') if self.s.get('lastWinner') in ids else ids[0]
                self.s.update(phase='playing', hand=self.s['hand']+1, dealer=dealer, turn=dealer, level=self.s['config']['minBet'], pot=0, round=1, acted=[], pending=None, result=None, bets=[], handActions=[], winnerSelection=None)
                for x in self.s['players']:
                    x.update(active=x in eligible,seen=False,spent=0,start=x['score'],ready=False)
                    if x['active']: self.charge(x,self.s['config']['ante'],'底注')
                self.log(f"第 {self.s['hand']} 局开始，庄家 {self.player(dealer)['name']} 首先行动，已收取每人 {self.s['config']['ante']} 分底注")
            elif a=='settle':
                if self.s['phase']!='showdown': fail('仅行动轮数用完后可强制摊牌结算，请由玩家自主比牌或弃牌')
                self.settle(d.get('id'),'房主确认摊牌')
            elif a=='resolve':
                if self.s['phase']!='comparing': fail('没有待确认的比牌')
                pending=self.s['pending']; winner=d.get('id')
                if winner not in (pending['actor'],pending['target']): fail('请选择比牌双方之一')
                loser=self.player(pending['target'] if winner==pending['actor'] else pending['actor']); loser['active']=False
                self.log(f"比牌结果：{self.player(winner)['name']} 胜，{loser['name']} 出局")
                self.s['pending']=None; self.s['winnerSelection']=None; self.s['phase']='playing'; self.advance(pending['actor'])
            elif a=='cancel':
                if self.s['phase'] not in ('playing','showdown','comparing'): fail('没有进行中的牌局')
                for x in self.s['players']: x['score']+=x['spent']; x['spent']=0; x['active']=False
                for x in self.s['players']: x['ready']=False
                self.s.update(phase='lobby',pot=0,turn=None,pending=None,result=None,bets=[],handActions=[],winnerSelection=None); self.log('房主撤销本局，所有投入已退回')
            elif a in ('remove','adjust','reset'):
                if a!='adjust' and self.s['phase'] not in ('lobby','finished'): fail('请在局间操作')
                if a=='reset':
                    for x in self.s['players']: x.update(score=self.s['config']['initial'],spent=0,active=False,ready=False,start=self.s['config']['initial'])
                    self.s.update(phase='lobby',result=None,bets=[]); self.log('全桌积分已重置')
                else:
                    q=self.player(d.get('id'))
                    if not q: fail('玩家不存在')
                    if a=='remove':
                        if q['id']==self.s.get('hostPlayer'): fail('不能移除房主玩家')
                        self.s['players'].remove(q)
                        if self.s['config'].get('designatedDealer')==q['id']:self.s['config']['designatedDealer']=''
                        self.log(f"房主移除了 {q['name']}")
                    else:
                        score=integer(d.get('score'),'积分',-1000000 if self.s['config'].get('allowNegative',0) else self.s['config']['floor'],1000000)
                        q['score']=score; q['ready']=bool(self.s['phase'] in BETWEEN and q.get('autoReady') and q['id']!=self.s.get('hostPlayer') and (self.s['config'].get('allowNegative',0) or score-self.s['config']['ante']>=self.s['config']['floor'])); self.log(f"房主将 {q['name']} 的积分设为 {score}")
            return {}
        if not p: fail('请先加入牌桌')
        if a=='seen':
            if self.s['phase']!='playing' or not p['active']: fail('当前不能看牌')
            if p['seen']: fail('已经看牌')
            p['seen']=True; self.record_action(p,'看牌'); self.log(f"{p['name']} 已看牌，之后投入按双倍计算"); return {}
        if self.s['phase']!='playing' or self.s['turn']!=p['id'] or not p['active']: fail('尚未轮到你行动')
        if a=='fold': p['active']=False; self.record_action(p,'弃牌'); self.log(f"{p['name']} 弃牌"); self.advance(p['id']); return {}
        if a not in ('call','raise','compare'): fail('未知操作')
        level=self.s['level']
        if a=='raise':
            c=self.s['config']
            if 'base' in c:
                base=c['base']; lower=(self.s['level']//base+1)*base
            else:lower=self.s['level']+max(1,(c['minRaise']+(1 if p['seen'] else 0))//(2 if p['seen'] else 1))
            level=integer(d.get('level'),'加注档位',lower,100000)
            if 'base' in c and level%c['base']:fail('加注档位必须为旧版起跟分的整数倍')
            if 'base' in c and level*2>c['maxBet']:fail('加注档位不能超过单次上限的一半')
        multiplier=2 if p['seen'] else 1
        amount=level*multiplier
        if a in ('call','compare'): amount=min(amount,self.s['config']['maxBet'])
        minimum=amount
        if a=='call' and 'amount' in d:
            amount=integer(d['amount'],'跟注积分',minimum,self.s['config']['maxBet'])
            if amount>minimum:
                if amount-minimum<self.s['config'].get('minRaise',0):fail('加注金额未达到最低跟注增量')
                level=max(level,(amount+multiplier-1)//multiplier)
        if amount>self.s['config']['maxBet']: fail('超过单次下注上限')
        if a=='compare':
            if self.s['round']<self.s['config']['minCompare']: fail('达到允许比牌轮数才能比牌')
            q=self.player(d.get('id'))
            if not q or q==p or not q['active']: fail('请选择另一位仍在场的玩家')
            if p['seen'] and not q['seen'] and not self.s['config'].get('allowBlindCompare',0): fail('当前规则明牌只能与已看牌玩家比牌')
            self.charge(p,amount,'比牌'); self.record_action(p,'比牌',amount); self.s['pending']=dict(actor=p['id'],target=q['id']); self.s['winnerSelection']=None; self.s['phase']='comparing'
            self.log(f"{p['name']} 投入 {amount} 分，与 {q['name']} 比牌，等待房主确认"); return {}
        self.charge(p,amount,'加注' if a=='raise' or amount>minimum else '跟注')
        self.record_action(p,'加注' if a=='raise' or amount>minimum else '跟注' if p['seen'] else '闷注',amount)
        self.s['level']=max(level,amount) if p['seen'] and self.s['config'].get('seenRaisesFloor',0) else level
        self.log(f"{p['name']} {'加注' if a=='raise' or amount>minimum else '跟注'} {amount} 分"); self.advance(p['id']); return {}

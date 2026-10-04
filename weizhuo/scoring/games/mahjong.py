"""Manual Mahjong scoring: no turns, readiness, bets or hand rules."""
import time
from .zhajinhua import Engine as RoomIdentityEngine, fresh as base_fresh, fail, integer


def validate_config(data):
    if not isinstance(data, dict):
        fail('设置格式不正确')
    enabled=data.get('poolEnabled',False)
    if not isinstance(enabled,bool):fail('奖金池设置不正确')
    return {'initial': integer(data.get('initial', 0), '初始积分', -1000000, 1000000), 'poolEnabled':enabled}


def fresh(code=None, config=None, name='自由积分桌'):
    s = base_fresh(code=code, name=name)
    s.update(game='mahjong', config=validate_config(config or {}), transactions=[])
    return s


class Engine(RoomIdentityEngine):
    def record(self, kind, actor, changes, note=''):
        rows = self.s.setdefault('transactions', [])
        rows.append(dict(seq=len(rows)+1, time=time.strftime('%H:%M:%S'), kind=kind,
                         actor=actor['name'], note=note,
                         changes=[dict(id=p['id'], name=p['name'], delta=delta)
                                  for p, delta in changes if delta]))

    def action(self, d):
        action = d.get('action')
        host, p = self.identity(d.get('token', ''))
        # Reuse room identity/membership operations, never poker actions.
        if action in ('join', 'hostSeat', 'leave', 'destroy', 'remove', 'rename', 'renameRoom'):
            result=super().action(d)
            if action in ('leave','remove'):
                ids={x['id'] for x in self.s['players']}
                for r in self.s.get('paymentRequests',[]):
                    if r['status']=='pending' and (r['requester'] not in ids or r['payer'] not in ids):r['status']='cancelled'
            return result
        if action == 'editScoringRules':
            if not host:fail('只有房主可以编辑记分规则')
            text=d.get('text')
            if not isinstance(text,str) or len(text)>2000:fail('记分规则最多 2000 个字')
            self.s['scoringRules']=text.strip()
            self.log('房主更新了记分规则')
            return {}
        if action in ('depositPool','allocatePool'):
            if not self.s['config'].get('poolEnabled',True):fail('本房间未启用奖金池')
            if not p:fail('请先加入房间')
            amount=integer(d.get('amount'),'积分',1,1000000)
            note=str(d.get('note','')).strip()
            if len(note)>60:fail('备注最多 60 个字')
            if action=='depositPool':
                p['score']-=amount;self.s['pot']+=amount
                self.record('押分到牌桌',p,[(p,-amount)],note)
                self.log(f"{p['name']} 向牌桌奖池投入 {amount} 分")
            else:
                if not host:fail('只有房主可以分配牌桌奖池')
                target=self.player(d.get('id'))
                if not target:fail('玩家已离开房间')
                if amount>self.s['pot']:fail('分配金额不能超过牌桌奖池')
                self.s['pot']-=amount;target['score']+=amount
                self.record('奖池分配',p,[(target,amount)],note)
                self.log(f"房主将牌桌奖池 {amount} 分分配给 {target['name']}")
            return {}
        if action in ('transferAll','requestTransferAll'):
            if not p:fail('请先加入房间')
            targets=[q for q in self.s['players'] if q['id']!=p['id']]
            ids=d.get('ids')
            if not targets:fail('请等待其他玩家加入')
            current={q['id'] for q in targets}
            roster=d.get('rosterIds',ids)
            if not isinstance(roster,list) or any(not isinstance(x,str) for x in roster) or len(roster)!=len(current) or set(roster)!=current:fail('房间成员已变化，请重新打开全场操作')
            if not isinstance(ids,list) or not ids or any(not isinstance(x,str) for x in ids) or len(set(ids))!=len(ids) or not set(ids)<=current:fail('请选择有效的其他玩家，不能重复或选择自己')
            targets=[q for q in targets if q['id'] in ids]
            amount=integer(d.get('amount'),'每人积分',1,1000000)
            note=str(d.get('note','')).strip()
            if len(note)>60:fail('备注最多 60 个字')
            if action=='transferAll':
                total=amount*len(targets);p['score']-=total
                for target in targets:target['score']+=amount
                self.record('全场赠送',p,[(p,-total)]+[(target,amount) for target in targets],note)
                self.log(f"{p['name']} 向其他 {len(targets)} 人各赠送 {amount} 分，合计 {total} 分")
                return {'message':f'已向 {len(targets)} 人各赠送 {amount} 分'}
            requests=self.s.setdefault('paymentRequests',[])
            if sum(q['status']=='pending' and q['requester']==p['id'] for q in requests)+len(targets)>max(10,len(self.s['players'])-1):fail('待确认收取过多，请先处理已有请求')
            import secrets
            batch=secrets.token_hex(8)
            for target in targets:requests.append(dict(id=secrets.token_hex(8),batch=batch,requester=p['id'],payer=target['id'],amount=amount,note=note,status='pending',time=time.strftime('%H:%M:%S')))
            self.s['paymentRequests']=[q for q in requests if q['status']=='pending']+[q for q in requests if q['status']!='pending'][-100:]
            self.log(f"{p['name']} 向其他 {len(targets)} 人各索取 {amount} 分，等待分别确认")
            return {'message':f'已向 {len(targets)} 人发出索取，等待分别确认'}
        if action == 'requestTransfer':
            if not p:fail('请先加入房间')
            target=self.player(d.get('id'))
            if not target or target['id']==p['id']:fail('请选择另一位在座玩家')
            amount=integer(d.get('amount'),'索取积分',1,1000000)
            note=str(d.get('note','')).strip()
            if len(note)>60:fail('备注最多 60 个字')
            requests=self.s.setdefault('paymentRequests',[])
            if sum(r['status']=='pending' and r['requester']==p['id'] for r in requests)>=max(10,len(self.s['players'])-1):fail('待确认收取过多，请先处理已有请求')
            import secrets
            requests.append(dict(id=secrets.token_hex(8),requester=p['id'],payer=target['id'],amount=amount,note=note,status='pending',time=time.strftime('%H:%M:%S')))
            self.s['paymentRequests']=[r for r in requests if r['status']=='pending']+[r for r in requests if r['status']!='pending'][-100:]
            self.log(f"{p['name']} 向 {target['name']} 索取 {amount} 分，等待对方确认")
            return {'message':'索取请求已发送，等待对方确认'}
        if action == 'resolveTransfer':
            if not p:fail('请先加入房间')
            request=next((r for r in self.s.get('paymentRequests',[]) if r['id']==d.get('requestIdToResolve')),None)
            if not request or request['status']!='pending':fail('索取请求已处理，请刷新查看')
            accepted=d.get('accepted')
            if not isinstance(accepted,bool):fail('确认状态不正确')
            if request['payer']!=p['id']:fail('只有被索取的玩家可确认给分')
            target=self.player(request['requester'])
            if not target:fail('索取者已离开房间')
            request['status']='accepted' if accepted else 'declined'
            if accepted:
                amount=request['amount'];p['score']-=amount;target['score']+=amount
                self.record('索取确认',p,[(p,-amount),(target,amount)],request['note'])
                self.log(f"{p['name']} 确认给 {target['name']} {amount} 分")
            else:self.log(f"{p['name']} 拒绝了 {target['name']} 的索取请求")
            return {}
        if action == 'cancelTransferRequest':
            if not p:fail('请先加入房间')
            request=next((r for r in self.s.get('paymentRequests',[]) if r['id']==d.get('requestIdToResolve')),None)
            if not request or request['status']!='pending' or request['requester']!=p['id']:fail('只能取消自己待确认的索取请求')
            request['status']='cancelled';return {}
        if action == 'transfer':
            if not p:
                fail('请先加入房间')
            target = self.player(d.get('id'))
            if not target or target['id'] == p['id']:
                fail('请选择另一位在座玩家')
            amount = integer(d.get('amount'), '给分', 1, 1000000)
            note = str(d.get('note', '')).strip()
            if len(note) > 60:
                fail('备注最多 60 个字')
            p['score'] -= amount
            target['score'] += amount
            self.record('给分', p, [(p, -amount), (target, amount)], note)
            self.log(f"{p['name']} 给 {target['name']} {amount} 分" + (f'（{note}）' if note else ''))
            return {}
        if action == 'seating':
            return super().action(d)
        if action in ('manualSettle', 'adjust', 'config'):
            if not host:
                fail('此操作需要房主权限')
            if action == 'config':
                data=d.get('config',{})
                if not isinstance(data,dict):fail('设置格式不正确')
                config=validate_config({**data,'poolEnabled':data.get('poolEnabled',self.s['config'].get('poolEnabled',True))})
                if not config['poolEnabled'] and self.s.get('pot',0):fail('请先分配完奖金池，再关闭奖金池')
                self.s['config'] = config
                self.log('房主更新了游戏设置，现有积分不变')
                return {}
            if action == 'adjust':
                target = self.player(d.get('id'))
                if not target:
                    fail('玩家不存在')
                score = integer(d.get('score'), '积分', -1000000, 1000000)
                delta = score - target['score']
                target['score'] = score
                self.record('改分', p or {'name': '房主'}, [(target, delta)])
                self.log(f"房主将 {target['name']} 的积分设为 {score}")
                return {}
            deltas = d.get('deltas')
            if not isinstance(deltas, dict) or set(deltas) != {x['id'] for x in self.s['players']}:
                fail('房间成员已变化，请重新打开结算')
            changes = [(x, integer(deltas[x['id']], '本次得失', -1000000, 1000000))
                       for x in self.s['players']]
            if sum(delta for _, delta in changes) != 0:
                fail('本次得失合计需要为 0，请核对输赢积分')
            if not any(delta for _, delta in changes):
                fail('请填写本次得失积分')
            note = str(d.get('note', '')).strip()
            if len(note) > 60:
                fail('备注最多 60 个字')
            for target, delta in changes:
                target['score'] += delta
            self.record('结算', p or {'name': '房主'}, changes, note)
            self.log('房主录入结算：' + '，'.join(f"{x['name']} {v:+d} 分" for x, v in changes if v)
                     + (f'（{note}）' if note else ''))
            return {}
        fail('自由记分房间仅支持随时给分和手动结算')

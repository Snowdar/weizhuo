"""Offline no-limit Hold'em ledger and dealer workflow; no virtual cards."""
import time
from .zhajinhua import Engine as IdentityEngine, fresh as base_fresh, fail, integer, BETWEEN

DEFAULT = dict(initial=1000, smallBlind=5, bigBlind=10, ante=0)
STREETS = ('preflop', 'flop', 'turn', 'river')
STREET_NAMES = dict(preflop='翻牌前', flop='翻牌', turn='转牌', river='河牌')


def validate_config(data):
    if not isinstance(data, dict):
        fail('规则格式不正确')
    c = {k: integer(data.get(k, v), k, 0 if k == 'ante' else 1, 1000000)
         for k, v in DEFAULT.items()}
    if c['smallBlind'] > c['bigBlind']:
        fail('小盲不能高于大盲')
    return c


def fresh(code=None, config=None, name='朋友的德州扑克桌'):
    s = base_fresh(code=code, name=name)
    s.update(game='holdem', config=validate_config(config or {}), street='preflop',
             currentBet=0, lastRaise=0, actedAt={}, facilitator=None,
             smallBlindPlayer=None, bigBlindPlayer=None, pots=[], dealPending=None,
             returns=[], lastAggressor=None, showFirst=None, nextPlayerNumber=1, winnerSelection=None)
    return s


class Engine(IdentityEngine):
    def __init__(self, state):
        super().__init__(state)
        self.ensure_player_numbers()

    def ensure_player_numbers(self):
        used = set()
        next_number = max(self.s.get('nextPlayerNumber', 1), max((p.get('playerNumber', 0) for p in self.s['players']), default=0)+1)
        for player in self.s['players']:
            number = player.get('playerNumber')
            if not isinstance(number, int) or number < 1 or number in used:
                number = next_number
                next_number += 1
                player['playerNumber'] = number
            used.add(number)
        self.s['nextPlayerNumber'] = next_number

    def controller(self, token):
        host, player = self.identity(token)
        return host or bool(player and player['id'] == self.s.get('facilitator'))

    def order_after(self, pid):
        ids = [p['id'] for p in self.s['players']]
        index = ids.index(pid) if pid in ids else -1
        return [self.player(ids[(index + n) % len(ids)]) for n in range(1, len(ids)+1)]

    def contenders(self):
        return [p for p in self.s['players'] if p['active']]

    def bettors(self):
        return [p for p in self.contenders() if p['score'] > 0]

    def can_raise(self, p):
        previous = self.s['actedAt'].get(p['id'])
        return (len(self.bettors()) >= 2 and
                (previous is None or self.s['currentBet'] - previous >= self.s['lastRaise']))

    def options(self, p):
        due = max(0, self.s['currentBet'] - p.get('streetSpent', 0))
        minimum = self.s['currentBet'] + self.s['lastRaise']
        maximum = p.get('streetSpent', 0) + p['score']
        return dict(toCall=min(due, p['score']), callDue=due, minRaiseTo=minimum,
                    maxRaiseTo=maximum, canCheck=due == 0,
                    canRaise=self.can_raise(p) and maximum > self.s['currentBet'],
                    canAllIn=maximum <= self.s['currentBet'] or self.can_raise(p))

    def charge(self, p, amount, kind='投入', street=True):
        if amount < 0 or amount > p['score']:
            fail('投入超过当前剩余积分')
        p['score'] -= amount
        p['spent'] += amount
        if street:
            p['streetSpent'] = p.get('streetSpent', 0) + amount
        p['allIn'] = p['score'] == 0
        self.s['pot'] += amount
        if amount:
            self.s['bets'].append(dict(seq=len(self.s['bets'])+1, playerId=p['id'],
                playerName=p['name'], amount=amount, kind=kind, street=self.s['street'],
                time=time.strftime('%H:%M:%S')))

    def refund_uncalled(self):
        # Only a unique largest *live* contribution may be returned. Folded
        # money stays in the pot, including chips above a short stack's cap.
        ranked = sorted(self.s['players'], key=lambda p: p['spent'], reverse=True)
        if not ranked or not ranked[0]['active']:
            return
        p = ranked[0]
        second = ranked[1]['spent'] if len(ranked) > 1 else 0
        amount = p['spent'] - second
        if amount <= 0:
            return
        p['score'] += amount; p['spent'] -= amount
        p['streetSpent'] = max(0, p.get('streetSpent', 0) - amount)
        p['allIn'] = p['score'] == 0
        self.s['pot'] -= amount
        self.s['returns'].append(dict(playerId=p['id'], name=p['name'], amount=amount))
        self.s['bets'].append(dict(seq=len(self.s['bets'])+1, playerId=p['id'],
            playerName=p['name'], amount=-amount, kind='退还未跟注',
            street=self.s['street'], time=time.strftime('%H:%M:%S')))
        self.log(f"{p['name']} 无人跟注的 {amount} 分已退还")

    def build_pots(self):
        levels = sorted({p['spent'] for p in self.s['players'] if p['spent'] > 0})
        pots, previous = [], 0
        for level in levels:
            contributors = [p for p in self.s['players'] if p['spent'] >= level]
            amount = (level - previous) * len(contributors)
            eligible = [p['id'] for p in contributors if p['active']]
            if not eligible and pots:
                # Folded dead chips never form an unwinnable side pot.
                pots[-1]['amount'] += amount
            elif amount:
                pots.append(dict(id=str(len(pots)), amount=amount, cap=level, eligible=eligible))
            previous = level
        return pots

    def finish(self, awards, reason):
        total = self.s['pot']
        if sum(a['amount'] for a in awards) != total:
            fail('派奖金额与奖池不一致')
        for award in awards:
            self.player(award['playerId'])['score'] += award['amount']
        self.s['result'] = dict(amount=total, reason=reason, awards=awards,
            pots=self.s['pots'], returns=list(self.s['returns']), bets=list(self.s['bets']),
            scores=[dict(id=p['id'], name=p['name'], delta=p['score']-p['start']) for p in self.s['players']])
        self.s.update(phase='finished', turn=None, pot=0, dealPending=None, winnerSelection=None)
        for p in self.s['players']:
            p['ready'] = bool(p.get('autoReady') and p['score'] > 0 and p['id'] != self.s.get('hostPlayer'))
        self.log(f"第 {self.s['hand']} 局已结算：{reason}，合计派奖 {total} 分")

    def after_action(self, actor=None):
        if len(self.contenders()) == 1:
            self.refund_uncalled()
            winner = self.contenders()[0]
            self.s['pots'] = [dict(id='0', amount=self.s['pot'], eligible=[winner['id']])]
            self.finish([dict(playerId=winner['id'], name=winner['name'], amount=self.s['pot'], potId='0')], '其他玩家全部弃牌')
            return
        bettors = self.bettors()
        needed = [p for p in bettors if p['id'] not in self.s['actedAt'] or p['streetSpent'] < self.s['currentBet']]
        # A lone player with chips need only respond to an outstanding wager;
        # they cannot bet into an empty side pot against all-in opponents.
        if len(bettors) <= 1:
            if bettors:
                opponent_bet = max((p.get('streetSpent', 0) for p in self.contenders() if p is not bettors[0]), default=0)
                self.s['currentBet'] = min(self.s['currentBet'], opponent_bet)
            needed = [p for p in bettors if p['streetSpent'] < self.s['currentBet']]
        if needed:
            order = self.order_after(actor if actor else self.s['bigBlindPlayer'] if self.s['street']=='preflop' else self.s['dealer'])
            if not actor and self.s['street']=='preflop' and len(self.s['players'])==2:
                order = [self.player(self.s['dealer'])] + order
            self.s['turn'] = next(p['id'] for p in order if p in needed)
            return
        self.refund_uncalled()
        self.s['turn'] = None
        self.s['pots'] = self.build_pots()
        if self.s['street'] == 'river':
            self.s['phase'] = 'showdown'
            self.s['winnerSelection'] = dict(activePot=self.s['pots'][0]['id'], winners={p['id']: list(p['eligible']) if len(p['eligible']) == 1 else [] for p in self.s['pots']})
            self.s['showFirst'] = self.s.get('lastAggressor') or next(p['id'] for p in self.order_after(self.s['dealer']) if p['active'])
            self.log('河牌行动已完成，请摊牌并逐池确认赢家；平牌可多选')
        else:
            self.s['phase'] = 'dealing'
            self.s['dealPending'] = STREETS[STREETS.index(self.s['street'])+1]
            self.log('本轮行动完成，请庄家烧一张牌并发'+STREET_NAMES[self.s['dealPending']])
            if len(self.bettors()) <= 1:
                self.log('已无后续下注，请剩余玩家亮牌，依次发完公共牌')

    def start(self):
        if self.s['phase'] not in BETWEEN:
            fail('已有进行中的牌局')
        players = self.s['players']
        if len(players) < 2 or not all((p['id']==self.s.get('hostPlayer') or p['ready']) and p['score'] > 0 for p in players):
            fail('至少两位有积分的玩家，且其他玩家准备后才能开始')
        # Rotate the big blind; with a stable table this rotates the button.
        # On transition to heads-up this prevents the same player paying BB twice.
        old_bb = self.s.get('bigBlindPlayer')
        if self.s.get('nextDealer') and self.player(self.s['nextDealer']):
            button = self.player(self.s.pop('nextDealer'))
            bb = self.order_after(button['id'])[0 if len(players)==2 else 1]
        elif self.s['hand'] and old_bb:
            bb = next(p for p in self.order_after(old_bb) if p in players)
            bb_index = players.index(bb)
            button = players[(bb_index-(1 if len(players)==2 else 2)) % len(players)]
        else:
            button = players[0]
            bb = self.order_after(button['id'])[0 if len(players)==2 else 1]
        sb = button if len(players)==2 else self.order_after(button['id'])[0]
        self.s.update(phase='dealing', hand=self.s['hand']+1, dealer=button['id'],
            smallBlindPlayer=sb['id'], bigBlindPlayer=bb['id'], street='preflop',
            currentBet=self.s['config']['bigBlind'], lastRaise=self.s['config']['bigBlind'],
            turn=None, actedAt={}, bets=[], handActions=[], result=None, pot=0, pots=[], returns=[], winnerSelection=None,
            lastAggressor=None, showFirst=None, dealPending='hole')
        for p in players:
            p.update(start=p['score'], spent=0, streetSpent=0, active=True, ready=False, seen=False, allIn=False)
            self.charge(p, min(p['score'], self.s['config']['ante']), '前注', street=False)
        self.charge(sb, min(sb['score'], self.s['config']['smallBlind']), '小盲')
        self.charge(bb, min(bb['score'], self.s['config']['bigBlind']), '大盲')
        self.log(f"第 {self.s['hand']} 局开始，按钮庄位 {button['name']}，小盲 {sb['name']}，大盲 {bb['name']}；请每人发两张底牌")

    def action(self, d):
        action = d.get('action')
        host, p = self.identity(d.get('token', ''))
        controller = self.controller(d.get('token', ''))
        between = self.s['phase'] in BETWEEN
        if action in ('join', 'hostSeat', 'leave', 'destroy', 'remove', 'rename', 'renameRoom'):
            result = super().action(d)
            self.ensure_player_numbers()
            if self.s.get('facilitator') not in {player['id'] for player in self.s['players']}:
                self.s['facilitator'] = None
            return result
        if action in ('config', 'adjust', 'seating', 'assignFacilitator', 'setDealer'):
            if not host:
                fail('此操作需要房主权限')
            if not between:
                fail('请在局间调整，避免改变本局筹码和下注规则')
            if action == 'config':
                self.s['config'] = validate_config(d.get('config', {}))
            elif action == 'adjust':
                target = self.player(d.get('id'))
                if not target:
                    fail('玩家不存在')
                target['score'] = integer(d.get('score'), '积分', 0, 1000000)
            elif action == 'setDealer':
                target = self.player(d.get('id'))
                if not target:
                    fail('请选择在座的按钮庄家')
                self.s['nextDealer'] = target['id']
                self.log('下一局按钮庄位指定为 '+target['name'])
            elif action == 'assignFacilitator':
                target = self.player(d.get('id'))
                if not target:
                    fail('请选择在座的发牌协助者')
                self.s['facilitator'] = target['id']
                self.log(target['name']+' 担任发牌协助者，也可正常参与牌局')
            else:
                ids = d.get('ids')
                if not isinstance(ids,list) or len(ids)!=len(self.s['players']) or any(not isinstance(x,str) for x in ids) or set(ids)!={p['id'] for p in self.s['players']}:
                    fail('座位名单已变化，请重新调整')
                self.s['players'] = [self.player(pid) for pid in ids]
            for player in self.s['players']:
                if action == 'adjust' and player['id'] != target['id']:
                    continue
                player['ready'] = bool(player.get('autoReady') and player['score'] > 0 and player['id'] != self.s.get('hostPlayer'))
            self.log('房主调整了积分' if action == 'adjust' else '房主更新了局间设置，自动准备玩家按资格准备')
            return {}
        if action == 'selectWinner':
            if not controller:
                fail('只有房主或发牌协助者可以选择赢家')
            if self.s['phase'] != 'showdown':
                fail('请在摊牌阶段选择赢家')
            pot = next((p for p in self.s['pots'] if p['id'] == d.get('potId')), None)
            if not pot:
                fail('奖池不存在')
            selection = self.s.get('winnerSelection') or dict(activePot=pot['id'], winners={p['id']: list(p['eligible']) if len(p['eligible']) == 1 else [] for p in self.s['pots']})
            if 'id' in d:
                pid, selected = d['id'], d.get('selected')
                if not isinstance(selected, bool) or pid not in pot['eligible']:
                    fail('只能选择有资格争夺该奖池的玩家')
                ids = selection['winners'][pot['id']]
                selection['winners'][pot['id']] = [x for x in ids if x != pid] + ([pid] if selected else [])
            selection['activePot'] = pot['id']
            self.s['winnerSelection'] = selection
            return {}
        if action == 'autoReady':
            if not p or p['id'] == self.s.get('hostPlayer'):
                fail('自动准备仅供非房主玩家使用')
            enabled = d.get('enabled')
            if not isinstance(enabled, bool):
                fail('自动准备设置不正确')
            p['autoReady'] = enabled
            if between:
                p['ready'] = enabled and p['score'] > 0
            self.log(p['name']+(' 开启自动准备' if enabled else ' 关闭自动准备'))
            return {}
        if action == 'ready':
            if not p or not between:
                fail('请在局间入座后准备')
            ready = d.get('ready', not p['ready'])
            if not isinstance(ready, bool):
                fail('准备状态不正确')
            if ready and p['score'] <= 0:
                fail('积分为零，请先在局间补充积分')
            p['ready'] = ready
            if not ready:
                p['autoReady'] = False
            self.log(p['name']+(' 已准备' if ready else ' 取消准备'))
            return {}
        if action in ('start', 'deal', 'settle', 'actFor', 'cancel'):
            if not controller:
                fail('请由房主或发牌协助者确认')
            if action == 'start':
                self.start()
            elif action == 'actFor':
                target = self.player(d.get('id'))
                if not target or target['id'] != self.s['turn']:
                    fail('只能代记当前行动玩家的操作')
                move = d.get('move')
                if move not in ('check','call','raise','bet','allIn','fold'):
                    fail('不支持的代记动作')
                self.action(dict(action=move, token=target['token'], amount=d.get('amount')))
                self.log('发牌协助者代记 '+target['name']+' 的行动')
            elif action == 'deal':
                if self.s['phase'] != 'dealing':
                    fail('当前没有待确认的发牌，请等待本轮行动结束')
                street = self.s['dealPending']
                if d.get('stage') != street:
                    fail('发牌阶段已变化，请按当前提示确认')
                if street != 'hole':
                    self.s.update(street=street, currentBet=0, lastRaise=self.s['config']['bigBlind'], actedAt={}, lastAggressor=None)
                    for player in self.s['players']:
                        player['streetSpent'] = 0
                self.s.update(phase='playing', dealPending=None)
                self.log('底牌已发好' if street=='hole' else STREET_NAMES[street]+'已发好')
                self.after_action()
            elif action == 'cancel':
                if between:
                    fail('没有进行中的牌局')
                for player in self.s['players']:
                    player.update(score=player['score']+player['spent'], spent=0, streetSpent=0, active=False, ready=False, allIn=False)
                self.s.update(phase='lobby', pot=0, turn=None, dealPending=None, result=None, pots=[], bets=[], returns=[], actedAt={}, winnerSelection=None)
                self.s['handActions']=[]
                self.log('本局撤销，净投入全部退还')
            else:
                if self.s['phase'] != 'showdown':
                    fail('请完成河牌行动后逐池结算')
                self.s['pots'] = self.build_pots()
                winners = d.get('winners')
                if not isinstance(winners, dict) or set(winners) != {pot['id'] for pot in self.s['pots']}:
                    fail('请为每个主池与边池选择赢家')
                awards = []
                for pot in self.s['pots']:
                    ids = winners[pot['id']]
                    if not isinstance(ids, list) or not ids or any(not isinstance(pid,str) for pid in ids) or len(set(ids))!=len(ids) or not set(ids)<=set(pot['eligible']):
                        fail('赢家须为有资格争夺该池的玩家；平牌可多选')
                    if self.s.get('winnerSelection') and self.s['winnerSelection']['winners'].get(pot['id']) and set(ids) != set(self.s['winnerSelection']['winners'][pot['id']]):
                        fail('赢家选择已更新，请核对牌桌后结算')
                    ordered = [player for player in self.order_after(self.s['dealer']) if player['id'] in ids]
                    share, odd = divmod(pot['amount'], len(ids))
                    for i, player in enumerate(ordered):
                        awards.append(dict(playerId=player['id'], name=player['name'], amount=share+(i<odd), potId=pot['id']))
                self.finish(awards, '线下核对手牌，逐池派奖')
            return {}
        if action not in ('check','call','raise','bet','allIn','fold'):
            fail('德州扑克不支持此操作')
        if not p or self.s['phase']!='playing' or self.s['turn']!=p['id'] or not p['active'] or p['score']<=0:
            fail('尚未轮到你行动')
        due = self.s['currentBet'] - p['streetSpent']
        if action == 'fold':
            p['active'] = False
            self.record_action(p,'弃牌')
            self.log(p['name']+' 弃牌')
        elif action == 'check':
            if due:
                fail('仍需跟注，不能过牌')
            self.s['actedAt'][p['id']] = self.s['currentBet']
            self.record_action(p,'过牌')
            self.log(p['name']+' 过牌')
        elif action == 'call':
            if due <= 0:
                fail('无需跟注，请过牌或下注')
            self.charge(p, min(due, p['score']), '全下跟注' if due>=p['score'] else '跟注')
            self.s['actedAt'][p['id']] = self.s['currentBet']
            self.record_action(p,self.s['bets'][-1]['kind'],self.s['bets'][-1]['amount'])
            self.log(p['name']+' 跟注'+('并全下' if p['allIn'] else ''))
        else:
            target = p['streetSpent']+p['score'] if action=='allIn' else integer(d.get('amount'), '本轮加到', 1, 2000000)
            added = target - p['streetSpent']
            if added<=0 or added>p['score']:
                fail('本轮总投入超过剩余积分')
            old = self.s['currentBet']
            if target <= old:
                if action!='allIn':
                    fail('加注必须高于当前本轮下注额')
                self.charge(p, added, '全下跟注')
            else:
                if not self.can_raise(p):
                    fail('短额全下未重新开放加注，或其他玩家已全下；只能跟注或弃牌')
                increment = target-old
                if increment<self.s['lastRaise'] and added!=p['score']:
                    fail('加注不足最小增量；不足时仅允许全下')
                self.charge(p, added, '全下' if added==p['score'] else '下注' if old==0 else '加注')
                self.s['currentBet'] = target
                if increment>=self.s['lastRaise']:
                    self.s['lastRaise'] = increment
                self.s['lastAggressor'] = p['id']
            self.s['actedAt'][p['id']] = self.s['currentBet']
            self.record_action(p,self.s['bets'][-1]['kind'],added)
            self.log(f"{p['name']} 本轮投入到 {target} 分"+(' · 全下' if p['allIn'] else ''))
        self.after_action(p['id'])
        return {}

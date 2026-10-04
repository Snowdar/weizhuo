"""Hold'em regression: real betting rules, dealer flow and atomic persistence."""
from pathlib import Path
import json,tempfile,unittest
from scoring.games.holdem import Engine,validate_config
from scoring.repository import Repository
from scoring.rooms import Rooms

class HoldemTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'rooms.sqlite3';self.rooms=Rooms(Repository(self.path));self.create()
    def create(self,count=3,**config):
        out=self.rooms.create(dict(game='holdem',name='测试桌',nickname='A',config=config));self.code=out['room'];self.host=out['token'];self.tokens=[self.host]
        for i in range(1,count):self.tokens.append(self.rooms.execute(self.code,dict(action='join',name=chr(65+i)))['token'])
        self.ids=[p['id'] for p in self.state()['players']]
    def state(self):return self.rooms.repo.get(self.code)
    def do(self,action,token=None,**data):return self.rooms.execute(self.code,dict(action=action,token=token or self.host,expectedVersion=self.state()['version'],**data))
    def start(self):
        for t in self.tokens:self.do('ready',token=t,ready=True)
        self.do('start');self.assertEqual(self.state()['phase'],'dealing');self.do('deal',stage='hole')
    def passive(self):
        for _ in range(30):
            s=self.state()
            if s['phase']!='playing':return
            p=next(p for p in s['players'] if p['id']==s['turn']);t=self.host if p['id']==s['hostPlayer'] else p['token']
            self.do('call' if p['streetSpent']<s['currentBet'] else 'check',token=t)
        self.fail('轮次未结束')
    def runout(self):
        for _ in range(10):
            s=self.state()
            if s['phase']=='showdown':return
            if s['phase']=='dealing':self.do('deal',stage=s['dealPending'])
            elif s['phase']=='playing':self.passive()
            else:self.fail('意外状态')
        self.fail('未摊牌')
    def stacks(self,values):
        for pid,value in zip(self.ids,values):self.do('adjust',id=pid,score=value)
    def conserved(self,total=3000):
        s=self.state();self.assertEqual(sum(p['score'] for p in s['players'])+s['pot'],total)
    def test_player_numbers_survive_seating_recovery_and_departures(self):
        original={p['id']:p['playerNumber'] for p in self.state()['players']}
        self.assertEqual(sorted(original.values()),[1,2,3])
        self.do('seating',ids=self.ids[::-1])
        self.assertEqual({p['id']:p['playerNumber'] for p in self.state()['players']},original)
        recovered=Rooms(Repository(self.path)).public(self.code,self.host,'')
        self.assertEqual({p['id']:p['playerNumber'] for p in recovered['players']},original)
        self.do('remove',id=self.ids[2])
        self.rooms.execute(self.code,dict(action='join',name='New'))
        self.assertEqual(self.state()['players'][-1]['playerNumber'],4)

    def test_legacy_player_numbers_are_assigned_before_seat_changes(self):
        legacy=self.state()
        legacy.pop('nextPlayerNumber',None)
        for p in legacy['players']:p.pop('playerNumber',None)
        self.rooms.repo.save(legacy)
        self.do('seating',ids=self.ids[::-1])
        self.assertEqual([p['playerNumber'] for p in self.state()['players']],[3,2,1])

    def test_host_starts_without_ready_but_guests_must_be_ready(self):
        with self.assertRaises(ValueError):self.do('start')
        for t in self.tokens[1:]:self.do('ready',token=t,ready=True)
        self.assertFalse(self.state()['players'][0]['ready'])
        self.do('start');self.assertEqual(self.state()['phase'],'dealing')

    def test_next_dealer_is_host_only_between_hands_and_one_shot(self):
        with self.assertRaises(ValueError):self.do('setDealer',token=self.tokens[1],id=self.ids[2])
        with self.assertRaises(ValueError):self.do('setDealer',id='missing')
        self.do('setDealer',id=self.ids[2]);self.start()
        self.assertEqual(self.state()['dealer'],self.ids[2])
        self.assertNotIn('nextDealer',self.state())
        with self.assertRaises(ValueError):self.do('setDealer',id=self.ids[1])
        self.do('cancel');self.start();self.assertEqual(self.state()['dealer'],self.ids[0])

    def test_positions_blind_option_and_explicit_deal(self):
        self.start();s=self.state();self.assertEqual([s['dealer'],s['smallBlindPlayer'],s['bigBlindPlayer'],s['turn']],self.ids+[self.ids[0]])
        self.assertEqual([p['streetSpent'] for p in s['players']],[0,5,10])
        with self.assertRaises(ValueError):self.do('check')
        with self.assertRaises(ValueError):self.do('call',token=self.tokens[1])
        self.do('call');self.do('call',token=self.tokens[1]);self.assertEqual(self.state()['turn'],self.ids[2]);self.do('check',token=self.tokens[2])
        self.assertEqual(self.state()['dealPending'],'flop')
        with self.assertRaises(ValueError):self.do('deal',stage='turn')
        with self.assertRaises(ValueError):self.do('deal',stage='flop',token=self.tokens[1])
        self.do('deal',stage='flop');self.assertEqual(self.state()['turn'],self.ids[1]);self.conserved()
    def test_heads_up_and_button_rotation(self):
        self.create(2);self.start();s=self.state();self.assertEqual([s['dealer'],s['smallBlindPlayer'],s['turn']],[self.ids[0]]*3)
        self.passive();self.do('deal',stage='flop');self.assertEqual(self.state()['turn'],self.ids[1]);self.runout();self.do('settle',winners={'0':[self.ids[0]]})
        self.start();self.assertEqual(self.state()['dealer'],self.ids[1]);self.assertEqual(self.state()['bigBlindPlayer'],self.ids[0])
    def test_big_blind_not_repeated_when_table_becomes_heads_up(self):
        self.start();self.do('fold');self.do('fold',token=self.tokens[1]);self.do('remove',id=self.ids[1]);self.tokens=[self.tokens[0],self.tokens[2]];self.start()
        self.assertEqual(self.state()['bigBlindPlayer'],self.ids[0]);self.assertEqual(self.state()['dealer'],self.ids[2])
    def test_raise_minimum_and_repeat_response(self):
        self.start();self.do('raise',amount=30);self.assertEqual(self.state()['lastRaise'],20);before=self.state()
        with self.assertRaises(ValueError):self.do('raise',token=self.tokens[1],amount=40)
        self.assertEqual(self.state(),before);self.do('raise',token=self.tokens[1],amount=50);self.do('call',token=self.tokens[2]);self.assertEqual(self.state()['turn'],self.ids[0]);self.do('call');self.conserved()
    def test_short_all_in_reopening_is_per_player(self):
        self.stacks([1000,15,1000]);self.start();self.do('call');self.do('allIn',token=self.tokens[1]);s=self.state();e=Engine(s)
        self.assertFalse(e.can_raise(e.player(self.ids[0])));self.assertTrue(e.can_raise(e.player(self.ids[2])));self.do('call',token=self.tokens[2])
        with self.assertRaises(ValueError):self.do('raise',amount=25)
        with self.assertRaises(ValueError):self.do('allIn')
        self.do('call');self.assertEqual(self.state()['phase'],'dealing');self.conserved(2015)
    def test_cumulative_short_all_ins_reopen_only_full_amount(self):
        self.create(5);self.start();self.passive();self.do('deal',stage='flop')
        s=self.state();s['players'][2]['score']=125;s['players'][4]['score']=200;self.rooms.repo.save(s)
        self.do('bet',token=self.tokens[1],amount=100);self.do('allIn',token=self.tokens[2]);self.do('call',token=self.tokens[3]);self.do('allIn',token=self.tokens[4]);self.do('call');s=self.state();e=Engine(s)
        self.assertTrue(e.can_raise(e.player(self.ids[1])));self.assertFalse(e.can_raise(e.player(self.ids[3])));self.do('call',token=self.tokens[1])
        with self.assertRaises(ValueError):self.do('raise',token=self.tokens[3],amount=300)
        self.do('call',token=self.tokens[3]);self.assertEqual(self.state()['phase'],'dealing')
    def test_incomplete_opening_keeps_minimum_and_prior_check_rights(self):
        self.start();self.passive();self.do('deal',stage='flop');self.do('check',token=self.tokens[1]);s=self.state();s['players'][2]['score']=4;self.rooms.repo.save(s)
        self.do('allIn',token=self.tokens[2]);s=self.state();e=Engine(s);self.assertEqual(e.options(e.player(self.ids[0]))['minRaiseTo'],14);self.assertFalse(e.can_raise(e.player(self.ids[1])))
        self.do('raise',amount=14);self.assertEqual(self.state()['lastRaise'],10);self.assertTrue(Engine(self.state()).can_raise(self.state()['players'][1]))
    def test_side_pots_and_atomic_eligibility_validation(self):
        self.stacks([50,100,200]);self.start();self.do('allIn');self.do('allIn',token=self.tokens[1]);self.do('call',token=self.tokens[2]);self.conserved(350);self.runout();s=self.state()
        self.assertEqual([p['amount'] for p in s['pots']],[150,100]);self.assertEqual(s['pots'][1]['eligible'],self.ids[1:])
        with self.assertRaises(ValueError):self.do('settle',winners={'0':[self.ids[0]],'1':[self.ids[0]]})
        self.assertEqual(self.state(),s);self.do('settle',winners={'0':[self.ids[0]],'1':[self.ids[1]]});self.assertEqual([p['score'] for p in self.state()['players']],[150,100,100]);self.conserved(350);self.assertEqual(len(self.rooms.repo.histories(self.code)),1)
    def test_three_pots_and_no_dry_side_betting(self):
        self.create(4);self.stacks([10,40,100,200]);self.start();self.do('allIn',token=self.tokens[3]);self.do('allIn');self.do('allIn',token=self.tokens[1]);self.do('allIn',token=self.tokens[2]);s=self.state()
        self.assertEqual(s['players'][3]['score'],100);self.assertEqual(s['returns'][0]['amount'],100);self.assertEqual([p['amount'] for p in s['pots']],[40,90,120]);self.conserved(350)
        self.do('deal',stage='flop');self.assertEqual(self.state()['phase'],'dealing');self.assertIsNone(self.state()['turn']);self.runout();self.do('settle',winners={'0':[self.ids[0]],'1':[self.ids[1]],'2':[self.ids[2]]});self.conserved(350)
    def test_short_big_blind_requires_full_nominal_call(self):
        self.stacks([100,100,3]);self.start();self.assertEqual(self.state()['currentBet'],10);self.assertEqual(self.rooms.public(self.code,self.host,'')['actionOptions']['toCall'],10);self.passive();self.conserved(203)
    def test_heads_up_short_blind_does_not_require_dry_side_call(self):
        self.create(2);self.stacks([100,3]);self.start();s=self.state()
        self.assertEqual(s['phase'],'dealing');self.assertEqual(s['dealPending'],'flop')
        self.assertIsNone(s['turn']);self.assertEqual(s['pot'],6)
        self.assertEqual(s['players'][0]['score'],97);self.runout();self.conserved(103)
    def test_fold_win_refunds_unmatched_chips(self):
        self.start();self.do('raise',amount=200);self.do('fold',token=self.tokens[1]);self.do('fold',token=self.tokens[2]);s=self.state()
        self.assertEqual(s['phase'],'finished');self.assertEqual(s['result']['returns'][0]['amount'],190);self.assertEqual(s['result']['amount'],25);self.assertEqual([p['score'] for p in s['players']],[1015,995,990]);self.conserved()
    def test_folded_dead_money_cannot_win_or_be_refunded(self):
        s=self.state()
        for p,spent,active in zip(s['players'],[100,40,40],[False,True,True]):p.update(spent=spent,score=1000-spent,active=active)
        s.update(pot=180,phase='showdown',street='river');e=Engine(s);e.refund_uncalled();self.assertEqual(s['pot'],180);self.assertEqual(e.build_pots(),[dict(id='0',amount=180,cap=40,eligible=self.ids[1:])])
    def test_tie_odd_chip_left_of_button(self):
        self.create(3,ante=1);self.start();self.runout();self.assertEqual(self.state()['pot'],33);self.do('settle',winners={'0':[self.ids[2],self.ids[1]]});awards=self.state()['result']['awards']
        self.assertEqual([(a['playerId'],a['amount']) for a in awards],[(self.ids[1],17),(self.ids[2],16)]);self.conserved()
    def test_facilitator_plays_and_delegates_but_cannot_manage(self):
        self.do('assignFacilitator',id=self.ids[1]);self.start()
        with self.assertRaises(ValueError):self.do('actFor',token=self.tokens[2],id=self.ids[0],move='call')
        with self.assertRaises(ValueError):self.do('actFor',token=self.tokens[1],id=self.ids[2],move='call')
        self.do('actFor',token=self.tokens[1],id=self.ids[0],move='call');self.do('call',token=self.tokens[1]);self.do('check',token=self.tokens[2]);self.do('deal',token=self.tokens[1],stage='flop')
        with self.assertRaises(ValueError):self.do('config',token=self.tokens[1],config={})
        self.runout();self.do('settle',token=self.tokens[1],winners={'0':[self.ids[1]]});self.conserved()
    def test_undo_restores_chips_stages_and_settlement_history(self):
        self.start();before=self.state();self.do('call');self.do('undo');after=self.state();self.assertEqual(after['players'],before['players']);self.assertEqual(after['pot'],before['pot']);self.assertEqual(after['turn'],before['turn'])
        self.runout();before=self.state();self.do('settle',winners={'0':[self.ids[0]]});self.do('undo');self.assertEqual(self.state()['phase'],'showdown');self.assertEqual(self.state()['pot'],before['pot']);self.assertEqual(self.rooms.repo.histories(self.code),[]);self.conserved()
        self.do('cancel');self.assertEqual(self.state()['phase'],'lobby');self.conserved();self.do('undo');self.assertEqual(self.state()['phase'],'showdown');self.conserved()
    def test_deal_undo_dedup_and_stale_version(self):
        self.start();self.passive();before=self.state();payload=dict(action='deal',token=self.host,stage='flop',expectedVersion=before['version'],requestId='one');self.rooms.execute(self.code,payload);after=self.state();self.rooms.execute(self.code,payload);self.assertEqual(self.state(),after)
        with self.assertRaises(ValueError):self.rooms.execute(self.code,{**payload,'requestId':'two'})
        self.do('undo');self.assertEqual(self.state()['phase'],'dealing');self.assertEqual(self.state()['dealPending'],'flop')
    def test_restart_device_recovery_and_no_private_tokens(self):
        self.do('assignFacilitator',id=self.ids[1]);self.start();self.do('raise',amount=30);saved=self.state();restored=Rooms(Repository(self.path));self.assertEqual(restored.room(self.code),saved)
        secret='a'*40;restored.device_rooms(secret,[dict(room=self.code,token=self.tokens[1])]);self.assertEqual(restored.device_rooms(secret)[0]['room'],self.code);public=restored.public(self.code,self.tokens[1],'invite');self.assertTrue(public['isController']);raw=json.dumps(public)
        for t in self.tokens:self.assertNotIn(t,raw)
        self.assertEqual(restored.repo.active_count(),1)
    def test_stack_freeze_zero_ready_and_invalid_config(self):
        self.start()
        for a,d in [('adjust',dict(id=self.ids[0],score=100)),('config',dict(config={})),('seating',dict(ids=self.ids))]:
            with self.assertRaises(ValueError):self.do(a,**d)
        self.do('cancel');self.do('adjust',id=self.ids[1],score=0)
        with self.assertRaises(ValueError):self.do('ready',token=self.tokens[1],ready=True)
        for c in [{'smallBlind':11,'bigBlind':10},{'bigBlind':True},{'ante':-1},{'initial':0}]:
            with self.assertRaises(ValueError):validate_config(c)

    def test_varied_stack_hands_conserve_and_have_eligible_pots(self):
        import random
        rng=random.Random(20261003)
        for case in range(24):
            self.create(rng.randint(2,6), ante=rng.randint(0,8))
            stacks=[rng.randint(1,120) for _ in self.ids];self.stacks(stacks);total=sum(stacks);self.start()
            for step in range(120):
                s=self.state();self.conserved(total)
                if s['phase']=='finished':break
                if s['phase']=='dealing':self.do('deal',stage=s['dealPending']);continue
                if s['phase']=='showdown':
                    self.assertEqual(sum(p['amount'] for p in s['pots']),s['pot'])
                    self.assertTrue(all(p['eligible'] for p in s['pots']))
                    winners={p['id']:rng.sample(p['eligible'],rng.randint(1,len(p['eligible']))) for p in s['pots']}
                    self.do('settle',winners=winners);continue
                p=next(p for p in s['players'] if p['id']==s['turn']);t=self.host if p['id']==s['hostPlayer'] else p['token'];o=Engine(s).options(p)
                moves=['check' if o['canCheck'] else 'call']
                if o['canAllIn']:moves.append('allIn')
                if len([q for q in s['players'] if q['active']])>1:moves.append('fold')
                self.do(rng.choice(moves),token=t)
            else:self.fail('合法随机行动未终止')
            self.conserved(total)

    def test_winner_selection_is_public_and_does_not_change_scores(self):
        self.start();self.runout();before=self.state();pot=before['pots'][0];pid=pot['eligible'][0]
        self.do('selectWinner',potId=pot['id'],id=pid,selected=True)
        after=self.state()
        self.assertEqual([p['score'] for p in before['players']],[p['score'] for p in after['players']])
        self.assertEqual(len(before['undo']),len(after['undo']))
        guest=self.rooms.public(self.code,self.tokens[1],'')
        self.assertEqual(guest['winnerSelection']['winners'][pot['id']],[pid])
        self.assertFalse(guest['isController'])
        with self.assertRaises(Exception):self.do('selectWinner',token=self.tokens[1],potId=pot['id'],id=pid,selected=True)
        self.do('selectWinner',potId=pot['id'],id=pid,selected=False)
        self.assertEqual(self.state()['winnerSelection']['winners'][pot['id']],[])

    def test_winner_selection_checks_phase_eligibility_and_version(self):
        with self.assertRaises(Exception):self.do('selectWinner',potId='0',id=self.ids[0],selected=True)
        self.start();self.runout();pot=self.state()['pots'][0]
        for values in [dict(potId='invalid',id=self.ids[0],selected=True),dict(potId=pot['id'],id='missing',selected=True),dict(potId=pot['id'],id=self.ids[0],selected='yes')]:
            before=self.state()
            with self.assertRaises(Exception):self.do('selectWinner',**values)
            self.assertEqual(before,self.state())
        before=self.state()
        self.do('selectWinner',potId=pot['id'],id=pot['eligible'][0],selected=True)
        with self.assertRaises(Exception):self.rooms.execute(self.code,dict(action='selectWinner',token=self.host,expectedVersion=before['version'],potId=pot['id']))

    def test_auto_ready_finishes_and_allows_next_start(self):
        self.create(count=2)
        self.do('autoReady',token=self.tokens[1],enabled=True)
        self.assertTrue(self.state()['players'][1]['ready'])
        self.do('start');self.do('deal',stage='hole');self.runout()
        pot=self.state()['pots'][0]
        self.do('settle',winners={pot['id']:[self.ids[0]]})
        self.assertTrue(self.state()['players'][1]['ready'])
        self.assertFalse(self.state()['players'][0]['ready'])
        self.do('start')
        self.assertEqual(self.state()['hand'],2)

    def test_auto_ready_permission_zero_score_and_manual_cancel(self):
        with self.assertRaises(ValueError):self.do('autoReady',enabled=True)
        with self.assertRaises(ValueError):self.do('autoReady',token=self.tokens[1],enabled='yes')
        self.do('adjust',id=self.ids[1],score=0)
        self.do('autoReady',token=self.tokens[1],enabled=True)
        self.assertFalse(self.state()['players'][1]['ready'])
        self.do('adjust',id=self.ids[1],score=1000)
        self.do('autoReady',token=self.tokens[1],enabled=True)
        self.do('ready',token=self.tokens[1],ready=False)
        self.assertFalse(self.state()['players'][1]['autoReady'])

    def test_auto_ready_mid_hand_preserves_undo_and_preference(self):
        self.start();self.runout();before=len(self.state()['undo'])
        self.do('autoReady',token=self.tokens[1],enabled=True)
        self.assertEqual(len(self.state()['undo']),before)
        self.assertFalse(self.state()['players'][1]['ready'])
        self.do('undo')
        self.assertTrue(self.state()['players'][1]['autoReady'])

if __name__=='__main__':unittest.main()

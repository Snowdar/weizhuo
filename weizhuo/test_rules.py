"""Isolated lifecycle and rule tests. No production DB is opened."""
import json,sqlite3,tempfile,unittest
from pathlib import Path
from scoring.games.zhajinhua import Engine, fresh, DEFAULT as NEW_DEFAULT, LEGACY_DEFAULT as DEFAULT
from scoring.repository import Repository
from scoring.rooms import Rooms

class RoomLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'rooms.sqlite3';self.rooms=Rooms(Repository(self.path))
        out=self.rooms.create(dict(game='zhajinhua',name='朋友桌',nickname='A',config=DEFAULT))
        self.code=out['room'];self.host=out['token'];self.tokens=[self.host]
        for name in ['B','C']:self.tokens.append(self.do('join',token='',name=name)['token'])
        self.ids=[p['id'] for p in self.state()['players']]
    def state(self):return self.rooms.repo.get(self.code)
    def do(self,action,token=None,**data):return self.rooms.execute(self.code,dict(action=action,token=self.host if token is None else token,**data))
    def start(self):
        for t in self.tokens:self.do('ready',token=t)
        self.do('start')
    def total(self):s=self.state();return sum(p['score'] for p in s['players'])+s['pot']
    def test_requires_every_player_ready(self):
        with self.assertRaises(ValueError):self.do('start')
        for t in self.tokens[:2]:self.do('ready',token=t)
        with self.assertRaises(ValueError):self.do('start')
        self.do('ready',token=self.tokens[2]);self.do('start');self.assertEqual(self.total(),3000)
    def test_host_also_player_and_permissions(self):
        out=self.rooms.public(self.code,self.host,'invite')
        self.assertTrue(out['isHost']);self.assertEqual(out['me'],self.ids[0])
        with self.assertRaises(ValueError):self.do('adjust',token=self.tokens[1],id=self.ids[1],score=10)
        with self.assertRaises(ValueError):self.do('remove',id=self.ids[0])
    def test_two_hands_and_ready_reset(self):
        self.start();self.do('fold',token=self.tokens[0]);self.do('fold',token=self.tokens[1])
        s=self.state();self.assertEqual(s['phase'],'finished');self.assertEqual(self.total(),3000)
        self.assertFalse(any(p['ready'] for p in s['players']))
        with self.assertRaises(ValueError):self.do('start')
        self.start();self.assertEqual(self.state()['hand'],2);self.assertEqual(self.state()['turn'],self.ids[1])
        self.assertEqual(len(self.rooms.repo.histories(self.code)),1)
    def test_room_survives_repository_restart(self):
        self.start();before=self.state();reloaded=Rooms(Repository(self.path))
        self.assertEqual(reloaded.repo.get(self.code),before)
        self.assertTrue(reloaded.public(self.code,self.host,'invite')['isHost'])
    def test_destroy_clears_room_scores_and_history(self):
        self.start()
        with self.assertRaises(ValueError):self.do('destroy')
        self.do('fold');self.do('fold',token=self.tokens[1]);self.do('destroy')
        with self.assertRaises(ValueError):self.rooms.room(self.code)
        self.assertEqual(self.state()['players'],[]);self.assertEqual(self.rooms.repo.histories(self.code),[])
    def test_two_rooms_are_isolated(self):
        second=self.rooms.create(dict(game='zhajinhua',name='另一桌',nickname='D',config={'initial':200}))
        before=self.rooms.repo.get(second['room']);self.start();self.do('call');self.do('cancel')
        self.assertEqual(self.rooms.repo.get(second['room']),before)
        with self.assertRaises(ValueError):self.do('start',token=second['token'])
    def test_adjust_kick_and_leave_only_between(self):
        self.do('ready',token=self.tokens[1]);self.do('adjust',id=self.ids[1],score=800)
        self.assertFalse(self.state()['players'][1]['ready']);self.start()
        for a in ['remove','leave','ready']:
            with self.assertRaises(ValueError):self.do(a,token=self.tokens[1] if a in ['leave','ready'] else self.host,id=self.ids[1],score=500)
        self.do('adjust',id=self.ids[1],score=500);self.assertEqual(self.state()['players'][1]['score'],500)
        self.do('cancel');self.do('remove',id=self.ids[2]);self.do('leave',token=self.tokens[1]);self.assertEqual(len(self.state()['players']),1)
    def test_config_reprepare_and_invalid_config_rollback(self):
        for t in self.tokens:self.do('ready',token=t)
        self.do('config',config={**DEFAULT,'base':20});self.assertFalse(any(p['ready'] for p in self.state()['players']))
        before=self.state()
        with self.assertRaises(ValueError):self.do('config',config={**DEFAULT,'maxBet':1})
        self.assertEqual(self.state(),before)
    def test_floor_cap_turn_and_raise(self):
        self.start();before=self.state()
        with self.assertRaises(ValueError):self.do('call',token=self.tokens[1])
        with self.assertRaises(ValueError):self.do('raise',level=110)
        self.assertEqual(self.state(),before)
        s=self.state();s['players'][0]['score']=0;self.rooms.repo.save(s)
        with self.assertRaises(ValueError):self.do('call')
        s['players'][0].update(score=995,spent=495);self.rooms.repo.save(s)
        with self.assertRaises(ValueError):self.do('call')
    def test_seen_raise_fold_conservation(self):
        self.start();self.do('seen');self.do('raise',level=20);self.assertEqual(self.state()['pot'],55)
        self.do('call',token=self.tokens[1]);self.do('fold',token=self.tokens[2]);self.do('fold')
        self.assertEqual(self.state()['result']['winner'],'B');self.assertEqual(self.total(),3000)
    def test_compare_pending_then_resolution(self):
        self.start()
        for t in self.tokens:self.do('seen',token=t)
        with self.assertRaises(ValueError):self.do('compare',id=self.ids[1])
        for t in self.tokens:self.do('call',token=t)
        self.do('compare',id=self.ids[1]);self.assertEqual(self.state()['phase'],'comparing')
        with self.assertRaises(ValueError):self.do('resolve',token=self.tokens[2],id=self.ids[1])
        self.do('resolve',id=self.ids[1]);self.assertEqual(self.state()['turn'],self.ids[1]);self.assertEqual(self.total(),3000)
    def test_max_rounds_and_cancellation(self):
        self.do('config',config={**DEFAULT,'maxRounds':1});self.start()
        for t in self.tokens:self.do('call',token=t)
        self.assertEqual(self.state()['phase'],'showdown');self.do('cancel');self.assertEqual(self.total(),3000)
        self.assertFalse(any(p['ready'] for p in self.state()['players']))
    def test_idempotent_and_failed_action_atomicity(self):
        self.start();self.do('call',requestId='unique-call');before=self.state()
        self.do('call',requestId='unique-call');self.assertEqual(self.state(),before)
        with self.assertRaises(ValueError):self.do('call')
        self.assertEqual(self.state(),before)
    def test_no_private_tokens_in_public(self):
        raw=json.dumps(self.rooms.public(self.code,'','invitation'))
        for t in self.tokens:self.assertNotIn(t,raw)
    def test_rule_modes_and_blind_compare(self):
        self.do('config',config={**DEFAULT,'seenRaisesFloor':1,'allowBlindCompare':1})
        self.start();self.do('seen');self.do('call');self.assertEqual(self.state()['level'],20)
        self.do('call',token=self.tokens[1]);self.do('call',token=self.tokens[2])
        self.do('compare',id=self.ids[1]);self.do('resolve',id=self.ids[1]);self.assertEqual(self.total(),3000)
    def test_instant_rule_change_preserves_spent(self):
        self.start();self.do('call');before=self.state();self.do('config',config={**DEFAULT,'maxRounds':1,'base':20})
        s=self.state();self.assertEqual(s['players'],before['players']);self.assertEqual(s['pot'],before['pot']);self.assertEqual(s['level'],20)
    def test_migrate_legacy_without_changing_scores(self):
        old=fresh();old['players']=[dict(id='x',token='t',name='旧玩家',score=876,spent=0,active=False,seen=False,start=876)]
        path=Path(self.tmp.name)/'old.sqlite3'
        with sqlite3.connect(path) as db:db.execute('CREATE TABLE state(id INTEGER PRIMARY KEY,data TEXT)');db.execute('INSERT INTO state VALUES(1,?)',(json.dumps(old),))
        repo=Repository(path);s=repo.get(old['room']);self.assertEqual(s['players'][0]['score'],876);self.assertFalse(s['players'][0]['ready'])
        self.assertEqual(repo.legacy,old['room'])
    def test_only_rounds_force_showdown_at_cap(self):
        self.do('config',config={**DEFAULT,'cap':25,'maxBet':20})
        self.start();self.do('call');self.do('seen',token=self.tokens[1]);self.do('call',token=self.tokens[1])
        self.assertEqual(self.state()['players'][1]['spent'],25)
        self.assertEqual(self.state()['phase'],'playing')
        self.assertEqual(self.state()['turn'],self.ids[2])
        before=self.state()
        with self.assertRaises(ValueError):self.do('settle',id=self.ids[1])
        self.assertEqual(self.state(),before)
        self.do('call',token=self.tokens[2]);self.do('call')
        before=self.state()
        with self.assertRaises(ValueError):self.do('call',token=self.tokens[1])
        self.assertEqual(self.state(),before)
        self.do('fold',token=self.tokens[1]);self.assertEqual(self.state()['phase'],'playing')
        self.assertEqual(self.total(),3000)

    def test_lower_bet_limit_does_not_force_showdown(self):
        self.start();self.do('raise',level=20)
        self.do('config',config={**DEFAULT,'maxBet':20})
        self.assertEqual(self.state()['phase'],'playing')
        self.do('seen',token=self.tokens[1]);before=self.state()
        self.do('call',token=self.tokens[1])
        self.assertEqual(self.state()['players'][1]['spent'],25)
        self.assertEqual(self.state()['level'],20)
        self.do('call',token=self.tokens[2])
        self.assertEqual(self.state()['phase'],'playing');self.assertEqual(self.total(),3000)

    def test_host_can_confirm_compare_and_second_submission_rejected(self):
        self.start()
        for t in self.tokens:self.do('seen',token=t)
        for t in self.tokens:self.do('call',token=t)
        self.do('compare',id=self.ids[1]);before=self.state()
        with self.assertRaises(ValueError):self.do('resolve',id=self.ids[2])
        self.assertEqual(self.state(),before)
        self.do('resolve',token=self.tokens[0],id=self.ids[0])
        self.assertFalse(self.state()['players'][1]['active'])
        before=self.state()
        with self.assertRaises(ValueError):self.do('resolve',token=self.tokens[1],id=self.ids[1])
        self.assertEqual(self.state(),before);self.assertEqual(self.total(),3000)

    def test_rounds_end_in_comparison_then_force_showdown(self):
        self.do('config',config={**DEFAULT,'maxRounds':2})
        self.start()
        for t in self.tokens:self.do('seen',token=t)
        for t in self.tokens:self.do('call',token=t)
        self.do('call');self.do('call',token=self.tokens[1])
        self.do('compare',token=self.tokens[2],id=self.ids[0])
        self.assertEqual(self.state()['phase'],'comparing')
        self.do('resolve',id=self.ids[0])
        self.assertEqual(self.state()['phase'],'showdown')
        self.do('settle',id=self.ids[0]);self.assertEqual(self.total(),3000)

    def test_custom_call_and_following_level(self):
        self.start();self.do('call',amount=15)
        self.assertEqual(self.state()['players'][0]['spent'],20)
        self.assertEqual(self.state()['level'],15)
        self.do('call',token=self.tokens[1])
        self.assertEqual(self.state()['players'][1]['spent'],20)
        self.do('raise',token=self.tokens[2],level=20)
        self.assertEqual(self.state()['level'],20);self.assertEqual(self.total(),3000)

    def test_custom_seen_call_and_invalid_amounts_atomic(self):
        self.start();self.do('seen')
        for amount in [0,19,201,True,'30',20.5,None]:
            before=self.state()
            with self.assertRaises(ValueError):self.do('call',amount=amount)
            self.assertEqual(self.state(),before)
        self.do('call',amount=31)
        self.assertEqual(self.state()['level'],16)
        self.assertEqual(self.state()['players'][0]['spent'],36)
        self.assertEqual(self.total(),3000)

    def test_capped_seen_and_dark_call_keep_level(self):
        self.do('config',config={**DEFAULT,'seenRaisesFloor':1,'maxBet':40})
        self.start();self.do('seen');self.do('call',amount=40)
        self.assertEqual(self.state()['level'],40)
        self.do('seen',token=self.tokens[1]);self.do('call',token=self.tokens[1],amount=40)
        self.assertEqual(self.state()['players'][1]['spent'],45)
        self.assertEqual(self.state()['level'],40)
        self.do('call',token=self.tokens[2]);self.assertEqual(self.state()['players'][2]['spent'],45)
        self.assertEqual(self.state()['phase'],'playing');self.assertEqual(self.total(),3000)

    def test_custom_call_respects_floor_cap_and_turn(self):
        self.start();before=self.state()
        with self.assertRaises(ValueError):self.do('call',token=self.tokens[1],amount=20)
        self.assertEqual(self.state(),before)
        s=self.state();s['players'][0].update(score=15,spent=5);self.rooms.repo.save(s)
        before=self.state()
        with self.assertRaises(ValueError):self.do('call',amount=20)
        self.assertEqual(self.state(),before)
        s['players'][0].update(score=995,spent=490);self.rooms.repo.save(s)
        before=self.state()
        with self.assertRaises(ValueError):self.do('call',amount=20)
        self.assertEqual(self.state(),before)

    def test_comparison_fee_capped_and_idempotent_custom_call(self):
        self.do('config',config={**DEFAULT,'maxBet':40,'seenRaisesFloor':1,'allowBlindCompare':1,'minCompare':1})
        self.start();self.do('seen');self.do('call',amount=40,requestId='custom-40')
        before=self.state();self.do('call',amount=40,requestId='custom-40');self.assertEqual(self.state(),before)
        self.do('call',token=self.tokens[1]);self.do('call',token=self.tokens[2])
        pot=self.state()['pot'];self.do('compare',id=self.ids[1])
        self.assertEqual(self.state()['pot']-pot,40)
        self.do('resolve',id=self.ids[1]);self.assertEqual(self.total(),3000)

    def gameplay(self):
        return {k:v for k,v in self.state().items() if k not in ('version','requests','log','undo')}

    def test_undo_permissions_steps_persistence_and_privacy(self):
        self.start();before=self.gameplay()
        self.do('seen');seen=self.gameplay();self.do('call',amount=31,requestId='original-call')
        state=self.state()
        with self.assertRaises(ValueError):self.do('undo',token=self.tokens[1])
        self.assertEqual(self.state(),state)
        public=self.rooms.public(self.code,self.host,'invite')
        self.assertTrue(public['canUndo']);self.assertNotIn('undo',public)
        self.assertFalse(self.rooms.public(self.code,self.tokens[1],'invite')['canUndo'])
        self.rooms=Rooms(Repository(self.path))
        self.do('undo',requestId='undo-call');self.assertEqual(self.gameplay(),seen)
        state=self.state();self.do('undo',requestId='undo-call');self.assertEqual(self.state(),state)
        # Retries of the original action cannot silently reapply an undone bet.
        self.do('call',amount=31,requestId='original-call');self.assertEqual(self.state(),state)
        self.do('undo');self.assertEqual(self.gameplay(),before)
        state=self.state()
        with self.assertRaises(ValueError):self.do('undo')
        self.assertEqual(self.state(),state);self.assertEqual(self.total(),3000)

    def test_undo_compare_and_host_only_result(self):
        self.start()
        for t in self.tokens:self.do('seen',token=t)
        for t in self.tokens:self.do('call',token=t)
        self.do('call');before=self.gameplay()
        self.do('compare',token=self.tokens[1],id=self.ids[2]);pending=self.gameplay()
        for t in self.tokens[1:]:
            state=self.state()
            with self.assertRaises(ValueError):self.do('resolve',token=t,id=self.ids[2])
            self.assertEqual(self.state(),state)
        self.do('resolve',id=self.ids[2]);self.do('undo');self.assertEqual(self.gameplay(),pending)
        self.do('undo');self.assertEqual(self.gameplay(),before);self.assertEqual(self.total(),3000)

    def test_undo_auto_settlement_removes_history(self):
        self.start();self.do('fold');before=self.gameplay()
        self.do('fold',token=self.tokens[1]);self.assertEqual(self.state()['phase'],'finished')
        self.assertEqual(len(self.rooms.repo.histories(self.code)),1)
        self.do('undo');self.assertEqual(self.gameplay(),before)
        self.assertEqual(self.rooms.repo.histories(self.code),[])
        self.do('fold',token=self.tokens[1]);self.do('ready')
        with self.assertRaises(ValueError):self.do('undo')
        self.assertEqual(self.total(),3000)

    def test_undo_round_config_cancel_and_forced_settlement(self):
        self.do('config',config={**DEFAULT,'maxRounds':1});self.start()
        self.do('call');self.do('call',token=self.tokens[1]);before=self.gameplay()
        self.do('call',token=self.tokens[2]);showdown=self.gameplay()
        self.do('settle',id=self.ids[0]);self.do('undo')
        self.assertEqual(self.gameplay(),showdown);self.assertEqual(self.rooms.repo.histories(self.code),[])
        self.do('undo');self.assertEqual(self.gameplay(),before)
        self.do('config',config={**DEFAULT,'maxRounds':3});self.do('undo');self.assertEqual(self.gameplay(),before)
        self.do('cancel');self.do('undo');self.assertEqual(self.gameplay(),before)
        self.assertEqual(self.total(),3000)

    def test_creation_defaults_and_explicit_override(self):
        c=self.state()['config']
        self.assertEqual(c['seenRaisesFloor'],0);self.assertEqual(c['allowBlindCompare'],1)
        self.start();self.do('seen');self.do('call')
        self.assertEqual(self.state()['level'],10)
        self.do('call',token=self.tokens[1]);self.do('call',token=self.tokens[2])
        self.do('compare',id=self.ids[1]);self.assertEqual(self.state()['phase'],'comparing')
        other=self.rooms.create(dict(game='zhajinhua',name='自定义',nickname='房主',config={'seenRaisesFloor':1,'allowBlindCompare':0}))
        c=self.rooms.repo.get(other['room'])['config']
        self.assertEqual(c['seenRaisesFloor'],1);self.assertEqual(c['allowBlindCompare'],0)
        self.assertEqual(Repository.normalize({'config':{},'players':[]})['config']['allowBlindCompare'],0)

    def test_dark_compare_targets_cost_and_undo(self):
        self.do('config',config={**DEFAULT,'allowBlindCompare':0})
        self.start();before=self.state()
        with self.assertRaises(ValueError):self.do('compare',id=self.ids[1])
        self.assertEqual(self.state(),before)
        self.do('seen',token=self.tokens[1])
        for t in self.tokens:self.do('call',token=t)
        original=self.gameplay()
        for target in (self.ids[1],self.ids[2]):
            self.do('compare',id=target)
            s=self.state();self.assertEqual(s['pot'],original['pot']+10)
            self.assertFalse(s['players'][0]['seen']);self.assertEqual(s['bets'][-1]['kind'],'比牌')
            self.do('undo');self.assertEqual(self.gameplay(),original)
        self.do('compare',id=self.ids[2]);pending=self.gameplay()
        with self.assertRaises(ValueError):self.do('resolve',token=self.tokens[2],id=self.ids[2])
        self.do('resolve',id=self.ids[2]);self.do('undo');self.assertEqual(self.gameplay(),pending)
        self.assertEqual(self.total(),3000)

    def test_dark_compare_respects_limits_and_seen_rule(self):
        self.do('config',config={**DEFAULT,'allowBlindCompare':0,'minCompare':1})
        self.start();self.do('seen',token=self.tokens[1])
        for score,spent in ((0,5),(995,495)):
            s=self.state();s['players'][0].update(score=score,spent=spent);self.rooms.repo.save(s)
            before=self.state()
            with self.assertRaises(ValueError):self.do('compare',id=self.ids[1])
            self.assertEqual(self.state(),before)
        s=self.state();s['players'][0].update(score=995,spent=5);self.rooms.repo.save(s)
        self.do('call');before=self.state()
        with self.assertRaises(ValueError):self.do('compare',id=self.ids[1])
        with self.assertRaises(ValueError):self.do('compare',token=self.tokens[1],id=self.ids[2])
        self.assertEqual(self.state(),before)

    def test_new_limits_defaults_no_hand_cap_and_integer_raises(self):
        self.do('config',config=NEW_DEFAULT)
        c=self.state()['config']
        self.assertEqual((c['ante'],c['minBet'],c['maxBet'],c['minRaise']),(10,10,100,0))
        self.assertNotIn('base',c);self.assertNotIn('cap',c)
        self.start();self.assertEqual(self.state()['pot'],30)
        self.do('call',amount=11);self.assertEqual(self.state()['level'],11)
        self.do('raise',token=self.tokens[1],level=12)
        self.do('call',token=self.tokens[2],amount=100)
        for _ in range(15):
            s=self.state();t=next(p['token'] for p in s['players'] if p['id']==s['turn'])
            self.do('call',token=t)
        self.assertTrue(all(p['spent']>500 for p in self.state()['players']))
        self.assertEqual(self.state()['phase'],'playing');self.assertEqual(self.total(),3000)

    def test_new_increment_validation_config_and_undo(self):
        self.do('config',config={**NEW_DEFAULT,'minRaise':5});self.start()
        before=self.state()
        for action,data in [('call',{'amount':11}),('raise',{'level':11})]:
            with self.assertRaises(ValueError):self.do(action,**data)
            self.assertEqual(self.state(),before)
        self.do('call',amount=10);self.do('raise',token=self.tokens[1],level=15)
        self.assertEqual(self.state()['level'],15);self.do('undo')
        self.assertEqual(self.state()['level'],10)
        for patch in ({'minBet':101},{'minRaise':-1},{'minRaise':0.5}):
            before=self.state()
            with self.assertRaises(ValueError):self.do('config',config={**NEW_DEFAULT,**patch})
            self.assertEqual(self.state(),before)
        self.assertEqual(self.total(),3000)

    def test_unknown_game_and_incompatible_settings(self):
        with self.assertRaises(ValueError):self.rooms.create(dict(game='unknown',name='x',nickname='y'))
        with self.assertRaises(ValueError):self.rooms.create(dict(game='zhajinhua',name='x',nickname='y',config={'cap':10}))

class BetRecordTests(unittest.TestCase):
    setUp=RoomLifecycle.setUp
    state=RoomLifecycle.state
    do=RoomLifecycle.do
    start=RoomLifecycle.start
    def test_per_bet_labels_totals_and_persistence(self):
        self.start();self.do('seen');self.do('call',amount=20)
        self.do('raise',token=self.tokens[1],level=20)
        self.do('call',token=self.tokens[2]);self.do('call')
        s=self.state();bets=s['bets']
        self.assertEqual([b['kind'] for b in bets],['底注','底注','底注','跟注','加注','跟注','跟注'])
        self.assertEqual([b['seq'] for b in bets],list(range(1,8)))
        self.assertEqual(sum(b['amount'] for b in bets),s['pot'])
        for p in s['players']:self.assertEqual(sum(b['amount'] for b in bets if b['playerId']==p['id']),p['spent'])
        self.assertEqual(Rooms(Repository(self.path)).repo.get(self.code)['bets'],bets)
    def test_compare_record_and_next_hand_reset(self):
        self.start()
        for t in self.tokens:self.do('seen',token=t)
        for t in self.tokens:self.do('call',token=t)
        self.do('compare',id=self.ids[1]);self.assertEqual(self.state()['bets'][-1]['kind'],'比牌')
        self.do('resolve',id=self.ids[1]);self.do('fold',token=self.tokens[1])
        self.assertEqual(len(self.rooms.repo.histories(self.code)[0]['bets']),7)
        self.start();self.assertEqual(len(self.state()['bets']),3)
        self.do('cancel');self.assertEqual(self.state()['bets'],[])
    def test_invalid_bet_and_duplicate_do_not_add_records(self):
        self.start();self.do('call',requestId='bet-once');before=self.state()['bets']
        self.do('call',requestId='bet-once');self.assertEqual(self.state()['bets'],before)
        with self.assertRaises(ValueError):self.do('call')
        self.assertEqual(self.state()['bets'],before)

class NegativeScoreRules(unittest.TestCase):
    setUp=RoomLifecycle.setUp
    state=RoomLifecycle.state
    do=RoomLifecycle.do
    start=RoomLifecycle.start
    total=RoomLifecycle.total
    def test_default_allows_negative_and_negative_player_can_bet_compare(self):
        self.assertEqual(fresh()['config']['allowNegative'],1)
        self.do('config',config={**NEW_DEFAULT,'allowNegative':1})
        self.do('adjust',id=self.ids[0],score=0)
        self.do('adjust',id=self.ids[1],score=0)
        self.do('autoReady',token=self.tokens[1],enabled=True)
        self.assertTrue(self.state()['players'][1]['ready'])
        self.start();total=self.total()
        self.assertEqual(self.state()['players'][0]['score'],-10)
        self.do('call');self.assertEqual(self.state()['players'][0]['score'],-20)
        self.do('call',token=self.tokens[1]);self.do('call',token=self.tokens[2])
        self.do('seen');self.do('compare',id=self.ids[1])
        self.assertEqual(self.state()['players'][0]['score'],-40)
        self.assertEqual(self.state()['phase'],'comparing')
        self.assertEqual(self.total(),total)
        self.do('resolve',id=self.ids[1]);self.assertEqual(self.total(),total)
        self.do('hostFold',id=self.ids[2]);self.assertEqual(self.total(),total)
        self.assertTrue(self.state()['players'][1]['ready'])
    def test_disable_negative_prevents_payment_and_can_enable_mid_hand(self):
        self.start()
        self.do('adjust',id=self.ids[0],score=0)
        for action,data in [('call',{}),('compare',{'id':self.ids[1]})]:
            with self.assertRaises(ValueError):self.do(action,**data)
        self.assertTrue(self.state()['players'][0]['active'])
        self.do('config',config={**DEFAULT,'allowNegative':1,'minCompare':1})
        self.do('compare',id=self.ids[1]);self.assertEqual(self.state()['players'][0]['score'],-10)

if __name__=='__main__':unittest.main()

import tempfile, unittest
from pathlib import Path
from scoring.repository import Repository
from scoring.rooms import Rooms

class MahjongScoring(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'rooms.sqlite3';self.rooms=Rooms(Repository(self.path))
        out=self.rooms.create(dict(game='mahjong',name='麻将桌',nickname='A',config={'initial':0}))
        self.code=out['room'];self.host=out['token']
        self.b=self.do('join',token='',name='B')['token'];self.c=self.do('join',token='',name='C')['token']
        self.ids=[p['id'] for p in self.state()['players']]
    def state(self):return self.rooms.room(self.code)
    def do(self,action,token=None,**data):return self.rooms.execute(self.code,dict(action=action,token=self.host if token is None else token,**data))
    def scores(self):return [p['score'] for p in self.state()['players']]
    def test_free_scoring_supports_more_than_ten_players_and_group_requests(self):
        for i in range(3,20):self.do('join',token='',name=f'玩家{i}')
        self.assertEqual(len(self.state()['players']),20)
        with self.assertRaisesRegex(ValueError,'最多 20 人'):self.do('join',token='',name='超出人数')
        ids=[p['id'] for p in self.state()['players']][1:]
        self.do('requestTransferAll',ids=ids,rosterIds=ids,amount=1)
        self.assertEqual(len(self.state()['paymentRequests']),19)
    def test_transfer_without_start_allows_negative_and_only_debits_actor(self):
        self.do('transfer',token=self.b,id=self.ids[0],amount=20)
        self.assertEqual(self.scores(),[20,-20,0]);self.assertEqual(self.state()['phase'],'lobby')
        self.assertEqual(len(self.state()['transactions']),1)
        with self.assertRaises(ValueError):self.do('transfer',token='',id=self.ids[0],amount=20)
    def test_invalid_transfer_rolls_back(self):
        before=self.state()
        for value in [0,-1,1.5,True]:
            with self.assertRaises(ValueError):self.do('transfer',id=self.ids[1],amount=value)
        with self.assertRaises(ValueError):self.do('transfer',id=self.ids[0],amount=10)
        self.assertEqual(self.state(),before)
    def test_settlement_zero_sum_and_host_permission(self):
        deltas=dict(zip(self.ids,[30,-20,-10]))
        with self.assertRaises(ValueError):self.do('manualSettle',token=self.b,deltas=deltas)
        with self.assertRaises(ValueError):self.do('manualSettle',deltas=dict(zip(self.ids,[30,-10,-10])))
        self.do('manualSettle',deltas=deltas);self.assertEqual(self.scores(),[30,-20,-10])
        self.assertEqual(self.state()['hand'],0);self.assertIsNone(self.state()['result'])
    def test_stale_membership_rejected(self):
        deltas=dict(zip(self.ids,[30,-20,-10]));self.do('remove',id=self.ids[2])
        with self.assertRaises(ValueError):self.do('manualSettle',deltas=deltas)
        self.assertEqual(self.scores(),[0,0])
    def test_undo_and_request_retry(self):
        self.do('transfer',id=self.ids[1],amount=15,requestId='one')
        self.do('transfer',id=self.ids[1],amount=15,requestId='one')
        self.assertEqual(self.scores(),[-15,15,0])
        with self.assertRaises(ValueError):self.do('undo',token=self.b)
        self.do('undo');self.assertEqual(self.scores(),[0,0,0]);self.assertEqual(self.state()['transactions'],[])
    def test_persistence_and_destroy(self):
        self.do('transfer',id=self.ids[1],amount=8)
        self.assertEqual(Rooms(Repository(self.path)).room(self.code),self.state())
        self.do('destroy');s=self.rooms.repo.get(self.code)
        self.assertEqual(s['players'],[]);self.assertEqual(s['transactions'],[])
    def test_no_poker_rules_and_future_initial(self):
        for action in ('ready','start','call','seen','fold','settle'):
            with self.assertRaises(ValueError):self.do(action)
        self.do('config',config={'initial':100,'poolEnabled':False});self.assertEqual(self.scores(),[0,0,0])
        self.do('join',token='',name='D');self.assertEqual(self.scores(),[0,0,0,100])
        self.assertEqual(self.state()['config'],{'initial':100,'poolEnabled':False})
    def test_adjust_logged_and_reversible(self):
        self.do('adjust',id=self.ids[1],score=-200);self.assertEqual(self.scores(),[0,-200,0])
        self.assertEqual(self.state()['transactions'][0]['kind'],'改分')
        self.do('undo');self.assertEqual(self.scores(),[0,0,0])

    def test_free_scoring_label_keeps_legacy_identity_and_records(self):
        self.do('transfer', id=self.ids[1], amount=13)
        before = self.state()
        restored = Rooms(Repository(self.path))
        public = restored.public(self.code, self.host, 'invite')
        self.assertEqual(public['game'], 'mahjong')
        self.assertEqual(public['gameName'], '自由记分')
        self.assertEqual(restored.room(self.code), before)
        self.assertEqual(public['transactions'][0]['changes'][0]['delta'], -13)


    def test_optional_pool_default_permissions_and_balance(self):
        self.assertFalse(self.state()['config']['poolEnabled'])
        for action in ('depositPool','allocatePool'):
            with self.assertRaisesRegex(ValueError,'未启用'):self.do(action,id=self.ids[1],amount=1)
        with self.assertRaises(ValueError):self.do('config',token=self.b,config={'poolEnabled':True})
        with self.assertRaises(ValueError):self.do('config',config={'poolEnabled':'false'})
        self.do('config',config={'poolEnabled':True})
        self.do('depositPool',amount=10)
        with self.assertRaisesRegex(ValueError,'分配完'):self.do('config',config={'poolEnabled':False})
        self.assertEqual(self.state()['pot'],10)
        self.assertTrue(self.state()['config']['poolEnabled'])
        self.do('allocatePool',id=self.ids[1],amount=10)
        self.do('config',config={'poolEnabled':False})
        self.assertEqual(self.scores(),[-10,10,0])
        self.assertFalse(Rooms(Repository(self.path)).room(self.code)['config']['poolEnabled'])
        self.do('undo')
        self.assertTrue(self.state()['config']['poolEnabled'])

    def test_legacy_room_keeps_pool(self):
        s=self.state();s['config'].pop('poolEnabled');self.rooms.repo.save(s)
        self.do('depositPool',amount=7)
        self.do('config',config={'initial':20})
        self.assertTrue(self.state()['config']['poolEnabled'])
        self.assertEqual(self.state()['pot'],7)

if __name__=='__main__':unittest.main()

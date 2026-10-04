import unittest,tempfile
from pathlib import Path
from scoring.repository import Repository
from scoring.rooms import Rooms

class TabletopProducts(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.rooms=Rooms(Repository(Path(self.tmp.name)/'test.sqlite3'))
 def create(self,game):
  out=self.rooms.create({'game':game,'name':'体验桌','nickname':'甲','config':{}});self.code=out['room'];self.host=out['token']
  self.other=self.do('join',token='',name='乙')['token'];self.ids=[p['id'] for p in self.saved()['players']]
 def saved(self):return self.rooms.repo.get(self.code)
 def do(self,action,token=None,**d):return self.rooms.execute(self.code,{'action':action,'token':self.host if token is None else token,**d})
 def test_host_ready_numbers_and_proxy_undo(self):
  self.create('zhajinhua');numbers={p['id']:p['playerNumber'] for p in self.saved()['players']}
  self.do('seating',ids=self.ids[::-1]);self.assertEqual(numbers,{p['id']:p['playerNumber'] for p in self.saved()['players']})
  self.do('ready',token=self.other);self.do('start');s=self.saved();turn=s['turn']
  with self.assertRaises(ValueError):self.do('actFor',token=self.other,playerId=turn,operation='call',amount=10)
  self.do('actFor',playerId=turn,operation='call',amount=10);self.assertEqual(self.saved()['pot'],30)
  self.do('undo');self.assertEqual(self.saved()['pot'],20);self.assertEqual(self.saved()['turn'],turn)
 def test_comparison_selection_is_public_and_eligible(self):
  self.create('zhajinhua');self.do('ready',token=self.other);self.do('start')
  self.do('compare',id=self.ids[1]);self.do('selectWinner',id=self.ids[0])
  public=self.rooms.public(self.code,self.other,'')
  self.assertEqual(public['winnerSelection'],self.ids[0]);self.assertEqual(public['pot'],30)
  with self.assertRaises(ValueError):self.do('selectWinner',token=self.other,id=self.ids[1])
  self.do('resolve',id=self.ids[0]);self.assertIsNone(self.saved()['winnerSelection'])
  with self.assertRaises(ValueError):self.do('selectWinner',id=self.ids[1])
 def test_automatic_ready_after_settlement(self):
  self.create('zhajinhua');self.do('autoReady',token=self.other,enabled=True);self.do('start');self.do('fold')
  self.assertTrue(self.saved()['players'][1]['ready']);self.do('start')
 def request(self):
  self.create('mahjong');self.do('requestTransfer',id=self.ids[1],amount=50,note='桌游结算')
  return self.saved()['paymentRequests'][0]['id']
 def test_request_requires_payer_and_is_idempotent(self):
  rid=self.request();self.assertEqual([p['score'] for p in self.saved()['players']],[0,0])
  self.assertEqual(self.rooms.public(self.code,self.other,'')['paymentRequests'][0]['status'],'pending')
  with self.assertRaises(ValueError):self.do('resolveTransfer',requestIdToResolve=rid,accepted=True)
  self.do('resolveTransfer',token=self.other,requestIdToResolve=rid,accepted=True)
  self.assertEqual([p['score'] for p in self.saved()['players']],[50,-50])
  with self.assertRaises(ValueError):self.do('resolveTransfer',token=self.other,requestIdToResolve=rid,accepted=True)
  self.do('undo');self.assertEqual([p['score'] for p in self.saved()['players']],[0,0]);self.assertEqual(self.saved()['paymentRequests'][0]['status'],'pending')
 def test_reject_cancel_and_leave_never_change_scores(self):
  rid=self.request();self.do('resolveTransfer',token=self.other,requestIdToResolve=rid,accepted=False)
  self.assertEqual([p['score'] for p in self.saved()['players']],[0,0])
  self.do('requestTransfer',id=self.ids[1],amount=10);rid=self.saved()['paymentRequests'][0]['id']
  self.do('cancelTransferRequest',requestIdToResolve=rid);self.assertEqual(self.saved()['paymentRequests'][0]['status'],'cancelled')
  self.do('requestTransfer',id=self.ids[1],amount=10);self.do('leave',token=self.other)
  self.assertFalse(any(r['status']=='pending' for r in self.saved()['paymentRequests']))
 def test_free_seat_reorder_preserves_numbers_and_scores(self):
  self.create('mahjong');before={p['id']:(p['playerNumber'],p['score']) for p in self.saved()['players']}
  self.do('seating',ids=self.ids[::-1]);self.assertEqual(before,{p['id']:(p['playerNumber'],p['score']) for p in self.saved()['players']})

 def test_pool_conservation_owner_allocation_and_undo(self):
  self.create('mahjong');self.do('config',config={'initial':0,'poolEnabled':True});self.do('depositPool',amount=100);self.do('depositPool',token=self.other,amount=50)
  self.assertEqual(sum(p['score'] for p in self.saved()['players'])+self.saved()['pot'],0)
  with self.assertRaises(ValueError):self.do('allocatePool',token=self.other,id=self.ids[1],amount=10)
  with self.assertRaises(ValueError):self.do('allocatePool',id=self.ids[1],amount=151)
  self.do('allocatePool',id=self.ids[1],amount=120);self.assertEqual(self.saved()['pot'],30);self.assertEqual(self.saved()['players'][1]['score'],70)
  self.do('undo');self.assertEqual(self.saved()['pot'],150);self.assertEqual(self.saved()['players'][1]['score'],-50)
  self.do('undo');self.assertEqual(self.saved()['pot'],100);self.assertEqual(self.saved()['players'][1]['score'],0)

 def test_custom_scoring_rules_permissions_and_undo(self):
  self.create('mahjong')
  with self.assertRaises(ValueError):self.do('editScoringRules',token=self.other,text='胜者得 10 分')
  self.do('transfer',id=self.ids[1],amount=10)
  self.do('editScoringRules',text='胜者得 10 分\n允许负分')
  self.assertEqual(self.rooms.public(self.code,self.other,'')['scoringRules'],'胜者得 10 分\n允许负分')
  self.do('undo');self.assertEqual(self.saved()['scoringRules'],'胜者得 10 分\n允许负分')
  self.assertEqual([p['score'] for p in self.saved()['players']],[0,0])
  with self.assertRaises(ValueError):self.do('editScoringRules',text='字'*2001)

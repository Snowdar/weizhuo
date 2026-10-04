from pathlib import Path
import tempfile,unittest
from scoring.repository import Repository
from scoring.rooms import Rooms
class FreeGroupTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.rooms=Rooms(Repository(Path(self.tmp.name)/'db.sqlite3'))
  out=self.rooms.create(dict(game='mahjong',name='全场测试',nickname='甲',config={}))
  self.code,self.host=out['room'],out['token'];self.tokens=[]
  for name in ['乙','丙']:self.tokens.append(self.do('join',token='',name=name)['token'])
  self.ids=[p['id'] for p in self.saved()['players']][1:]
 def saved(self):return self.rooms.repo.get(self.code)
 def do(self,action,token=None,**data):return self.rooms.execute(self.code,dict(action=action,token=self.host if token is None else token,**data))
 def test_group_give_atomic_conserved_idempotent_and_undo(self):
  data=dict(ids=self.ids,amount=1,requestId='group-1')
  self.do('transferAll',**data);self.do('transferAll',**data)
  self.assertEqual([p['score'] for p in self.saved()['players']],[-2,1,1]);self.assertEqual(len(self.saved()['transactions']),1)
  self.do('undo');self.assertEqual([p['score'] for p in self.saved()['players']],[0,0,0]);self.assertEqual(self.saved()['transactions'],[])
 def test_membership_and_invalid_amount_have_no_partial_result(self):
  before=self.saved()
  for ids,amount in [(self.ids[:1],1),(self.ids*2,1),(self.ids,0),(self.ids,True),(self.ids,1000001)]:
   with self.assertRaises(ValueError):self.do('transferAll',ids=ids,amount=amount)
   self.assertEqual(self.saved(),before)
  self.do('join',token='',name='丁');after=self.saved()
  with self.assertRaises(ValueError):self.do('requestTransferAll',ids=self.ids,amount=1)
  self.assertEqual(self.saved(),after)
 def test_group_collection_individual_permission_and_confirmation(self):
  self.do('requestTransferAll',ids=self.ids,amount=1,requestId='req-1');self.do('requestTransferAll',ids=self.ids,amount=1,requestId='req-1')
  requests=self.saved()['paymentRequests'];self.assertEqual(len(requests),2);self.assertEqual([p['score'] for p in self.saved()['players']],[0,0,0])
  with self.assertRaises(ValueError):self.do('resolveTransfer',requestIdToResolve=requests[0]['id'],accepted=True)
  self.do('resolveTransfer',token=self.tokens[0],requestIdToResolve=requests[0]['id'],accepted=True)
  self.do('resolveTransfer',token=self.tokens[1],requestIdToResolve=requests[1]['id'],accepted=False)
  self.assertEqual([p['score'] for p in self.saved()['players']],[1,-1,0]);self.assertEqual(len(self.saved()['transactions']),1)
 def test_pending_limit_no_partial_batch(self):
  for i in range(9):self.do('requestTransfer',id=self.ids[0],amount=1)
  before=self.saved()
  with self.assertRaises(ValueError):self.do('requestTransferAll',ids=self.ids,amount=1)
  self.assertEqual(self.saved(),before)
 def test_selected_group_gift_and_undo(self):
  self.do('transferAll',ids=self.ids[:1],rosterIds=self.ids,amount=3)
  self.assertEqual([p['score'] for p in self.saved()['players']],[-3,3,0])
  self.do('undo');self.assertEqual([p['score'] for p in self.saved()['players']],[0,0,0])
 def test_selected_collection_and_invalid_selection(self):
  before=self.saved()
  for ids in [[],[self.ids[0]]*2,[before['players'][0]['id']],['unknown']]:
   with self.assertRaises(ValueError):self.do('requestTransferAll',ids=ids,rosterIds=self.ids,amount=1)
   self.assertEqual(self.saved(),before)
  self.do('requestTransferAll',ids=self.ids[1:],rosterIds=self.ids,amount=1)
  requests=self.saved()['paymentRequests'];self.assertEqual([r['payer'] for r in requests],self.ids[1:])
  self.do('resolveTransfer',token=self.tokens[1],requestIdToResolve=requests[0]['id'],accepted=True)
  self.assertEqual([p['score'] for p in self.saved()['players']],[1,0,-1])
 def test_selected_group_rejects_stale_roster(self):
  self.do('join',token='',name='丁');before=self.saved()
  with self.assertRaises(ValueError):self.do('transferAll',ids=self.ids[:1],rosterIds=self.ids,amount=1)
  self.assertEqual(self.saved(),before)
 def test_non_host_can_give_to_every_other_player(self):
  ids=[p['id'] for p in self.saved()['players'] if p['id']!=self.ids[0]]
  self.do('transferAll',token=self.tokens[0],ids=ids,amount=1)
  self.assertEqual([p['score'] for p in self.saved()['players']],[1,-2,1])
 def test_pending_survives_reload_and_unrelated_actions_and_can_cancel(self):
  self.do('requestTransfer',id=self.ids[0],amount=1,requestId='pending-1')
  req=self.saved()['paymentRequests'][0]
  restored=Rooms(Repository(self.rooms.repo.path))
  for token in [self.host,self.tokens[0]]:
   self.assertEqual(restored.public(self.code,token,'invite')['paymentRequests'][0]['status'],'pending')
  self.do('transfer',id=self.ids[1],amount=2)
  self.do('undo')
  self.assertEqual(self.saved()['paymentRequests'][0],req)
  with self.assertRaises(ValueError):self.do('cancelTransferRequest',token=self.tokens[0],requestIdToResolve=req['id'])
  self.do('cancelTransferRequest',requestIdToResolve=req['id'],requestId='cancel-1')
  self.do('cancelTransferRequest',requestIdToResolve=req['id'],requestId='cancel-1')
  self.assertEqual(self.saved()['paymentRequests'][0]['status'],'cancelled')
  with self.assertRaises(ValueError):self.do('resolveTransfer',token=self.tokens[0],requestIdToResolve=req['id'],accepted=True)
  self.assertEqual([p['score'] for p in self.saved()['players']],[0,0,0])

 def test_public_requests_are_personal_even_for_host(self):
  self.do('requestTransfer',token=self.tokens[0],id=self.ids[1],amount=2)
  self.do('requestTransfer',id=self.ids[0],amount=1)
  saved=self.saved()['paymentRequests'];other,own=saved
  for token,expected in [(self.host,[own['id']]),(self.tokens[0],[other['id'],own['id']]),(self.tokens[1],[other['id']]),('',[])]:
   self.assertEqual([r['id'] for r in self.rooms.public(self.code,token,'invite')['paymentRequests']],expected)
  with self.assertRaises(ValueError):self.do('resolveTransfer',requestIdToResolve=other['id'],accepted=True)
  self.assertEqual(self.saved()['paymentRequests'],saved)

 def test_host_audio_feed_is_not_a_personal_todo_or_permission(self):
  self.do('requestTransfer',token=self.tokens[0],id=self.ids[1],amount=20,note='private note')
  req=self.saved()['paymentRequests'][0]
  host=self.rooms.public(self.code,self.host,'invite')
  self.assertEqual(host['paymentRequests'],[])
  self.assertEqual(host['soundRequests'][0]['id'],req['id'])
  self.assertNotIn('note',host['soundRequests'][0])
  for token in self.tokens:self.assertNotIn('soundRequests',self.rooms.public(self.code,token,'invite'))
  with self.assertRaises(ValueError):self.do('resolveTransfer',requestIdToResolve=req['id'],accepted=True)
  self.do('resolveTransfer',token=self.tokens[1],requestIdToResolve=req['id'],accepted=True)
  self.assertEqual(self.rooms.public(self.code,self.host,'invite')['soundRequests'][0]['status'],'accepted')

if __name__=='__main__':unittest.main()

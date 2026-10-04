import unittest,tempfile
from pathlib import Path
from scoring.repository import Repository
from scoring.rooms import Rooms
class RoomImprovements(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.rooms=Rooms(Repository(Path(self.tmp.name)/'test.sqlite3'))
  out=self.rooms.create(dict(game='zhajinhua',name='桌',nickname='A',config={}));self.code=out['room'];self.host=out['token'];self.tokens=[self.host]
  for name in ('B','C'):self.tokens.append(self.do('join',token='',name=name)['token'])
  self.ids=[p['id'] for p in self.s()['players']]
 def do(self,action,token=None,**data):return self.rooms.execute(self.code,dict(action=action,token=self.host if token is None else token,**data))
 def s(self):return self.rooms.repo.get(self.code)
 def start(self):
  for t in self.tokens:self.do('ready',token=t)
  self.do('start')
 def test_defaults_and_reorder(self):
  self.assertEqual((self.s()['config']['minCompare'],self.s()['config']['maxRounds']),(1,7))
  with self.assertRaises(ValueError):self.do('seating',token=self.tokens[1],ids=self.ids[::-1])
  before=self.s()
  with self.assertRaises(ValueError):self.do('seating',ids=[self.ids[0]]*3)
  self.assertEqual(before,self.s());self.do('seating',ids=self.ids[::-1]);self.start();self.assertEqual(self.s()['turn'],self.ids[2]);self.do('call',token=self.tokens[2]);self.assertEqual(self.s()['turn'],self.ids[1])
  with self.assertRaises(ValueError):self.do('seating',ids=self.ids)
 def test_fixed_and_winner_dealers(self):
  self.do('config',config={**self.s()['config'],'dealerMode':'fixed','designatedDealer':self.ids[1]});self.start();self.assertEqual(self.s()['dealer'],self.ids[1]);self.do('hostFold',id=self.ids[0]);self.do('hostFold',id=self.ids[1]);self.assertEqual(self.s()['lastWinner'],self.ids[2])
  self.do('config',config={**self.s()['config'],'dealerMode':'winner'});self.start();self.assertEqual(self.s()['turn'],self.ids[2]);self.do('cancel');self.do('config',config={**self.s()['config'],'dealerMode':'fixed'});self.start();self.assertEqual(self.s()['dealer'],self.ids[1])
 def test_rename_ownership_unique_and_preserved_records(self):
  self.start();self.do('call');old=self.s()['bets'][-1]['playerName'];self.do('rename',token=self.tokens[1],name='小乙',id=self.ids[0]);self.assertEqual(self.s()['players'][1]['name'],'小乙');self.assertEqual(self.s()['players'][0]['name'],'A')
  with self.assertRaises(ValueError):self.do('rename',name='小乙')
  with self.assertRaises(ValueError):self.do('rename',token='',name='x')
  self.assertEqual(self.s()['bets'][-1]['playerName'],old)
 def test_host_fold_out_of_turn_and_undo(self):
  self.start();before=self.s();self.do('hostFold',id=self.ids[2]);self.assertEqual(self.s()['turn'],self.ids[0]);self.assertFalse(self.s()['players'][2]['active']);self.do('undo');self.assertEqual(self.s()['players'],before['players'])
  with self.assertRaises(ValueError):self.do('hostFold',token=self.tokens[1],id=self.ids[0])
  self.do('hostFold',id=self.ids[0]);self.assertEqual(self.s()['turn'],self.ids[1]);self.do('hostFold',id=self.ids[1]);self.assertEqual(self.s()['phase'],'finished');self.do('undo');self.assertEqual(self.s()['phase'],'playing');self.assertEqual(self.rooms.repo.histories(self.code),[])
 def test_pending_comparison_host_fold(self):
  self.do('config',config={**self.s()['config'],'dealerMode':'fixed','designatedDealer':self.ids[0]})
  for loser in (0,1,2):
   if self.s()['phase']=='playing':self.do('cancel')
   self.start();self.do('compare',id=self.ids[1]);self.do('hostFold',id=self.ids[loser]);self.assertEqual(self.s()['pot'],40)
   if loser==2:self.assertEqual(self.s()['phase'],'comparing');self.do('resolve',id=self.ids[0])
   else:self.assertEqual(self.s()['phase'],'playing');self.assertIsNone(self.s()['pending'])
 def test_adjust_in_play_undo_and_seen_auto_cost(self):
  self.start();before=self.s();self.do('adjust',id=self.ids[1],score=500);self.assertEqual(self.s()['pot'],before['pot']);self.do('undo');self.assertEqual(self.s()['players'],before['players']);self.do('seen');self.do('compare',id=self.ids[1]);self.assertEqual(self.s()['bets'][-1]['amount'],20)
 def test_seat_stale_roster_and_dealer_config_invalid(self):
  before=self.s()
  for patch in ({'dealerMode':'bad'},{'designatedDealer':'unknown'}):
   with self.assertRaises(ValueError):self.do('config',config={**before['config'],**patch})
  self.assertEqual(self.s(),before)
 def test_bet_card_state_snapshot_survives_looking(self):
  self.start();self.do('call');self.assertEqual(self.s()['bets'][-1]['cardState'],'暗');self.do('seen')
  self.do('call',token=self.tokens[1]);self.do('call',token=self.tokens[2]);self.do('call');self.assertEqual(self.s()['bets'][-1]['cardState'],'明');self.assertEqual(self.s()['bets'][-1]['amount'],20);self.assertEqual(self.s()['bets'][3]['cardState'],'暗')
  reloaded=Rooms(Repository(self.rooms.repo.path));self.assertEqual(reloaded.repo.get(self.code)['bets'],self.s()['bets'])
 def test_compare_cost_follows_actor_not_target_default(self):
  self.start();self.do('seen',token=self.tokens[1]);self.do('compare',id=self.ids[1]);self.assertEqual((self.s()['bets'][-1]['amount'],self.s()['bets'][-1]['cardState']),(10,'暗'));self.do('undo')
  self.do('compare',id=self.ids[2]);self.assertEqual(self.s()['bets'][-1]['amount'],10);self.do('undo');self.do('seen')
  self.do('compare',id=self.ids[2]);self.assertEqual((self.s()['bets'][-1]['amount'],self.s()['bets'][-1]['cardState']),(20,'明'));self.do('undo');self.do('compare',id=self.ids[1]);self.assertEqual(self.s()['bets'][-1]['amount'],20)

 def test_room_rename_host_only_preserves_gameplay_and_undo(self):
  self.start();self.do('call');old=self.s();undo=old['undo']
  with self.assertRaises(ValueError):self.do('renameRoom',token=self.tokens[1],name='玩家改名')
  for name in ('','x'*25):
   with self.assertRaises(ValueError):self.do('renameRoom',name=name)
  self.do('renameRoom',name='新房间名')
  new=self.s();self.assertEqual(new['name'],'新房间名');self.assertEqual(new['undo'],undo)
  for key in ('players','pot','turn','round','hand','bets'):self.assertEqual(new[key],old[key])
  self.do('undo');self.assertEqual(self.s()['name'],'新房间名')
 def test_nickname_ten_character_limit_for_create_join_and_rename(self):
  ten='一二三四五六七八九十'
  self.do('rename',name=ten);self.assertEqual(self.s()['players'][0]['name'],ten)
  for action in ('rename','join'):
   with self.assertRaises(ValueError):self.do(action,token='' if action=='join' else self.host,name=ten+'一')
  for game in ('zhajinhua','mahjong'):
   with self.assertRaises(ValueError):self.rooms.create(dict(game=game,name='桌',nickname=ten+'一',config={}))
   out=self.rooms.create(dict(game=game,name='桌',nickname=ten,config={}))
   self.rooms.execute(out['room'],dict(action='renameRoom',token=out['token'],name='麻将也可改名'))
   self.assertEqual(self.rooms.repo.get(out['room'])['name'],'麻将也可改名')

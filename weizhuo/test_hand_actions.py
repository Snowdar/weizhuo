"""Public current-hand actions survive reload and follow undo, without log inference."""
import tempfile,unittest
from pathlib import Path
from scoring.rooms import Rooms
from scoring.repository import Repository
class HandActionTests(unittest.TestCase):
    def test_actions_undo_reload_and_new_hand(self):
        for game in ('holdem','zhajinhua'):
            with self.subTest(game=game),tempfile.TemporaryDirectory() as folder:
                rooms=Rooms(Repository(Path(folder)/'rooms.sqlite3'))
                created=rooms.create(dict(game=game,name='记录测试',nickname='A'))
                code,host=created['room'],created['token']
                for name in ('B','C'):
                    t=rooms.execute(code,dict(action='join',name=name))['token']
                    rooms.execute(code,dict(action='ready',token=t,ready=True))
                def state():return rooms.repo.get(code)
                def do(action,token=host,**data):return rooms.execute(code,dict(action=action,token=token,**data))
                def turn():return next(p for p in state()['players'] if p['id']==state()['turn'])['token']
                do('start')
                if game=='holdem':do('deal',stage='hole');do('raise',token=turn(),amount=30)
                else:do('seen',token=turn());do('call',token=turn(),amount=30)
                rows=state()['handActions'];self.assertEqual(rows[-1]['action'],'加注');self.assertEqual(rows[-1]['amount'],30)
                do('fold',token=turn());self.assertEqual(state()['handActions'][-1]['action'],'弃牌')
                do('undo');self.assertEqual(state()['handActions'],rows)
                public=Rooms(Repository(Path(folder)/'rooms.sqlite3')).public(code,'','')
                self.assertEqual(public['handActions'],rows);self.assertNotIn('token',str(rows))
                do('cancel');self.assertEqual(state()['handActions'],[])
                for p in state()['players']:
                    if p['id']!=state()['hostPlayer']:do('ready',token=p['token'],ready=True)
                do('start');self.assertEqual(state()['handActions'],[])
    def test_legacy_state_without_actions(self):
        from scoring.games.zhajinhua import Engine,fresh
        s=fresh();self.assertNotIn('handActions',s)
        e=Engine(s);e.record_action({'id':'a','name':'A'},'弃牌')
        self.assertEqual(s['handActions'][0]['playerName'],'A')

class IndependentPlayerPreferences(unittest.TestCase):
    def test_rename_does_not_erase_action_undo_or_restore_old_nickname(self):
        for game in ('holdem','zhajinhua','mahjong'):
            with self.subTest(game=game),tempfile.TemporaryDirectory() as folder:
                rooms=Rooms(Repository(Path(folder)/'rooms.sqlite3'))
                c=rooms.create(dict(game=game,name='偏好测试',nickname='甲'));code,host=c['room'],c['token']
                other=rooms.execute(code,dict(action='join',name='乙'))['token']
                def do(action,token=host,**d):return rooms.execute(code,dict(action=action,token=token,**d))
                def state():return rooms.repo.get(code)
                pid=state()['players'][1]['id']
                if game=='mahjong':do('transfer',id=pid,amount=5)
                else:
                    do('ready',token=other,ready=True);do('start')
                    if game=='holdem':do('deal',stage='hole')
                    turn=next(p['token'] for p in state()['players'] if p['id']==state()['turn'])
                    do('call',token=turn,**({'amount':10} if game=='zhajinhua' else {}))
                before=state();do('rename',token=other,name='新昵称')
                self.assertEqual(state()['undo'],before['undo'])
                do('undo');self.assertEqual(state()['players'][1]['name'],'新昵称')
                self.assertEqual(state()['pot'],before['undo'][-1]['state']['pot'])

    def test_adjust_honors_auto_ready_without_resetting_other_players(self):
        for game in ('holdem','zhajinhua'):
            with self.subTest(game=game),tempfile.TemporaryDirectory() as folder:
                rooms=Rooms(Repository(Path(folder)/'rooms.sqlite3'))
                c=rooms.create(dict(game=game,name='准备测试',nickname='甲'));code,host=c['room'],c['token']
                tokens=[rooms.execute(code,dict(action='join',name=name))['token'] for name in ('乙','丙')]
                def do(action,token=host,**d):return rooms.execute(code,dict(action=action,token=token,**d))
                def state():return rooms.repo.get(code)
                do('autoReady',token=tokens[0],enabled=True);do('ready',token=tokens[1],ready=True)
                pid=state()['players'][1]['id'];do('adjust',id=pid,score=1200)
                self.assertTrue(state()['players'][1]['autoReady']);self.assertTrue(state()['players'][1]['ready']);self.assertTrue(state()['players'][2]['ready'])
                if game=='holdem':
                    do('adjust',id=pid,score=0);self.assertFalse(state()['players'][1]['ready']);self.assertTrue(state()['players'][1]['autoReady'])
                    do('adjust',id=pid,score=100);self.assertTrue(state()['players'][1]['ready'])
                do('start')

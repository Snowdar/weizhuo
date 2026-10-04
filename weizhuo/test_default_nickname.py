from pathlib import Path
import tempfile,unittest
from scoring.repository import Repository
from scoring.rooms import Rooms

class DefaultNicknameTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'rooms.sqlite3';self.rooms=Rooms(Repository(self.path))
    def test_profile_survives_restart_without_rooms_and_isolated_identity(self):
        key='a'*32;other='b'*32
        self.assertEqual(self.rooms.device_nickname(key),'')
        self.assertEqual(self.rooms.device_nickname(key,'  常用昵称  '),'常用昵称')
        restored=Rooms(Repository(self.path))
        self.assertEqual(restored.device_nickname(key),'常用昵称')
        self.assertEqual(restored.device_nickname(other),'')
        self.assertEqual(restored.device_nickname(key,''),'')
    def test_invalid_profile_cannot_overwrite_saved_name(self):
        key='a'*32;self.rooms.device_nickname(key,'小明')
        for value in ['字'*11,123,[]]:
            with self.assertRaises(ValueError):self.rooms.device_nickname(key,value)
        with self.assertRaises(ValueError):self.rooms.device_nickname('invalid','名字')
        self.assertEqual(self.rooms.device_nickname(key),'小明')
    def test_duplicate_join_suffix_all_games_preserves_identity(self):
        for game in ('mahjong','zhajinhua','holdem'):
            with self.subTest(game=game):
                out=self.rooms.create(dict(game=game,name='测试桌',nickname='小明',config={}))
                for _ in range(4):self.rooms.execute(out['room'],dict(action='join',name='小明'))
                state=self.rooms.room(out['room'])
                self.assertEqual([p['name'] for p in state['players']],['小明','小明A','小明B','小明C','小明D'])
                self.assertEqual(len({p['token'] for p in state['players']}),5)
                self.assertEqual(state['host'],out['token'])
    def test_long_names_and_reserved_suffixes(self):
        name='一二三四五六七八九十'
        out=self.rooms.create(dict(game='mahjong',name='桌',nickname=name,config={}))
        self.rooms.execute(out['room'],dict(action='join',name=name[:9]+'A'))
        result=self.rooms.execute(out['room'],dict(action='join',name=name))
        names=[p['name'] for p in self.rooms.room(out['room'])['players']]
        self.assertEqual(names[-1],name[:9]+'B');self.assertTrue(all(len(n)<=10 for n in names))
        self.assertIn(names[-1],result['message'])
    def test_default_change_does_not_rename_seated_player(self):
        key='a'*32;self.rooms.device_nickname(key,'小明')
        out=self.rooms.create(dict(game='mahjong',name='桌',nickname='小明',config={}))
        self.rooms.device_rooms(key,[dict(room=out['room'],token=out['token'])])
        self.rooms.device_nickname(key,'小张')
        self.assertEqual(self.rooms.device_rooms(key)[0]['playerName'],'小明')

if __name__=='__main__':unittest.main()

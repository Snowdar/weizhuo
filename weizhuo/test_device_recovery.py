import secrets
import tempfile
import unittest
import threading,json
from http.cookiejar import CookieJar
from urllib.request import build_opener,HTTPCookieProcessor,Request
from pathlib import Path
from scoring.repository import Repository
from scoring.rooms import Rooms
from http.server import ThreadingHTTPServer
from server import Handler


class DeviceRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'rooms.sqlite3'
        self.rooms=Rooms(Repository(self.path));self.secret=secrets.token_urlsafe(32)
        self.host=self.rooms.create(dict(game='zhajinhua',name='朋友桌',nickname='房主',config={}))

    def test_restore_persistent_host_without_browser_room_list(self):
        self.rooms.device_rooms(self.secret,[self.host])
        restored=Rooms(Repository(self.path)).device_rooms(self.secret)
        self.assertEqual(restored,[{**self.host,'name':'朋友桌','isHost':True,'game':'zhajinhua','gameName':'炸金花','phase':'lobby','hand':0,'playerName':'房主'}])

    def test_other_device_cannot_claim_room(self):
        self.rooms.device_rooms(self.secret,[self.host])
        other=secrets.token_urlsafe(32)
        self.assertEqual(self.rooms.device_rooms(other),[])
        self.assertEqual(self.rooms.device_rooms(other,[dict(room=self.host['room'],token='invalid')]),[])

    def test_player_restore_and_removal(self):
        token=self.rooms.execute(self.host['room'],dict(action='join',room=self.host['room'],name='玩家'))['token']
        recovered=self.rooms.device_rooms(self.secret,[dict(room=self.host['room'],token=token)])
        self.assertFalse(recovered[0]['isHost'])
        state=self.rooms.repo.get(self.host['room']);pid=next(p['id'] for p in state['players'] if p['token']==token)
        self.rooms.execute(self.host['room'],dict(action='remove',token=self.host['token'],id=pid))
        self.assertEqual(self.rooms.device_rooms(self.secret),[])

    def test_player_identity_scores_survive_device_return_until_explicit_leave(self):
        code=self.host['room']
        token=self.rooms.execute(code,dict(action='join',name='返回玩家'))['token']
        self.rooms.device_rooms(self.secret,[dict(room=code,token=token)])
        player=next(p for p in self.rooms.repo.get(code)['players'] if p['token']==token)
        self.rooms.execute(code,dict(action='adjust',token=self.host['token'],id=player['id'],score=1370))
        returned=Rooms(Repository(self.path))
        restored=returned.device_rooms(self.secret)[0]
        snapshot=returned.public(code,restored['token'],'invite')
        self.assertEqual(snapshot['me'],player['id'])
        self.assertEqual(next(p['score'] for p in snapshot['players'] if p['id']==snapshot['me']),1370)
        returned.execute(code,dict(action='leave',token=restored['token']))
        self.assertEqual(returned.device_rooms(self.secret),[])
        self.assertIsNone(returned.public(code,token,'invite')['me'])

    def test_destroyed_room_never_restored(self):
        self.rooms.device_rooms(self.secret,[self.host])
        self.rooms.execute(self.host['room'],dict(action='destroy',token=self.host['token']))
        self.assertEqual(self.rooms.device_rooms(self.secret),[])

    def test_invalid_device_id(self):
        for value in ('predictable',None,False,'x'*129):
            with self.assertRaises(ValueError):self.rooms.device_rooms(value)

    def test_cookie_recovers_without_local_room_list_and_isolates_clients(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.rooms=self.rooms
        server.test_rooms=Rooms(Repository(Path(self.tmp.name)/'test.sqlite3'))
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        jar=CookieJar();client=build_opener(HTTPCookieProcessor(jar))
        base='http://127.0.0.1:'+str(server.server_port)
        def post(opener,path,data):
            with opener.open(Request(base+path,json.dumps(data).encode(),{'Content-Type':'application/json'})) as response:return json.load(response)
        try:
            first=post(client,'/api/device',{})
            room=post(client,'/api/rooms',dict(game='zhajinhua',name='新桌',nickname='主人',config={},deviceKey=first['deviceKey']))
            # New opener, same persisted browser cookie; no JS room/device storage.
            returned=post(build_opener(HTTPCookieProcessor(jar)),'/api/device',{})
            self.assertEqual(returned['rooms'],[{**room,'name':'新桌','isHost':True,'game':'zhajinhua','gameName':'炸金花','phase':'lobby','hand':0,'playerName':'主人'}])
            self.assertEqual(post(build_opener(),'/api/device',{})['rooms'],[])
            self.assertEqual(post(client,'/test/api/device',{})['rooms'],[])
            player_jar=CookieJar();player_client=build_opener(HTTPCookieProcessor(player_jar))
            device=post(player_client,'/api/device',{})
            joined=post(player_client,'/api/action',dict(action='join',room=room['room'],name='扫码玩家',deviceKey=device['deviceKey']))
            restored=post(build_opener(HTTPCookieProcessor(player_jar)),'/api/device',{})['rooms']
            self.assertEqual(restored,[dict(room=room['room'],token=joined['token'],name='新桌',isHost=False,game='zhajinhua',gameName='炸金花',phase='lobby',hand=0,playerName='扫码玩家')])
            with player_client.open(base+'/identity-qr.png?room='+room['room']+'&token='+joined['token']) as image:
                self.assertEqual(image.read()[:8],b'\x89PNG\r\n\x1a\n')
            from urllib.error import HTTPError
            with self.assertRaises(HTTPError) as rejected:player_client.open(base+'/identity-qr.png?room='+room['room']+'&token=invalid')
            self.assertEqual(rejected.exception.code,404)
            post(player_client,'/api/action',dict(action='leave',room=room['room'],token=joined['token']))
            self.assertEqual(post(player_client,'/api/device',{})['rooms'],[])
        finally:
            server.shutdown();server.server_close();worker.join()


if __name__=='__main__':unittest.main()

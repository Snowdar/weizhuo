"""Hall identity QR works before room creation and restores room memberships."""
from contextlib import closing
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer
from pathlib import Path
import json,tempfile,threading,unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit,parse_qs
from urllib.request import build_opener,HTTPCookieProcessor,Request
from server import Handler
from scoring.rooms import Rooms
from scoring.repository import Repository

class HallIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.rooms=Rooms(Repository(Path(self.tmp.name)/'main.sqlite3'))
        self.server.test_rooms=Rooms(Repository(Path(self.tmp.name)/'test.sqlite3'))
        self.worker=threading.Thread(target=self.server.serve_forever,daemon=True);self.worker.start();self.addCleanup(self.stop)
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        self.client=build_opener(HTTPCookieProcessor(CookieJar()))
    def stop(self):self.server.shutdown();self.server.server_close();self.worker.join()
    def post(self,path,data,client=None):
        with (client or self.client).open(Request(self.base+path,json.dumps(data).encode(),{'Content-Type':'application/json'})) as response:return json.load(response)
    def test_qr_before_join_then_cross_browser_restore_all_rooms(self):
        identity=self.post('/api/device',{});key=identity['deviceKey'];self.assertEqual(identity['rooms'],[])
        with self.client.open(self.base+'/device-identity-qr.png?key='+key) as image:self.assertEqual(image.read()[:8],b'\x89PNG\r\n\x1a\n')
        with patch('server.qr_png',return_value=b'png') as qr:
            with self.client.open(self.base+'/device-identity-qr.png?key='+key):pass
            url=qr.call_args.args[0]
        parsed=urlsplit(url);self.assertNotIn('room',parse_qs(parsed.query));self.assertEqual(parse_qs(parsed.fragment),{'device':[key]})
        a=self.post('/api/rooms',dict(game='holdem',name='德州桌',nickname='甲',config={},deviceKey=key))
        b=self.post('/api/rooms',dict(game='mahjong',name='原麻将桌',nickname='甲',config={},deviceKey=key))
        other=build_opener(HTTPCookieProcessor(CookieJar()))
        stranger=self.post('/api/device',{},other);self.assertEqual(stranger['rooms'],[])
        restored=self.post('/api/device',{'deviceKey':parse_qs(parsed.fragment)['device'][0]},other)
        self.assertEqual({x['room'] for x in restored['rooms']},{a['room'],b['room']})
        self.assertEqual({x['gameName'] for x in restored['rooms']},{'德州扑克','自由记分'})
        self.assertTrue(all('phase' in x and 'playerName' in x for x in restored['rooms']))
        self.assertEqual(self.post('/test/api/device',{'deviceKey':key},other)['rooms'],[])
    def test_nickname_cross_browser_restoration_and_test_isolation(self):
        identity=self.post('/api/device',{'nickname':'  小明  '});key=identity['deviceKey']
        self.assertEqual(identity['nickname'],'小明')
        other=build_opener(HTTPCookieProcessor(CookieJar()))
        self.assertEqual(self.post('/api/device',{'deviceKey':key},other)['nickname'],'小明')
        self.assertEqual(self.post('/test/api/device',{'deviceKey':key},other)['nickname'],'')
        with self.assertRaises(HTTPError) as error:self.post('/api/device',{'nickname':'字'*11})
        self.assertEqual(error.exception.code,400)
        self.assertEqual(self.post('/api/device',{})['nickname'],'小明')

    def test_invalid_qr_key_and_test_device_override_cookie(self):
        identity=self.post('/test/api/device',{})
        room=self.post('/test/api/rooms',dict(game='holdem',name='桌',nickname='甲',config={},deviceKey=identity['deviceKey']))
        simulated=self.post('/test/api/device',{'deviceKey':'b'*64})
        self.assertNotEqual(simulated['deviceKey'],identity['deviceKey']);self.assertEqual(simulated['rooms'],[])
        self.assertEqual(self.post('/test/api/device',{'deviceKey':identity['deviceKey']})['rooms'][0]['room'],room['room'])
        with self.assertRaises(HTTPError) as error:self.client.open(self.base+'/device-identity-qr.png?key=invalid')
        self.assertEqual(error.exception.code,404)

if __name__=='__main__':unittest.main()

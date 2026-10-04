import unittest,tempfile,threading,json,sqlite3
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.error import HTTPError
from http.cookiejar import CookieJar
from scoring.rooms import Rooms
from scoring.repository import Repository
from server import Handler,app_version
class AdminTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.rooms=Rooms(Repository(Path(self.tmp.name)/'main.sqlite3'))
  self.test=Rooms(Repository(Path(self.tmp.name)/'test.sqlite3'))
  self.created=self.rooms.create(dict(game='zhajinhua',name='管理员测试房',nickname='房主',config={}))
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.rooms=self.rooms;self.server.test_rooms=self.test;self.server.app_version=app_version()
  self.worker=threading.Thread(target=self.server.serve_forever,daemon=True);self.worker.start();self.addCleanup(self.shutdown)
  self.base='http://127.0.0.1:'+str(self.server.server_port)
  self.client=build_opener(HTTPCookieProcessor(CookieJar()))
 def shutdown(self):self.server.shutdown();self.server.server_close();self.worker.join()
 def api(self,path,data=None,client=None):
  req=Request(self.base+path,None if data is None else json.dumps(data).encode(),{'Content-Type':'application/json'})
  with (client or self.client).open(req) as r:return json.load(r)
 def test_bootstrap_admin_entry_visibility(self):
  self.assertTrue(self.api('/api/bootstrap')['isServiceDevice'])
  self.assertTrue(self.api('/test/api/bootstrap')['isServiceDevice'])
  from unittest.mock import patch
  with patch.object(Handler,'is_service_device_request',return_value=False):
   self.assertFalse(self.api('/api/bootstrap')['isServiceDevice'])
 def test_service_device_detects_self_lan_and_rejects_other_players(self):
  from types import SimpleNamespace
  from unittest.mock import Mock
  def check(peer,local,host):
   h=SimpleNamespace(client_address=(peer,12345),connection=Mock(),headers={'Host':host})
   h.connection.getsockname.return_value=(local,8765)
   return Handler.is_service_device_request(h)
  self.assertTrue(check('127.0.0.1','127.0.0.1','localhost:8765'))
  self.assertTrue(check('192.168.1.20','192.168.1.20','192.168.1.20:8765'))
  self.assertFalse(check('192.168.1.21','192.168.1.20','192.168.1.20:8765'))
  self.assertFalse(check('192.168.1.21','192.168.1.20','localhost:8765'))
  self.assertFalse(check('127.0.0.1','127.0.0.1','remote.example:8765'))
 def test_auth_listing_namespace_logout(self):
  for path,data,status in [('/api/admin/rooms',None,401),('/api/admin/clear',{},401),('/api/admin/login',dict(code='wrong'),403)]:
   with self.assertRaises(HTTPError) as e:self.api(path,data)
   self.assertEqual(e.exception.code,status)
  self.api('/api/admin/login',dict(code='1234'))
  rooms=self.api('/api/admin/rooms')['rooms'];self.assertEqual(len(rooms),1)
  self.assertNotIn('token',rooms[0]);self.assertNotIn(self.created['token'],json.dumps(rooms))
  with self.assertRaises(HTTPError):self.api('/test/api/admin/rooms')
  self.api('/api/admin/logout',{})
  with self.assertRaises(HTTPError):self.api('/api/admin/rooms')
 def test_clear_active_room_backup_version_and_other_rooms(self):
  code=self.created['room'];host=self.created['token']
  other=self.rooms.create(dict(game='mahjong',name='不受影响',nickname='其他房主',config={}))
  guest=self.rooms.execute(code,dict(action='join',name='玩家'))['token']
  for t in [host,guest]:self.rooms.execute(code,dict(action='ready',token=t))
  self.rooms.execute(code,dict(action='start',token=host))
  before=self.rooms.repo.get(code);other_before=self.rooms.repo.get(other['room'])
  self.api('/api/admin/login',dict(code='1234'))
  for version,confirm in [(before['version']-1,code),(before['version'],'wrong')]:
   with self.assertRaises(HTTPError):self.api('/api/admin/clear',dict(room=code,version=version,confirmRoom=confirm))
  self.assertEqual(self.rooms.repo.get(code),before)
  self.api('/api/admin/clear',dict(room=code,version=before['version'],confirmRoom=code))
  with self.assertRaises(ValueError):self.rooms.room(code)
  self.assertEqual(self.rooms.repo.get(other['room']),other_before)
  backup=next((Path(self.tmp.name)/'backups').glob('*.sqlite3'))
  with sqlite3.connect(backup) as db:saved=json.loads(db.execute('SELECT data FROM rooms WHERE code=?',(code,)).fetchone()[0])
  self.assertEqual(saved,before)
 def test_batch_clear_requires_confirmation_and_rejects_stale_selection(self):
  other=self.rooms.create(dict(game='mahjong',name='第二桌',nickname='甲',config={}))
  items=[dict(room=x['room'],version=self.rooms.repo.get(x['room'])['version']) for x in [self.created,other]]
  before=[self.rooms.repo.get(x['room']) for x in items]
  self.api('/api/admin/login',dict(code='1234'))
  for payload in [dict(rooms=items),dict(rooms=items,confirmed=False),dict(rooms=[items[0],{**items[1],'version':-1}],confirmed=True),dict(rooms=[items[0],items[0]],confirmed=True)]:
   with self.assertRaises(HTTPError):self.api('/api/admin/clear',payload)
  self.assertEqual([self.rooms.repo.get(x['room']) for x in items],before)
  out=self.api('/api/admin/clear',dict(rooms=items,confirmed=True));self.assertEqual(set(out['rooms']),{x['room'] for x in items})
  for x in items:
   with self.assertRaises(ValueError):self.rooms.room(x['room'])
  backup=next((Path(self.tmp.name)/'backups').glob('*.sqlite3'))
  with sqlite3.connect(backup) as db:
   saved={code:json.loads(raw) for code,raw in db.execute('SELECT code,data FROM rooms')}
  self.assertEqual([saved[x['room']] for x in items],before)
 def test_batch_rollback_on_storage_failure(self):
  from unittest.mock import patch
  other=self.rooms.create(dict(game='mahjong',name='第二桌',nickname='甲',config={}))
  items=[dict(room=x['room'],version=self.rooms.repo.get(x['room'])['version']) for x in [self.created,other]]
  before=[self.rooms.repo.get(x['room']) for x in items];save=self.rooms.repo.save;calls=0
  def failing_save(*args,**kwargs):
   nonlocal calls
   calls+=1
   if calls==2:raise RuntimeError('storage failed')
   return save(*args,**kwargs)
  with patch.object(self.rooms.repo,'save',side_effect=failing_save):
   with self.assertRaises(RuntimeError):self.rooms.admin_clear_many(items,True)
  self.assertEqual([self.rooms.repo.get(x['room']) for x in items],before)
 def test_password_change_persists_and_invalidates_old_sessions(self):
  self.api('/api/admin/login',dict(code='1234'));self.api('/test/api/admin/login',dict(code='1234'))
  for data in [dict(currentPassword='wrong',newPassword='test-secret',confirmPassword='test-secret'),dict(currentPassword='1234',newPassword='test-secret',confirmPassword='different'),dict(currentPassword='1234',newPassword='1',confirmPassword='1')]:
   with self.assertRaises(HTTPError):self.api('/api/admin/password',data)
  self.api('/api/admin/password',dict(currentPassword='1234',newPassword='test-secret',confirmPassword='test-secret'))
  with self.assertRaises(HTTPError):self.api('/api/admin/rooms')
  self.api('/test/api/admin/rooms') # Other namespace session remains valid.
  with self.assertRaises(HTTPError):self.api('/api/admin/login',dict(code='1234'))
  self.api('/api/admin/login',dict(code='test-secret'))
  self.assertTrue(Repository(self.rooms.repo.path).admin_password_matches('test-secret','1234'))
  with self.rooms.repo.connect() as db:self.assertNotIn('test-secret',repr(db.execute('SELECT * FROM admin_credentials').fetchall()))
 def test_local_reset_requires_confirmation_and_preserves_rooms(self):
  self.api('/api/admin/login',dict(code='1234'))
  self.api('/api/admin/password',dict(currentPassword='1234',newPassword='reset-test',confirmPassword='reset-test'))
  before=self.rooms.repo.get(self.created['room']);settings=self.api('/api/admin/settings');self.assertTrue(settings['canReset']);self.assertTrue(settings['passwordChanged'])
  with self.assertRaises(HTTPError):self.api('/api/admin/reset',{})
  request=Request(self.base+'/api/admin/reset',json.dumps(dict(confirmed=True)).encode(),{'Content-Type':'application/json','Host':'remote.example'})
  with self.assertRaises(HTTPError) as e:self.client.open(request)
  self.assertEqual(e.exception.code,403)
  from unittest.mock import patch
  with patch.object(Handler,'local_admin_reset',return_value=False):
   with self.assertRaises(HTTPError) as e:self.api('/api/admin/reset',dict(confirmed=True))
   self.assertEqual(e.exception.code,403)
  self.api('/api/admin/reset',dict(confirmed=True));self.api('/api/admin/login',dict(code='1234'))
  self.assertEqual(self.rooms.repo.get(self.created['room']),before)
  self.assertFalse(self.api('/api/admin/settings')['passwordChanged'])
 def test_password_change_requires_auth_and_reset_uses_configured_initial(self):
  with self.assertRaises(HTTPError) as e:self.api('/api/admin/password',dict(currentPassword='1234',newPassword='test-secret',confirmPassword='test-secret'))
  self.assertEqual(e.exception.code,401)
  from unittest.mock import patch
  with patch.dict('os.environ',{'SCOREBOARD_ADMIN_CODE':'configured-test'}):
   self.api('/api/admin/login',dict(code='configured-test'));self.api('/api/admin/password',dict(currentPassword='configured-test',newPassword='another-test',confirmPassword='another-test'))
   self.api('/api/admin/reset',dict(confirmed=True));self.api('/api/admin/login',dict(code='configured-test'))
   self.assertTrue(self.api('/api/admin/settings')['configuredInitial'])
if __name__=='__main__':unittest.main()

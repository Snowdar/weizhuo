"""LAN self-check is never evidence of reachability from another device."""
import json,tempfile,threading,time,unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from server import make_server,network_probe,network_check,Handler

class NetworkCheckTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.server=make_server(0,data_dir=self.tmp.name,bind='127.0.0.1',lan_address='127.0.0.1')
  thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
  self.addCleanup(lambda:(self.server.shutdown(),self.server.server_close(),thread.join()))
  self.base=f'http://127.0.0.1:{self.server.server_port}'
 def get(self,path):return urlopen(self.base+path,timeout=4)
 def begin(self,prefix='/'):
  with urlopen(Request(self.base+prefix+'api/network-check',data=b'{}',headers={'Content-Type':'application/json'}),timeout=5) as response:
   self.assertEqual(response.headers['Cache-Control'],'no-store');return json.load(response)
 def test_local_success_does_not_claim_remote_connectivity(self):
  result=self.begin();self.assertTrue(result['loopback']);self.assertTrue(result['lan']);self.assertFalse(result['peer'])
  with self.get('/network-check?check='+result['check']) as response:
   self.assertIn('服务设备自身访问',response.read().decode())
  with self.get('/api/network-check?check='+result['check']) as response:self.assertFalse(json.load(response)['peer'])
  with self.get('/network-check-qr.png?check='+result['check']) as response:self.assertEqual(response.read()[:8],b'\x89PNG\r\n\x1a\n')
 def test_remote_scan_and_host_only_status(self):
  result=self.begin()
  # Simulate the peer address supplied by the TCP socket, never trust HTTP headers.
  def remote(handler):handler.client_address=('192.168.1.55',23456);return False
  with patch.object(Handler,'is_service_device_request',remote):
   with self.get('/network-check?check='+result['check']) as response:self.assertIn('连接成功',response.read().decode())
   for path in ['/api/network-check?check='+result['check'],'/network-check-qr.png?check='+result['check']]:
    with self.assertRaises(HTTPError) as error:self.get(path)
    self.assertEqual(error.exception.code,403)
   with self.assertRaises(HTTPError) as error:self.begin()
   self.assertEqual(error.exception.code,403)
  self.assertTrue(network_check(self.server,result['check'])['peer'])
 def test_expired_and_changed_address_checks_cannot_confirm(self):
  result=self.begin();key=result['check']
  self.server.network_checks[key]['created']=time.monotonic()-181
  with self.assertRaises(ValueError):network_check(self.server,key)
  self.server.network_checks[key]['created']=time.monotonic();self.server.lan_address='192.168.2.10'
  with self.assertRaises(ValueError):network_check(self.server,key)
 def test_proxy_is_bypassed_and_wrong_service_is_rejected(self):
  with patch('server.build_opener') as factory:
   response=factory.return_value.open.return_value.__enter__.return_value
   response.read.return_value=b'{"instance":"another-service"}'
   self.assertFalse(network_probe(self.server,'127.0.0.1'))
   self.assertEqual(factory.call_args.args[0].proxies,{})
   self.assertEqual(factory.return_value.open.call_args.kwargs['timeout'],2)
 def test_test_space_invitation_and_no_room_changes(self):
  result=self.begin('/test/');self.assertIn('/test/network-check?',result['url'])
  self.assertEqual(self.server.rooms.repo.active_count(),0);self.assertEqual(self.server.test_rooms.repo.active_count(),0)
  for _ in range(10):self.begin()
  self.assertLessEqual(len(self.server.network_checks),8)

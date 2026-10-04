import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from urllib.request import urlopen,Request
APP=Path(__file__).parent
sys.path.insert(0,str(APP/'mobile/src'))
spec=importlib.util.spec_from_file_location('mobile_host',APP/'mobile/src/weizhuomobile/host.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class MobileHostTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.host=module.Host(APP,Path(self.tmp.name));self.addCleanup(self.host.stop)
 def request(self,path,data=None):
  url=f'http://127.0.0.1:{self.host.server.server_port}/{path}'
  with urlopen(Request(url,data=json.dumps(data).encode() if data else None,headers={'Content-Type':'application/json'}),timeout=3) as response:return response.read()
 def test_mobile_address_and_readonly_assets(self):
  self.host.start('192.168.1.20',0)
  state=json.loads(self.request('api/bootstrap'));self.assertEqual(state['entry'],f'http://192.168.1.20:{self.host.server.server_port}/')
  self.assertEqual(state['serviceDevice'],'phone')
  self.assertIn(b'<!doctype html>',self.request(''))
  self.host.update_address('192.168.1.21');self.assertIn('192.168.1.21',json.loads(self.request('api/bootstrap'))['entry'])
  with self.assertRaises(ValueError):self.host.start('192.168.1.20',0)
 def test_restart_preserves_room_in_private_directory(self):
  self.host.start('192.168.1.20',0)
  created=json.loads(self.request('api/rooms',dict(game='mahjong',name='手机测试',nickname='甲',config={})))
  self.host.stop();self.host.start('192.168.1.20',0)
  state=json.loads(self.request('api/state?room='+created['room']+'&token='+created['token']))
  self.assertEqual(state['players'][0]['name'],'甲');self.assertTrue((Path(self.tmp.name)/'scoreboard.sqlite3').exists())
 def test_default_port_is_assigned_without_colliding(self):
  first_url=self.host.start('192.168.1.20')
  other=module.Host(APP,Path(self.tmp.name)/'second');self.addCleanup(other.stop)
  second_url=other.start('192.168.1.21')
  self.assertGreater(self.host.server.server_port,0);self.assertGreater(other.server.server_port,0)
  self.assertNotEqual(self.host.server.server_port,other.server.server_port)
  self.assertEqual(first_url,f'http://192.168.1.20:{self.host.server.server_port}/')
  self.assertEqual(second_url,f'http://192.168.1.21:{other.server.server_port}/')
 def test_android_sourceless_server_entry(self):
  import py_compile,shutil
  resources=Path(self.tmp.name)/'compiled-runtime';resources.mkdir()
  for name in ('scoring','vendor','static'):shutil.copytree(APP/name,resources/name)
  py_compile.compile(str(APP/'server.py'),cfile=str(resources/'server.pyc'),doraise=True)
  host=module.Host(resources,Path(self.tmp.name)/'android-data');self.addCleanup(host.stop)
  host.start('192.168.1.20')
  with urlopen(f'http://127.0.0.1:{host.server.server_port}/api/bootstrap',timeout=3) as response:
   self.assertEqual(json.loads(response.read())['serviceDevice'],'phone')
 def test_non_private_address_assigned_to_local_wifi(self):
  from unittest.mock import patch
  with patch('weizhuomobile.network.wifi_address',return_value='172.40.4.86'):
   self.assertEqual(module.validate_wifi_address('172.40.4.86'),'172.40.4.86')
   with self.assertRaises(ValueError):module.validate_wifi_address('8.8.8.8')
 def test_reject_non_wifi_address(self):
  for value in ['127.0.0.1','0.0.0.0','8.8.8.8','169.254.1.1','::1','not-an-ip']:
   with self.assertRaises(ValueError):module.validate_wifi_address(value)

class MobileLocaleTests(unittest.TestCase):
 def setUp(self):
  spec=importlib.util.spec_from_file_location('mobile_bootstrap',APP/'mobile/src/weizhuomobile/bootstrap.py')
  self.bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.bootstrap)
 def test_unsupported_phone_locale_falls_back_before_toga(self):
  from unittest.mock import patch
  with patch.dict(self.bootstrap.os.environ,{'LC_ALL':'zh_CN_unsupported'}),patch.object(self.bootstrap.locale,'setlocale',side_effect=[self.bootstrap.locale.Error('unsupported locale'),'C']):
   self.bootstrap.prepare_locale();self.assertEqual(self.bootstrap.os.environ['LC_ALL'],'C')
 def test_supported_locale_preserves_user_environment(self):
  from unittest.mock import patch
  with patch.dict(self.bootstrap.os.environ,{'LC_ALL':'C.UTF-8'}),patch.object(self.bootstrap.locale,'setlocale',return_value='C.UTF-8'):
   self.bootstrap.prepare_locale();self.assertEqual(self.bootstrap.os.environ['LC_ALL'],'C.UTF-8')


class MobileNetworkTests(unittest.TestCase):
 def setUp(self):
  spec=importlib.util.spec_from_file_location('weizhuomobile.network',APP/'mobile/src/weizhuomobile/network.py')
  self.network=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.network)
 def test_android_reporting_linux_still_detects_wifi(self):
  from unittest.mock import patch,Mock
  import types
  address=Mock();address.getHostAddress.return_value='192.168.1.25'
  interface=Mock();interface.isUp.return_value=True;interface.getName.return_value='wlan0'
  # Direct Enumeration dispatch fails on the actual Mate 60 runtime.
  iterator=Mock();iterator.nextElement.side_effect=NotImplementedError('abstract')
  native=Mock();native.getNetworkInterfaces.return_value=iterator
  collections=Mock();collections.list.side_effect=[Mock(toArray=Mock(return_value=[interface])),Mock(toArray=Mock(return_value=[address]))]
  java=types.ModuleType('java');java.jclass=Mock(side_effect=lambda name:collections if name=='java.util.Collections' else native)
  with patch.object(sys,'platform','linux'),patch.object(sys,'getandroidapilevel',return_value=31,create=True),patch.dict(sys.modules,{'java':java}):
   self.assertEqual(self.network.wifi_address(),'192.168.1.25')
   iterator.nextElement.assert_not_called()
 def test_lost_wifi_selects_hotspot_and_return_restores_wifi_choice(self):
  state=self.network.service_network_state
  self.assertEqual(state('172.40.4.86','','同一 Wi-Fi'),('同一 Wi-Fi',True,'172.40.4.86'))
  self.assertEqual(state('','','同一 Wi-Fi'),('本机热点',False,''))
  self.assertEqual(state('','172.20.10.1','同一 Wi-Fi'),('本机热点',False,'172.20.10.1'))
  self.assertEqual(state('192.168.1.8','','本机热点'),('本机热点',True,''))
 def test_local_wifi_non_private_subnet(self):
  self.assertEqual(self.network.select_address([('en0','172.40.4.86'),('pdp_ip0','10.36.96.189')]),'172.40.4.86')
 def test_additional_local_en_interfaces_exclude_vpn_and_cellular(self):
  self.assertEqual(self.network.select_address([('en2','192.168.1.8'),('utun0','10.1.1.1'),('pdp_ip0','10.0.0.2')]),'192.168.1.8')
 def test_hotspot_mode_prefers_actual_bridge_over_wifi_client(self):
  interfaces=[('en0','192.168.1.20'),('bridge100','172.20.10.1'),('pdp_ip0','10.0.0.2'),('utun0','10.1.1.1')]
  self.assertEqual(self.network.select_address(interfaces),'192.168.1.20')
  self.assertEqual(self.network.select_address(interfaces,'hotspot'),'172.20.10.1')
 def test_wifi_is_never_used_as_hotspot_fallback(self):
  interfaces=[('en0','172.40.4.86'),('pdp_ip0','10.36.96.189')]
  self.assertEqual(self.network.select_address(interfaces),'172.40.4.86')
  self.assertEqual(self.network.select_address(interfaces,'hotspot'),'')
 def test_android_hotspot_and_rejected_interfaces(self):
  self.assertEqual(self.network.select_address([('ap0','192.168.43.1')],'hotspot'),'192.168.43.1')
  self.assertEqual(self.network.select_address([('ap0','192.168.43.1')]),'')
  self.assertEqual(self.network.select_address([('wlan0','192.168.50.1')],'hotspot'),'')
  bad=[('wlan0','169.254.1.1'),('bridge0','0.0.0.0'),('wlan1','::1'),('rmnet0','10.1.1.1'),('utun0','192.168.1.1')]
  self.assertEqual(self.network.select_address(bad,'hotspot'),'')

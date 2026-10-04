"""Wire-level checks for cached public assets and uncached private responses."""
import gzip,json,tempfile,threading,unittest,re
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from server import make_server

class LoadingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.server=make_server(0,data_dir=self.tmp.name,bind='127.0.0.1',lan_address='192.168.1.2')
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.addCleanup(self.stop);self.base=f'http://127.0.0.1:{self.server.server_port}'
 def stop(self):self.server.shutdown();self.server.server_close();self.thread.join()
 def get(self,path,headers=None):return urlopen(Request(self.base+path,headers=headers or {}),timeout=3)
 def test_webp_asset_and_conditional_revalidation(self):
  with self.get('/assets/zhajinhua-scene-v1.webp') as r:
   raw=r.read();tag=r.headers['ETag'];self.assertEqual(r.headers['Content-Type'],'image/webp');self.assertIn('max-age=',r.headers['Cache-Control']);self.assertEqual(raw[:4],b'RIFF')
  with self.assertRaises(HTTPError) as e:self.get('/assets/zhajinhua-scene-v1.webp',{'If-None-Match':tag})
  self.assertEqual(e.exception.code,304);self.assertEqual(e.exception.read(),b'')
 def test_code_is_revalidated_and_gzip_is_negotiated(self):
  with self.get('/app.js',{'Accept-Encoding':'gzip'}) as r:
   self.assertEqual(r.headers['Cache-Control'],'no-cache');self.assertEqual(r.headers['Content-Encoding'],'gzip');self.assertIn(b'async function poll',gzip.decompress(r.read()))
  with self.get('/app.js',{'Accept-Encoding':'gzip;q=0'}) as r:self.assertIsNone(r.headers['Content-Encoding']);self.assertIn(b'async function poll',r.read())
 def test_state_is_never_cached_and_compression_preserves_content(self):
  with self.get('/api/state',{'Accept-Encoding':'gzip'}) as r:
   raw=r.read();self.assertEqual(r.headers['Cache-Control'],'no-store');self.assertIsNone(r.headers['ETag']);self.assertIn('players',json.loads(gzip.decompress(raw) if r.headers['Content-Encoding']=='gzip' else raw))
  with self.get('/entry-qr.png') as r:self.assertEqual(r.headers['Cache-Control'],'no-store');self.assertEqual(r.read()[:8],b'\x89PNG\r\n\x1a\n')
 def test_unlisted_assets_are_not_exposed(self):
  with self.assertRaises(HTTPError) as e:self.get('/assets/ASSETS.md')
  self.assertEqual(e.exception.code,404)

 def test_css_scene_assets_are_served(self):
  static=Path(__file__).parent/'static'
  css='\n'.join((static/name).read_text() for name in ('style.css','theme.css'))
  paths=set(re.findall(r"url\(['\"]?(?:\./)?(assets/[^)'\"\s]+\.webp)",css))
  self.assertTrue(any('holdem-scene-iphone-' in path for path in paths))
  for path in paths:
   with self.subTest(asset=path),self.get('/'+path) as response:
    self.assertEqual(response.headers['Content-Type'],'image/webp')
    self.assertEqual(response.read()[:4],b'RIFF')

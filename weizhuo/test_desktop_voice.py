import io,json,tempfile,threading,unittest,wave
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from announcer import LocalAnnouncer
from server import make_server,Handler

class DesktopVoiceTests(unittest.TestCase):
    def test_serena_preserves_every_sample_and_rejects_unknown_sentence(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);clips=base/'Serena';clips.mkdir();pcm=b'\x00\x01\x00\xff'*200
            with wave.open(str(clips/'sentence.wav'),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(pcm)
            (clips/'manifest.json').write_text(json.dumps({'methodVersion':'context-v2','recipes':{'三号玩家弃牌':['sentence.wav']},'segments':{}}))
            speaker=LocalAnnouncer(base)
            with wave.open(io.BytesIO(speaker.render('三号玩家弃牌',3))) as f:self.assertEqual(f.readframes(f.getnframes()),pcm)
            with self.assertRaises(ValueError):speaker.render('未知动作',3)
            speaker.lock.acquire()
            try:
                with self.assertRaises(ValueError):speaker.render('三号玩家弃牌',3)
            finally:speaker.lock.release()

    def test_http_voice_is_local_host_only_and_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            server=make_server(0,data_dir=directory,bind='127.0.0.1')
            class Fake:
                choices=[0,1,2,3]
                def render(self,text,voice):return b'RIFF-audio'
            server.announcer=Fake();thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            room=server.rooms.create({'game':'mahjong','name':'语音测试','nickname':'房主'})
            data={**room,'voice':3,'text':'三号玩家弃牌'}
            def send(value,origin=None):return urlopen(Request(base+'/api/voice',data=json.dumps(value).encode(),headers={'Content-Type':'application/json',**({'Origin':origin} if origin else {})}),timeout=3)
            try:
                with send(data) as response:self.assertEqual(response.read(),b'RIFF-audio');self.assertEqual(response.headers['Cache-Control'],'no-store');self.assertEqual(response.headers['Content-Type'],'audio/wav')
                for payload,origin in (({**data,'token':'invalid'},None),(data,'https://untrusted.example')):
                    with self.assertRaises(HTTPError) as error:send(payload,origin)
                    self.assertEqual(error.exception.code,403)
                with patch.object(Handler,'is_service_device_request',return_value=False):
                    with self.assertRaises(HTTPError) as error:send(data)
                    self.assertEqual(error.exception.code,403)
                    with urlopen(base+'/api/bootstrap') as response:self.assertEqual(json.load(response)['voiceChoices'],[])
            finally:server.shutdown();server.server_close();thread.join()

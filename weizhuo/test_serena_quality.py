"""Reject corrupt, mismatched and elongated recordings before bundling."""
import importlib.util,tempfile,unittest,wave,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('serena_quality',Path(__file__).parent/'mobile/serena_quality.py')
quality=importlib.util.module_from_spec(spec);spec.loader.exec_module(quality)
class SerenaQualityTests(unittest.TestCase):
 def clip(self,path,seconds,rate=24000):
  with wave.open(str(path),'wb') as f:
   f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes(b'\1\0'*int(rate*seconds))
 def test_old_elongations_fail_and_reviewed_duration_passes(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'word.wav'
   for text,seconds in [('行动',1.69),('一百',21.945),('五',19.72)]:
    self.clip(p,seconds);self.assertFalse(quality.audit_clip(text,p)['passed'])
   self.clip(p,.845);self.assertTrue(quality.audit_clip('行动',p)['passed'])
 def test_invalid_rate_or_missing_file_fails(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'word.wav';self.assertFalse(quality.audit_clip('弃牌',p)['passed'])
   self.clip(p,.85,16000);self.assertFalse(quality.audit_clip('弃牌',p)['passed'])
 def test_empty_or_truncated_audio_fails(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'word.wav';self.clip(p,.02);self.assertFalse(quality.audit_clip('行动',p)['passed'])
   p.write_bytes(b'not a WAV');self.assertFalse(quality.audit_clip('行动',p)['passed'])
 def test_library_gate_rechecks_files_instead_of_trusting_a_report(self):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);p=base/'word.wav'
   (base/'manifest.json').write_text(json.dumps({'clips':{'行动':'word.wav'}}))
   self.clip(p,.845);self.assertEqual(quality.verify_library(base),1)
   self.clip(p,1.69)
   with self.assertRaisesRegex(ValueError,'行动'):quality.verify_library(base)

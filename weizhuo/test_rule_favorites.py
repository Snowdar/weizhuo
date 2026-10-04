from pathlib import Path
import tempfile,unittest
from scoring.repository import Repository
from scoring.rooms import Rooms

class RuleFavoritesTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name)/'rooms.sqlite3';self.rooms=Rooms(Repository(self.path));self.key='a'*32
 def save(self,text='胜者得 10 分',name='桌游'):
  return self.rooms.device_rule_favorites(self.key,dict(action='save',name=name,text=text))
 def test_restart_identity_and_isolation(self):
  saved=self.save();restored=Rooms(Repository(self.path))
  self.assertEqual(restored.device_rule_favorites(self.key),saved)
  self.assertEqual(restored.device_rule_favorites('b'*32),[])
  restored.device_rule_favorites('b'*32,dict(action='remove',id=saved[0]['id']))
  self.assertEqual(restored.device_rule_favorites(self.key),saved)
 def test_duplicate_and_remove(self):
  first=self.save();second=self.save(name='新标题')
  self.assertEqual(len(second),1);self.assertEqual(first[0]['id'],second[0]['id']);self.assertEqual(second[0]['name'],'新标题')
  self.assertEqual(self.rooms.device_rule_favorites(self.key,dict(action='remove',id=first[0]['id'])),[])
 def test_invalid_does_not_change_existing(self):
  before=self.save()
  for change in [[],{},dict(action='save',name='',text='x'),dict(action='save',name='n',text=''),dict(action='save',name='n',text='x'*2001),dict(action='save',name='x'*31,text='ok'),dict(action='remove',id=1)]:
   with self.assertRaises(ValueError):self.rooms.device_rule_favorites(self.key,change)
  with self.assertRaises(ValueError):self.rooms.device_rule_favorites('invalid')
  self.assertEqual(self.rooms.device_rule_favorites(self.key),before)
 def test_bound_and_unicode(self):
  for i in range(50):self.save(text=f'第 {i} 组规则\n特殊情况：+10 / -5')
  with self.assertRaises(ValueError):self.save('第 51 条')
  self.assertEqual(len(self.rooms.device_rule_favorites(self.key)),50)
if __name__=='__main__':unittest.main()

import unittest,test_rules
class RoundLimits(unittest.TestCase):
 setUp=test_rules.RoomLifecycle.setUp
 state=test_rules.RoomLifecycle.state
 do=test_rules.RoomLifecycle.do
 start=test_rules.RoomLifecycle.start
 total=test_rules.RoomLifecycle.total
 def test_first_round_compare_allowed_when_one(self):
  self.do('config',config={**self.state()['config'],'minCompare':1});self.start()
  self.do('compare',id=self.ids[1]);self.assertEqual(self.state()['phase'],'comparing')
  self.assertEqual(self.state()['round'],1)
 def test_compare_waits_for_configured_round(self):
  self.do('config',config={**self.state()['config'],'minCompare':2});self.start()
  with self.assertRaises(ValueError):self.do('compare',id=self.ids[1])
  for t in self.tokens:self.do('call',token=t)
  self.do('compare',id=self.ids[1]);self.assertEqual(self.state()['phase'],'comparing')
 def test_limit_seven_finishes_seven_full_rounds(self):
  self.do('config',config={**self.state()['config'],'maxRounds':7});self.start()
  for i in range(21):
   self.assertEqual(self.state()['phase'],'playing')
   self.do('call',token=self.tokens[i%3])
  s=self.state();self.assertEqual(s['phase'],'showdown');self.assertEqual(s['round'],7)
  self.assertIsNone(s['turn']);self.assertTrue(all(p['seen'] for p in s['players']))
  with self.assertRaises(ValueError):self.do('call')
  self.do('settle',id=self.ids[1]);self.assertEqual(self.total(),3000)
 def test_unlimited_continues_after_seven_rounds(self):
  self.do('config',config={**self.state()['config'],'maxRounds':0});self.start()
  for i in range(30):self.do('call',token=self.tokens[i%3])
  self.assertEqual(self.state()['phase'],'playing');self.assertEqual(self.state()['round'],11)

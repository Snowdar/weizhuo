"""Verify platform bridge routing without requiring an Apple runtime."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import tempfile
import json

PATH=Path(__file__).parent/'mobile/src/weizhuomobile/speech.py'
sys.path.insert(0,str(PATH.parents[1]))
spec=importlib.util.spec_from_file_location('weizhuomobile.speech',PATH)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class NativeSpeechTests(unittest.TestCase):
    def test_android_uses_native_chinese_queue_and_status(self):
        native=Mock();native.busy.return_value=False;native.getStatus.return_value='系统音色已就绪';native.available.return_value=False;native.getVoicePath.return_value=''
        activity=object()
        def jclass(name):
            if name=='org.beeware.android.MainActivity':return types.SimpleNamespace(singletonThis=activity)
            self.assertEqual(name,'com.snowdar.weizhuomobile.WeizhuoSpeaker')
            return lambda context:native
        with patch.object(sys,'platform','linux'),patch.object(sys,'getandroidapilevel',lambda:31,create=True),patch.dict(sys.modules,{'java':types.SimpleNamespace(jclass=jclass)}):
            speaker=module.Speaker()
            self.assertEqual(speaker.choices,[0]);self.assertTrue(speaker.ready)
            self.assertEqual(speaker.status,'系统音色已就绪')
            speaker.say('7号玩家，AbC，跟注20分')
            native.speakText.assert_called_once_with('7号玩家跟注20分')
            native.busy.return_value=True;self.assertFalse(speaker.ready)
            speaker.stop();native.stopSpeakingAtBoundary.assert_called_once_with(0)

    def speaker(self,available=True,missing=False,saved=None,selected=2):
        native=Mock();native.available.return_value=available;native.voice=2;native.busy.return_value=False
        system=Mock();system.busy.return_value=False;system.isSpeaking.return_value=False
        def objc(name):
            if name=='WZOfflineSpeaker':
                if missing:raise NameError(name)
                cls=Mock();cls.sharedSpeaker.return_value=native;return cls
            cls=Mock()
            if name=='NSUserDefaults':
                cls.standardUserDefaults.objectForKey.return_value=saved
                cls.standardUserDefaults.integerForKey.return_value=selected
            elif name=='NSBundle':cls.mainBundle.pathForResource.return_value='/tmp/missing-voice-test'
            else:cls.alloc.return_value.init.return_value=system
            return cls
        packages={'rubicon':types.ModuleType('rubicon'),'rubicon.objc':types.SimpleNamespace(ObjCClass=objc)}
        with patch.object(sys,'platform','ios'),patch.dict(sys.modules,packages),patch('ctypes.CDLL'):
            speaker=module.Speaker()
        native.reset_mock()
        return speaker,native,system
    def test_context_variables_and_continuous_action_sequence(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            tokens=['号玩家','给了','分','轮到','行动','跟注','弃牌','本局已结算','一','二','三','十','百','千','万','亿','零','四','五','六','七','八','九']
            segments={t:[str(i)+'.wav'] for i,t in enumerate(tokens)}
            for names in segments.values():(p/names[0]).write_bytes(b'context fixture')
            (p/'pause.wav').write_bytes(b'pause fixture')
            (p/'manifest.json').write_text(json.dumps({'methodVersion':'context-v2','clips':{},'recipes':{},'segments':segments,'pause':'pause.wav'}))
            speaker,native,system=self.speaker();speaker.clips=module.SerenaClips(p)
            self.assertIn(3,speaker.choices);speaker.set_voice(3)
            for text in ('21号玩家给了2号玩家1280分','三号玩家跟注二十分。三号玩家弃牌。本局已结算。'):
                self.assertIsNotNone(speaker.clips.plan(text));speaker.say(text)
                payload=json.loads(native.speakClipPaths.call_args.args[0])
                self.assertTrue(payload['preserveSamples']);self.assertTrue(all(Path(x).is_file() for x in payload['paths']))
            system.speakText.assert_not_called()
            self.assertIsNone(speaker.clips.plan('21号玩家未知动作'))
            (p/'0.wav').unlink();self.assertIsNone(speaker.clips.plan('1号玩家弃牌'))

    def test_context_planner_minimizes_junctions_and_backtracks_compound_actions(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);segments={'三号玩家全下':['prefix.wav'],'一':['one.wav'],'千':['thousand.wav'],'零':['zero.wav'],'五分':['five.wav'],'三号玩家':['actor.wav'],'全下一千零五分':['action-amount.wav'],'三号玩家比牌':['compare-prefix.wav'],'比牌出局':['lost.wav']}
            for names in segments.values():
                for name in names:(p/name).write_bytes(b'context fixture')
            (p/'manifest.json').write_text(json.dumps({'methodVersion':'context-v2','segments':segments,'recipes':{}}))
            clips=module.SerenaClips(p)
            self.assertEqual([Path(x).name for x in clips.plan('3号玩家全下1005分')],['actor.wav','action-amount.wav'])
            self.assertEqual([Path(x).name for x in clips.plan('3号玩家比牌出局')],['actor.wav','lost.wav'])

    def test_saved_native_number_does_not_break_startup(self):
        # NSNumber is represented by an opaque ObjCInstance, with no int protocol.
        speaker,_,_=self.speaker(saved=object(),selected=1)
        self.assertEqual(speaker.voice,1)
        speaker,_,_=self.speaker(saved=object(),selected=999)
        self.assertEqual(speaker.voice,2)
        speaker,_,_=self.speaker(saved=object(),selected='invalid')
        self.assertEqual(speaker.voice,2)
    def test_selected_voices_and_speech_route(self):
        speaker,native,_=self.speaker()
        self.assertTrue(speaker.offline)
        speaker.set_voice(1);speaker.say('三号玩家跟注25分');speaker.stop()
        native.setVoice.assert_called_once_with(1)
        native.speakText.assert_called_once_with('三号玩家跟注25分')
        self.assertGreaterEqual(native.stop.call_count,1)
        speaker.set_voice(9);self.assertEqual(speaker.voice,1)
    def test_missing_model_uses_system_voice(self):
        speaker,_,system=self.speaker(available=False)
        self.assertFalse(speaker.offline);self.assertIs(speaker.native,system)
        speaker.stop();system.stopSpeakingAtBoundary.assert_called_once_with(0)
    def test_unconfigured_build_uses_system_voice(self):
        speaker,_,system=self.speaker(missing=True)
        self.assertFalse(speaker.offline);self.assertIs(speaker.native,system)

    def test_webkit_float_voice_is_normalized_before_objc_call(self):
        speaker,native,_=self.speaker()
        speaker.set_voice(2.0)
        native.setVoice.assert_called_once_with(2)
        self.assertIs(type(native.setVoice.call_args.args[0]),int)
        speaker.say('三号玩家弃牌')
        native.speakText.assert_called_once_with('三号玩家弃牌')
        native.reset_mock()
        for invalid in (None,True,1.5,'2',float('nan')):speaker.set_voice(invalid)
        native.setVoice.assert_not_called()

    def test_nickname_is_removed_for_every_announcer(self):
        speaker,native,_=self.speaker()
        speaker.say('7号玩家，AbC，跟注20分')
        native.speakText.assert_called_once_with('7号玩家跟注20分')
    def test_system_option_does_not_interrupt_previous_utterance(self):
        speaker,native,system=self.speaker()
        speaker.set_voice(0);system.reset_mock()
        objc=Mock();objc.return_value.speechVoices.return_value=[]
        with patch.dict(sys.modules,{'rubicon.objc':types.SimpleNamespace(ObjCClass=objc)}):
            speaker.say('弃牌');speaker.say('本局已结算')
        self.assertEqual(system.speakText.call_count,2)
        system.stopSpeakingAtBoundary.assert_not_called()
    def test_serena_whole_amount_and_nickname_handling(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'manifest.json').write_text(json.dumps({'clips':{'一号玩家':'a.wav','二号玩家':'b.wav','给了':'give.wav','二十五分':'25.wav'}}))
            clips=module.SerenaClips(p)
            plan=clips.plan('1号玩家，小甲，给了2号玩家，小乙，25分')
            self.assertEqual([Path(x).name for x in plan],['a.wav','give.wav','b.wav','25.wav'])
            self.assertIsNone(clips.plan('未知提醒'))
        self.assertEqual(module.chinese_number(10005),'一万零五')
        self.assertEqual(module.chinese_number(1280),'一千二百八十')

    def test_context_bank_remains_selectable_and_preserves_approved_samples(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'whole.wav').write_bytes(b'approved audio fixture')
            (p/'manifest.json').write_text(json.dumps({'methodVersion':'context-v1',
                'clips':{},'recipes':{'轮到一号玩家行动':['whole.wav']}}))
            speaker,native,system=self.speaker()
            speaker.clips=module.SerenaClips(p)
            self.assertIn(3,speaker.choices)
            speaker.set_voice(3);speaker.say('轮到1号玩家行动')
            payload=json.loads(native.speakClipPaths.call_args.args[0])
            self.assertTrue(payload['preserveSamples'])
            self.assertEqual(payload['paths'],[str(p/'whole.wav')])
            system.speakText.assert_not_called()
            speaker.say('十九号玩家加注9876分')
            system.speakText.assert_not_called()
            self.assertEqual(speaker.status,'暖语暂未覆盖本句，请查看文字记录')
            self.assertEqual(native.speakClipPaths.call_count,1)
            speaker.clips=None;speaker.say('十九号玩家加注9876分')
            system.speakText.assert_not_called()

    def test_fallback_waits_for_previous_native_playback(self):
        speaker,native,system=self.speaker()
        self.assertTrue(speaker.ready)
        native.busy.return_value=True
        self.assertFalse(speaker.ready)
        native.busy.return_value=False;system.busy.return_value=True
        self.assertFalse(speaker.ready)
        system.busy.return_value=False
        self.assertTrue(speaker.ready)

    def test_context_recipe_never_reverts_to_loose_word_splicing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for name in ('prefix.wav','amount.wav'):(p/name).write_bytes(b'fixture')
            (p/'manifest.json').write_text(json.dumps({'methodVersion':'context-v1',
                'clips':{'分':'old.wav'},'recipes':{'一号玩家给了二号玩家一分':['prefix.wav','amount.wav']}}))
            clips=module.SerenaClips(p)
            self.assertEqual([Path(x).name for x in clips.plan('1号玩家给了2号玩家1分')],['prefix.wav','amount.wav'])
            self.assertIsNone(clips.plan('分'))
            speaker,native,_=self.speaker();speaker.voice=3;speaker.clips=clips
            speaker.say('1号玩家给了2号玩家1分')
            payload=json.loads(native.speakClipPaths.call_args.args[0])
            self.assertIs(payload['preserveSamples'],True)
            (p/'amount.wav').unlink();self.assertIsNone(clips.plan('1号玩家给了2号玩家1分'))

    def test_serena_overlong_plan_falls_back_instead_of_dropping(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'manifest.json').write_text(json.dumps({'clips':{'分':'unit.wav'}}))
            self.assertIsNone(module.SerenaClips(p).plan('分'*121))

    def test_shared_text_is_number_only_in_system_and_serena_routes(self):
        speaker,native,system=self.speaker()
        speaker.set_voice(0);system.reset_mock()
        speaker.say('三号玩家，小甲ABC，弃牌')
        system.speakText.assert_called_once_with('三号玩家弃牌')
        self.assertEqual(module.announcer_text('7号玩家，Snow，给了3号玩家，小乙，60分'),'7号玩家给了3号玩家60分')


class SerenaTemplateFamilyTests(unittest.TestCase):
    def test_scoped_amounts_do_not_mix_actions_or_guess_values(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for name in ['call-prefix.wav','bet-prefix.wav','call-amount.wav','bet-amount.wav','whole.wav']:(p/name).write_bytes(b'fixture')
            manifest={'methodVersion':'context-v2','recipes':{},'segments':{},'templateBanks':{
                '跟注':{'prefixes':{'一号玩家跟注':['call-prefix.wav']},'amounts':{'一万零五分':['call-amount.wav']},'approvedPairs':{'一号玩家跟注':['一万零五分']}},
                '下注':{'prefixes':{'一号玩家下注':['bet-prefix.wav']},'amounts':{'一万零五分':['bet-amount.wav']},'approvedPairs':{'一号玩家下注':['一万零五分']}}}}
            (p/'manifest.json').write_text(json.dumps(manifest));clips=module.SerenaClips(p)
            self.assertEqual([Path(x).name for x in clips.plan('1号玩家跟注10005分')],['call-prefix.wav','call-amount.wav'])
            self.assertEqual([Path(x).name for x in clips.plan('1号玩家下注10005分')],['bet-prefix.wav','bet-amount.wav'])
            self.assertIsNone(clips.plan('1号玩家跟注10006分'),'never substitute the nearest recorded amount')
            self.assertIsNone(clips.plan('2号玩家跟注10005分'),'never substitute another player')
            manifest['templateBanks']['跟注']['amounts']['二十分']=['call-amount.wav']
            (p/'manifest.json').write_text(json.dumps(manifest))
            self.assertIsNone(module.SerenaClips(p).plan('1号玩家跟注20分'),'an available slot is not an approved assembled pair')
            manifest['recipes']['一号玩家跟注一万零五分']=['whole.wav'];(p/'manifest.json').write_text(json.dumps(manifest))
            self.assertEqual([Path(x).name for x in module.SerenaClips(p).plan('1号玩家跟注10005分')],['whole.wav'])
            manifest['recipes']={};manifest['templateBanks']['跟注']['amounts']['一万零五分']=['../outside.wav'];(p/'manifest.json').write_text(json.dumps(manifest))
            self.assertIsNone(module.SerenaClips(p).plan('1号玩家跟注10005分'))

"""Prevent hidden syllable loss and accidental approval in voice preparation."""
import sys
import unittest
import hashlib
import json
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'mobile'))
from serena_templates import candidate_combinations, piece_ranges, quiet_boundaries
from review_serena import validated_review, Reviewer
from refine_serena_edges import declick, quiet_cut, trim_quiet_edges
from array import array
from unittest.mock import patch
from io import BytesIO
from adopt_serena import checked_selections, adopt, adopt_many


class ContextTemplateTests(unittest.TestCase):
    @unittest.skipUnless(__import__('importlib.util').util.find_spec('numpy'),'Development acoustic check requires numpy')
    def test_quiet_cut_preserves_samples_and_avoids_loud_syllables(self):
        import numpy as np
        pcm=np.full(24000,6000,dtype=np.int16);pcm[10800:13200]=0
        ranges=quiet_boundaries(pcm,[(0,.52),(.52,1)])
        cut=round(ranges[0][1]*24000)
        self.assertTrue(10800<=cut<=13200)
        rebuilt=np.concatenate([pcm[round(a*24000):round(b*24000)] for a,b in ranges])
        np.testing.assert_array_equal(pcm,rebuilt)
        with self.assertRaisesRegex(ValueError,'No measured quiet boundary'):
            quiet_boundaries(np.full(24000,6000,dtype=np.int16),[(0,.5),(.5,1)])

    def test_declick_preserves_duration_and_speech_body(self):
        original=array('h',[8000]*1000);result=declick(original)
        self.assertEqual(len(result),len(original))
        self.assertEqual(result[0],0);self.assertEqual(result[-1],0)
        self.assertEqual(result[12:-12],original[12:-12])
        self.assertEqual(original[0],8000,'source must not be modified')
        silent=array('h',[0]*100);self.assertEqual(declick(silent),silent)

    def test_acoustic_refinement_never_guesses_a_loud_cut(self):
        samples=array('h',[9000]*6000)
        self.assertEqual(quiet_cut(samples,3000),3000)
        samples[2640:2880]=array('h',[0]*240)
        cut=quiet_cut(samples,3000)
        self.assertTrue(2700<=cut<=2820)
        self.assertEqual(quiet_cut(samples,0),0)
        self.assertEqual(quiet_cut(samples,len(samples)),len(samples))

    def test_only_long_quiet_exterior_is_shortened(self):
        body=array('h',[1000]*2400);samples=array('h',[0]*4800)+body+array('h',[0]*4800)
        result,proof=trim_quiet_edges(samples)
        self.assertEqual(result,array('h',[0]*1200)+body+array('h',[0]*1200))
        self.assertEqual(proof['guardSamples'],1200)
        short=array('h',[0]*2400)+body
        self.assertEqual(trim_quiet_edges(short)[0],short)

    def test_candidates_compare_complete_takes_before_cross_splices(self):
        options=[[{'file':f'actor-{n}'} for n in range(3)],[{'file':f'amount-{n}'} for n in range(3)]]
        rows=list(candidate_combinations(options,4))
        self.assertEqual([[p['file'] for p in row] for row in rows[:3]],[[f'actor-{n}',f'amount-{n}'] for n in range(3)])
        self.assertEqual(len({tuple(p['file'] for p in row) for row in rows}),4)
        self.assertEqual(list(candidate_combinations([[]],3)),[])

    def test_whole_recording_needs_no_cut_alignment(self):
        self.assertEqual(piece_ranges('轮到一号玩家行动。', ['轮到一号玩家行动'], [], 1.8), [(0.0, 1.8)])
        with self.assertRaises(ValueError):
            piece_ranges('轮到一号玩家行动。', ['轮到二号玩家行动'], [], 1.8)

    def test_alignment_token_cannot_be_split_by_guessing(self):
        words = [dict(word='全下一', start=0, end=.8), dict(word='百分', start=.8, end=1.3)]
        with self.assertRaisesRegex(ValueError, 'crosses a cut'):
            piece_ranges('全下一百分。', ['全下', '一百分'], words, 1.4)

    def test_partition_has_no_overlap_or_missing_interval(self):
        words = [dict(word='加注', start=.1, end=.5), dict(word='一百分', start=.55, end=1.2)]
        self.assertEqual(piece_ranges('加注一百分。', ['加注', '一百分'], words, 1.3),
                         [(0, .55), (.55, 1.3)])

    def test_missing_amount_and_unfinished_review_cannot_pass(self):
        review = dict(missing_or_changed_words=False, issues=[], scores=dict(
            clarity=5, continuity=5, timbre_stability=5, pace=5, fullness=5))
        result = validated_review(dict(transcript='一号玩家给了二号玩家', uncertain=False),
                                  review, '一号玩家给了二号玩家一分')
        self.assertEqual(result['status'], 'model_rejected')
        with self.assertRaises(ValueError):
            validated_review(dict(transcript='一分', uncertain=False), {}, '一分')

    def test_model_score_is_shortlist_not_human_approval(self):
        review = dict(missing_or_changed_words=False, issues=[], scores=dict(
            clarity=5, continuity=5, timbre_stability=5, pace=5, fullness=5))
        self.assertEqual(validated_review(dict(transcript='一分。', uncertain=False), review,
                                         '一分')['status'], 'model_shortlisted_needs_human_listening')

    def test_number_spelling_is_not_a_missing_syllable(self):
        review = dict(missing_or_changed_words=False, issues=[], scores=dict(
            clarity=5, continuity=5, timbre_stability=5, pace=5, fullness=5))
        result = validated_review(dict(transcript='轮到一号玩家行动', uncertain=False),
                                  review, '轮到1号玩家行动')
        self.assertTrue(result['textMatch'])

    def test_english_case_does_not_hide_missing_action_or_amount(self):
        review=dict(missing_or_changed_words=False,issues=[],scores=dict(clarity=5,continuity=5,timbre_stability=5,pace=5,fullness=5))
        blind=dict(transcript='一号玩家 all in 二十分',uncertain=False)
        self.assertTrue(validated_review(blind,review,'一号玩家 All in 20分')['textMatch'])
        self.assertFalse(validated_review(blind,review,'一号玩家 All in 200分')['textMatch'])
        self.assertFalse(validated_review(dict(transcript='一号玩家二十分',uncertain=False),review,'一号玩家 All in 20分')['textMatch'])

    def test_curated_homophones_never_hide_changed_amount(self):
        review=dict(missing_or_changed_words=False,issues=[],scores=dict(clarity=5,continuity=5,timbre_stability=5,pace=5,fullness=5))
        blind=dict(transcript='一号玩家闷住一百分',uncertain=False)
        self.assertEqual(validated_review(blind,review,'一号玩家闷注一百分')['status'],'model_rejected')
        self.assertTrue(validated_review(blind,review,'一号玩家闷注一百分',True)['textMatch'])
        self.assertEqual(validated_review(blind,review,'一号玩家闷注一分',True)['status'],'model_rejected')
        same=dict(transcript='一号玩家权下一千零五分',uncertain=False)
        self.assertEqual(validated_review(same,review,'一号玩家全下1005分',True)['status'],'model_shortlisted_needs_human_listening')
        self.assertEqual(validated_review(same,review,'一号玩家全下105分',True)['status'],'model_rejected')

    def test_official_dots_auth_header(self):
        with tempfile.TemporaryDirectory() as d:
            wav=Path(d)/'dummy.wav';wav.write_bytes(b'non-personal test audio')
            body=json.dumps({'choices':[{'message':{'content':'{"transcript":"一分"}'}}]}).encode()
            with patch.dict('os.environ', {'DOTS_API_KEY':'test-only-value'}), patch(
                    'review_serena.urlopen', return_value=BytesIO(body)) as send:
                reviewer=Reviewer('dots','dots3-note-prev')
                self.assertEqual(reviewer.call('blind review',[wav]), {'transcript':'一分'})
                request=send.call_args.args[0]
                self.assertEqual(request.get_header('Api-key'),'test-only-value')
                self.assertIsNone(request.get_header('Authorization'))

    def test_adoption_rejects_stale_audio_and_missing_review(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);audio=base/'example.wav';audio.write_bytes(b'approved version')
            (base/'report.json').write_text(json.dumps({'examples':[dict(id='give',file=audio.name,text='一分',issues=[])]}))
            selection=[dict(id='give',accepted=True,sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),reviewNote='Reviewed complete sentence')]
            self.assertEqual(len(checked_selections(base,selection)),1)
            selection[0]['reviewNote']=''
            with self.assertRaisesRegex(ValueError,'evidence'):checked_selections(base,selection)
            selection[0]['reviewNote']='Reviewed complete sentence';audio.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'different audio'):checked_selections(base,selection)

    def test_multiple_review_batches_preserve_distinct_recipes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);dirs=[];selections=[]
            for index,text in enumerate(('一分','二分')):
                base=root/str(index);base.mkdir();dirs.append(base)
                with wave.open(str(base/'same.wav'),'wb') as wav:
                    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000)
                    wav.writeframes(bytes([index+1,0])*24000)
                row=dict(id='same-id',text=text,file='same.wav',issues=[],parts=[dict(file='same.wav')])
                (base/'report.json').write_text(json.dumps({'examples':[row]}))
                selections.append([dict(id='same-id',accepted=True,
                    sha256=hashlib.sha256((base/'same.wav').read_bytes()).hexdigest(),reviewNote='fixture approval')])
            self.assertEqual(adopt_many(dirs,selections,root/'Serena'),2)
            bank=json.loads((root/'Serena/manifest.json').read_text())
            self.assertEqual(set(bank['recipes']),{'一分','二分'})
            self.assertNotEqual(bank['recipes']['一分'],bank['recipes']['二分'])

    def test_adoption_contains_only_referenced_audio_and_keeps_old_bank(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);audition=base/'audition';audition.mkdir();out=base/'Serena';out.mkdir()
            (out/'old.wav').write_bytes(b'old bank')
            samples=b'\x01\x00'*24000
            for name,data in [('a.wav',samples[:19200]),('b.wav',samples[19200:]),('sentence.wav',samples)]:
                with wave.open(str(audition/name),'wb') as wav:
                    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(24000);wav.writeframes(data)
            (audition/'unused.wav').write_bytes(b'unused take')
            row=dict(id='one',text='一分',file='sentence.wav',issues=[],parts=[dict(file='a.wav'),dict(file='b.wav')])
            (audition/'report.json').write_text(json.dumps({'examples':[row]}))
            selection=[dict(id='one',accepted=True,sha256=hashlib.sha256((audition/'sentence.wav').read_bytes()).hexdigest(),reviewNote='fixture approval')]
            self.assertEqual(adopt(audition,selection,out),1)
            self.assertTrue((base/'Serena.previous/old.wav').exists())
            manifest=json.loads((out/'manifest.json').read_text())
            self.assertEqual(manifest['methodVersion'],'context-v1')
            self.assertFalse((out/'unused.wav').exists())
            self.assertEqual(len(list(out.glob('*.wav'))),2)

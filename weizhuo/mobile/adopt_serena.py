"""Atomically adopt explicitly reviewed contextual sentences, never loose legacy words."""
import argparse
import hashlib
import json
import shutil
import tempfile
import wave
from pathlib import Path


def checked_selections(audition, selection):
    report=json.loads((audition/'report.json').read_text())
    examples={row['id']:row for row in report['examples']}
    rows=[];texts=set()
    for accepted in selection:
        if accepted.get('accepted') is not True:
            continue
        row=examples[accepted['id']]
        wav=audition/row['file']
        if hashlib.sha256(wav.read_bytes()).hexdigest()!=accepted.get('sha256'):
            raise ValueError('Selection refers to a different audio version')
        if not isinstance(accepted.get('reviewNote'),str) or not accepted['reviewNote'].strip():
            raise ValueError('Record listening/review evidence before adoption')
        if row.get('issues'):
            raise ValueError('Signal defects must be fixed before adoption')
        if row['text'] in texts:
            raise ValueError('Choose only one candidate for each complete sentence')
        texts.add(row['text']);rows.append((row,accepted))
    if not rows:raise ValueError('No explicitly reviewed sentences selected')
    return rows


def adopt(audition, selection, output):
    rows=checked_selections(audition,selection)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='serena-stage-',dir=output.parent) as directory:
        stage=Path(directory);recipes={};evidence=[]
        for row,accepted in rows:
            names=[];frames=[]
            for part in row['parts']:
                name=part['file']
                if Path(name).name!=name:raise ValueError('Invalid piece filename')
                source=audition/name
                with wave.open(str(source)) as wav:
                    if (wav.getframerate(),wav.getnchannels(),wav.getsampwidth())!=(24000,1,2):
                        raise ValueError('Only 24kHz mono PCM16 is supported')
                    frames.append(wav.readframes(wav.getnframes()))
                destination=hashlib.sha256(source.read_bytes()).hexdigest()[:24]+'.wav'
                shutil.copy2(source,stage/destination);names.append(destination)
            with wave.open(str(audition/row['file'])) as wav:
                if b''.join(frames)!=wav.readframes(wav.getnframes()):
                    raise ValueError('Pieces do not reproduce the approved complete sentence')
            recipes[row['text']]=names
            evidence.append(dict(text=row['text'],selection=accepted,parts=row['parts']))
        manifest=dict(sampleRate=24000,speaker='Serena',source='Qwen3-TTS-12Hz-1.7B-CustomVoice',
                      methodVersion='context-v1',clips={},recipes=recipes)
        (stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        (stage/'review-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
        from serena_quality import verify_library
        verify_library(stage)
        # Keep one previous usable library; no accumulated unreferenced WAVs in the new bank.
        previous=output.with_name(output.name+'.previous')
        if previous.exists():raise ValueError('Move the existing .previous backup before another adoption')
        if output.exists():output.rename(previous)
        try:stage.rename(output)
        except BaseException:
            if previous.exists() and not output.exists():previous.rename(output)
            raise
    return len(recipes)



def adopt_many(auditions, selections, output):
    """Combine reviewed batches without changing their PCM or keeping unused takes."""
    if len(auditions)!=len(selections) or not auditions:
        raise ValueError('Pair each audition directory with one selection file')
    with tempfile.TemporaryDirectory(prefix='serena-reviewed-batches-') as directory:
        combined=Path(directory);examples=[];accepted=[]
        for index,(audition,selection) in enumerate(zip(auditions,selections)):
            for row,approval in checked_selections(audition,selection):
                row=dict(row);approval=dict(approval)
                row['id']=approval['id']=f'batch{index}-'+row['id']
                parts=[]
                for part in row['parts']:
                    name=part['file']
                    if Path(name).name!=name:raise ValueError('Invalid piece filename')
                    target=f'batch{index}-'+name
                    shutil.copy2(audition/name,combined/target)
                    parts.append(dict(part,file=target))
                original=row['file']
                if Path(original).name!=original:raise ValueError('Invalid sentence filename')
                row['file']=f'batch{index}-'+original
                shutil.copy2(audition/original,combined/row['file'])
                row['parts']=parts;examples.append(row);accepted.append(approval)
        (combined/'report.json').write_text(json.dumps({'examples':examples},ensure_ascii=False))
        return adopt(combined,accepted,output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audition',type=Path,action='append',required=True)
    parser.add_argument('--selection',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'.voice-assets/Voice/Serena')
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    if len(args.audition)!=len(args.selection):parser.error('Pair each --audition with --selection')
    selections=[json.loads(path.read_text()) for path in args.selection]
    count=sum(len(checked_selections(directory,selection)) for directory,selection in zip(args.audition,selections)) if args.check_only else adopt_many(args.audition,selections,args.output)
    print(f'{count} reviewed contextual sentences '+('validated' if args.check_only else 'adopted'))


if __name__=='__main__':main()

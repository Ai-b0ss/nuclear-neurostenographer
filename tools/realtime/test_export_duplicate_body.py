"""Regression: duplicate short phrases in TXT are checked at their own timestamps."""
import argparse
from collections import Counter
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from verify_transcript_exports import verify

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--evidence',type=Path,default=ROOT/'docs/evidence/consensus-phone-20261106/consensus-4voice')
    a=p.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        temp=Path(directory)
        for suffix in ('json','txt','srt'):
            shutil.copyfile(a.evidence/('transcript.'+suffix),temp/('transcript.'+suffix))
        verify(temp,'transcript')
        path=temp/'transcript.txt'
        lines=path.read_text(encoding='utf-8').splitlines()
        matched=[(i,re.match(r'^\[([^\]]+)\] (.*)$',line)) for i,line in enumerate(lines)]
        valid=[(i,match) for i,match in matched if match is not None]
        counts=Counter(match.group(2) for _,match in valid)
        repeated=[(i,match) for i,match in valid if counts[match.group(2)]>=2]
        if len(repeated)<2:raise AssertionError('No repeated TXT body in this evidence')
        idx,match=repeated[-1]
        start,end=match.group(1).split('–')
        modified=end[:-1]+('1' if end[-1]!='1' else '2')
        changed=lines.copy()
        changed[idx]=changed[idx].replace('–'+end+']','–'+modified+']',1)
        path.write_text('\n'.join(changed)+'\n',encoding='utf-8')
        try:verify(temp,'transcript')
        except AssertionError:pass
        else:raise AssertionError('Validator accepted corrupted duplicate timestamp')
        path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        verify(temp,'transcript')
        print('PASS exact timestamp duplicate body validation, corruption rejected')

if __name__=='__main__':main()
